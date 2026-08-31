"""Estado en memoria de la plataforma + orquestación de fases (plano de control).

Las fases 1-5 siguen siendo síncronas y simuladas. La fase de despliegue delega
la ejecución en un provider (mock o AWS Systems Manager Automation) mediante un
*job* persistido en SQLite: el store no ejecuta la operación, sólo crea el job,
lo reconcilia con `provider.poll()` y aplica el efecto cuando termina.
"""
from __future__ import annotations

import logging
import random
import threading
import zlib
from datetime import datetime

from . import engine, journey, seed
from .config import PROVIDER_AWS_AUTOMATION, PROVIDER_MOCK, Settings, get_settings
from .errors import (
    ConflictError,
    DependencyUnavailableError,
    NotFoundError,
    TargetNotAllowedError,
    ValidationError,
)
from .jobs import (
    JobState,
    JobType,
    PatchJob,
    is_terminal,
    new_job_id,
    state_for_execution,
)
from .lab import (
    LAB_STATE_PATCHED,
    LAB_STATE_UNKNOWN,
    LAB_STATE_VULNERABLE,
    RESTORE_KIND_RESET_LAB,
    LabTarget,
    synthetic_instance_id,
)
from .lab_lifecycle import LabLifecycleManager
from .lab_locks import OPERATION_PATCH as LOCK_OPERATION_PATCH
from .lab_locks import OPERATION_RESET as LOCK_OPERATION_RESET
from .lab_locks import LabLockManager, default_holder, get_lab_lock_backend
from .labs import (
    LabInstance,
    LabResolutionError,
    check_lab_tags,
    default_lab_target,
    get_lab_resolver,
    required_lab_tags,
)
from .policy import INSTANCE_ID_RE, evaluate_target, sanitize_text
from .precheck import get_lab_precheck
from .providers import get_patch_provider, get_restore_provider
from .providers.base import (
    PatchRequest,
    PatchSpec,
    ProviderError,
    RestoreRequest,
    Target,
    utcnow,
)
from .repository import JobRepository, TargetBusyError
from .runbooks import (
    OPERATION_PATCH,
    OPERATION_RESET_LAB,
    RunbookContractError,
    resolve_runbook,
)
from .seed import NOW, iso

# Códigos de provider que representan configuración ausente o dependencia caída.
_UNAVAILABLE_CODES = frozenset({"PROVIDER_UNAVAILABLE", "PROVIDER_MISCONFIGURED",
                                "RUNBOOK_NOT_CONFIGURED", "PROVIDER_START_FAILED"})
_TASK_SNAPSHOT_KEYS = ("id", "cve", "ci_id", "ci_name", "component", "track",
                       "vulnerable_version", "criticality", "environment")
# Estados a los que una reconciliación manual administrativa puede llevar un job
# cuyo resultado remoto no ha podido confirmarse. Nunca a «succeeded».
ADMIN_RESOLVABLE_STATES = (JobState.FAILED, JobState.CANCELLED, JobState.TIMED_OUT)

log = logging.getLogger("msr.store")


def sla_state(sla_due: str) -> dict:
    """Estado de cumplimiento del SLA de una tarea respecto a la fecha actual."""
    try:
        due = datetime.strptime(sla_due, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return {"due": sla_due, "days_left": None, "overdue": False, "days_overdue": 0}
    delta = due - NOW
    days_left = delta.days
    overdue = due < NOW
    return {
        "due": sla_due,
        "days_left": days_left,
        "overdue": overdue,
        "days_overdue": max(0, -days_left),
        "due_soon": (not overdue) and days_left <= 2,
    }


def _task_snapshot(task: dict) -> dict:
    """Subconjunto de la tarea que viaja al provider (sin datos sensibles)."""
    return {k: task.get(k) for k in _TASK_SNAPSHOT_KEYS if k in task}


def _patch_request_payload(request: PatchRequest) -> dict:
    return {
        "job_id": request.job_id, "task_id": request.task_id,
        "ring_number": request.ring_number,
        "targets": [t.as_dict() for t in request.targets],
        "spec": {"component": request.spec.component, "from_version": request.spec.from_version,
                 "to_version": request.spec.to_version, "cve": request.spec.cve,
                 "track": request.spec.track},
        "dry_run": request.dry_run, "correlation_id": request.correlation_id,
        "ring_label": request.ring_label, "executor": request.executor,
        "assets_count": request.assets_count, "task_snapshot": request.task_snapshot,
    }


def _patch_request_from_payload(payload: dict) -> PatchRequest:
    spec = payload.get("spec") or {}
    return PatchRequest(
        job_id=payload["job_id"], task_id=payload["task_id"],
        ring_number=int(payload["ring_number"]),
        targets=tuple(Target.from_dict(t) for t in payload.get("targets") or []),
        spec=PatchSpec(component=spec.get("component", "-"),
                       from_version=spec.get("from_version", ""),
                       to_version=spec.get("to_version", ""),
                       cve=spec.get("cve"), track=spec.get("track", "A")),
        dry_run=bool(payload.get("dry_run", True)),
        correlation_id=payload.get("correlation_id", ""),
        ring_label=payload.get("ring_label", ""),
        executor=payload.get("executor", ""),
        assets_count=int(payload.get("assets_count", 1)),
        task_snapshot=payload.get("task_snapshot") or {},
    )


def _restore_request_payload(request: RestoreRequest) -> dict:
    return {
        "job_id": request.job_id, "task_id": request.task_id,
        "ring_number": request.ring_number,
        "targets": [t.as_dict() for t in request.targets],
        "reason": request.reason, "target_version": request.target_version,
        "snapshot_ref": request.snapshot_ref, "dry_run": request.dry_run,
        "correlation_id": request.correlation_id, "restore_kind": request.restore_kind,
        "task_snapshot": request.task_snapshot,
    }


def _restore_request_from_payload(payload: dict) -> RestoreRequest:
    return RestoreRequest(
        job_id=payload["job_id"], task_id=payload["task_id"],
        ring_number=int(payload["ring_number"]),
        targets=tuple(Target.from_dict(t) for t in payload.get("targets") or []),
        reason=payload.get("reason", ""), target_version=payload.get("target_version", ""),
        snapshot_ref=payload.get("snapshot_ref"),
        dry_run=bool(payload.get("dry_run", True)),
        correlation_id=payload.get("correlation_id", ""),
        restore_kind=payload.get("restore_kind", "rollback"),
        task_snapshot=payload.get("task_snapshot") or {},
    )


class Store:
    def __init__(self, settings: Settings | None = None, repository: JobRepository | None = None,
                 patch_provider=None, restore_provider=None):
        self.settings = settings or get_settings()
        self.repo = repository or JobRepository(self.settings.jobs_db_absolute_path)
        self.patch_provider = patch_provider or get_patch_provider(self.settings)
        self.restore_provider = restore_provider or get_restore_provider(self.settings)
        # Resuelve el Instance ID del laboratorio por tags (nunca lo fija).
        self.lab_resolver = get_lab_resolver(self.settings, self.patch_provider, self.repo)
        # Evidencia de sólo lectura del estado real del laboratorio.
        self.lab_precheck = get_lab_precheck(self.settings, self.patch_provider, self.repo)
        # Lock de operación del laboratorio: exactamente una mutación a la vez
        # (patch, reset o reconciliación), también entre tasks independientes.
        self.lab_locks = LabLockManager(
            self.settings,
            get_lab_lock_backend(self.settings, self.repo, self.dynamodb_client),
            default_holder())
        # Reconciliador del laboratorio, independiente del reconciliador de jobs.
        self.lab_lifecycle = LabLifecycleManager(self)
        # Proyección en memoria ya aplicada (distinta del resultado persistido del
        # job): se reconstruye en cada rehidratación.
        self._projected: set[str] = set()
        self._job_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        log.info("store inicializado modo=%s patch_provider=%s restore_provider=%s",
                 self.settings.execution_mode(), self.patch_provider.name,
                 self.restore_provider.name)
        self.reset(clear_jobs=False)

    def dynamodb_client(self):
        """Cliente DynamoDB del provider AWS, con sus mismas credenciales."""
        provider = self.restore_provider
        if provider.name != PROVIDER_AWS_AUTOMATION:
            provider = self.patch_provider
        if provider.name != PROVIDER_AWS_AUTOMATION:
            return None
        return provider.dynamodb

    def reset(self, clear_jobs: bool = True):
        if clear_jobs:
            self.repo.clear()
        # Advisory, releasever y kernel corregido salen SIEMPRE de la
        # configuración (IaC/entorno), nunca de la petición del cliente.
        data = seed.build_all(
            lab_logical_id=self.settings.lab_logical_id,
            lab_advisory_id=self.settings.patch_advisory_id,
            lab_package_family=self.settings.patch_package_family,
            lab_releasever=self.settings.patch_releasever,
            lab_expected_fixed_kernel=self.settings.patch_expected_fixed_kernel,
            lab_region=self.settings.aws_region or None,
            lab_account_id=(self.settings.allowed_account_ids[0]
                            if self.settings.allowed_account_ids else None))
        self.cis = data["cis"]
        self.edges = data["edges"]
        self.findings = data["findings"]
        self.vulnerable_items = {v["id"]: v for v in data["vulnerable_items"]}
        self.tasks = {t["id"]: t for t in data["remediation_tasks"]}
        self.catalog = data["test_catalog"]
        # índice de adyacencia (una vez) para Impact Graph eficiente a 10k CIs
        self.adj = engine._build_adjacency(self.edges)
        self.ci_by_id = {c["id"]: c for c in self.cis}
        self.pipelines = {}
        self.activity = []  # feed global de actividad del agente

        # Distribución inicial de fases para una demo rica (varias en despliegue)
        start_phases = [5, 2, 5, 3, 4]
        for i, (tid, task) in enumerate(self.tasks.items()):
            self._init_pipeline(tid, start_phases[i % len(start_phases)])
        self._ensure_lab_target()
        # El estado funcional vive en memoria, pero los jobs son la fuente de
        # verdad: se re-proyectan desde SQLite en cada arranque.
        self.rehydrate_pipeline_state()

    def _ensure_lab_target(self) -> None:
        """Registra el laboratorio configurado si aún no está en SQLite."""
        logical_lab_id = self.settings.lab_logical_id
        if not logical_lab_id or self.repo.get_lab_target(logical_lab_id) is not None:
            return
        lab = default_lab_target(self.settings, logical_lab_id)
        if self.patch_provider.name == PROVIDER_MOCK:
            # En modo mock no hay EC2 que consultar: la instancia inicial del
            # laboratorio se simula (y cambia con cada reset).
            lab.current_instance_id = synthetic_instance_id(logical_lab_id, "genesis")
        self.repo.upsert_lab_target(lab)

    # ------------------------------------------------------------------
    def _init_pipeline(self, tid, phase_index):
        task = self.tasks[tid]
        impact = engine.build_impact_graph(task, self.cis, self.edges, adj=self.adj)
        mvt = engine.build_mvt(task, impact, self.catalog)
        # si la tarea ya avanzó más allá de la fase de laboratorio, el lab pasó
        lab = engine.build_lab_results(task, mvt, force_pass=phase_index > 3)
        proto = engine.build_prototype(task, impact)
        # anillos completados si estamos en fase de despliegue
        rings_done = 0
        if phase_index >= 5:
            # crc32 en lugar de hash(): estable entre procesos, de modo que la
            # rehidratación parte siempre del mismo histórico de demo.
            rings_done = random.Random(zlib.crc32(tid.encode()) & 0xFFFF).randint(1, 3)
        # Los anillos ya desplegados se consideran pre-aprobados por el owner (histórico).
        ring_preapprovals = {}
        ring_exclusions = {}
        for i in range(rings_done):
            rn = engine.RING_DEFS[i][0]
            ring_preapprovals[rn] = {
                "required": "Human-Driven", "preapproved": True,
                "approver": task.get("owner", "owner@bank.example"),
                "ts": iso(NOW), "note": "Pre-aprobación histórica del despliegue."}
        deploy = engine.build_deployment(task, impact, rings_done,
                                         preapprovals=ring_preapprovals, exclusions=ring_exclusions)
        audit = engine.build_audit(task, impact, mvt, lab, proto, deploy)

        # estado por fase
        statuses = {}
        for j, pid in enumerate(engine.PHASE_IDS):
            if j < phase_index:
                statuses[pid] = "approved"
            elif j == phase_index:
                statuses[pid] = "awaiting_approval"
            else:
                statuses[pid] = "pending"

        logs = []
        for j in range(phase_index + 1):
            logs.extend(self._phase_logs(engine.PHASE_IDS[j], task, impact, mvt, lab, proto, deploy))

        self.pipelines[tid] = {
            "task_id": tid, "phase_index": phase_index,
            "statuses": statuses, "rings_done": rings_done,
            "rolled_back_rings": [],
            "ring_preapprovals": ring_preapprovals,
            "ring_exclusions": ring_exclusions,
            "rollback": {"status": "armed", "triggered": False},
            # Evidencia real de ejecución por anillo (pasos devueltos por el provider).
            "ring_evidence": {},
            "artifacts": {"impact": impact, "mvt": mvt, "lab": lab,
                          "prototype": proto, "deployment": deploy, "audit": audit},
            "logs": logs,
            # Punto de partida determinista del histórico de demo: la
            # rehidratación vuelve aquí antes de re-proyectar los jobs.
            "baseline": {
                "rings_done": rings_done,
                "task_status": task.get("status"),
                "vi_status": self.vulnerable_items[task["vulnerable_item_id"]]["status"],
            },
        }
        if phase_index >= 5 and rings_done >= len(engine.RING_DEFS):
            self.tasks[tid]["status"] = "remediated"

    # ------------------------------------------------------------------
    # Rehidratación del pipeline desde SQLite
    # ------------------------------------------------------------------
    def _reset_projection(self, tid: str) -> None:
        """Devuelve la proyección en memoria al histórico determinista de demo."""
        p = self.pipelines[tid]
        baseline = p["baseline"]
        t = self.tasks[tid]
        p["rings_done"] = baseline["rings_done"]
        p["rolled_back_rings"] = []
        p["ring_evidence"] = {}
        p["rollback"] = {"status": "armed", "triggered": False}
        t["status"] = baseline["task_status"]
        self.vulnerable_items[t["vulnerable_item_id"]]["status"] = baseline["vi_status"]

    def rehydrate_pipeline_state(self) -> int:
        """Reconstruye el estado funcional a partir de los jobs persistidos.

        Los jobs son la fuente de verdad: al arrancar, cada tarea vuelve a su
        línea base y se re-proyectan en orden cronólogico los patch jobs
        `succeeded` (anillos completados), los restore jobs `restored` (anillos
        revertidos), la evidencia, los eventos y el estado de la tarea y del
        Vulnerable Item. Es idempotente: ejecutarla dos veces da el mismo
        resultado, y no depende del flag de proyección del job.
        """
        replayed = 0
        for tid in self.repo.tasks_with_jobs():
            if tid not in self.pipelines:
                continue
            self._reset_projection(tid)
            for job in self.repo.list_jobs_for_task_chronological(tid):
                self._projected.discard(job.id)
                if job.terminal:
                    self._apply_job_outcome(tid, job, persist=False)
                    replayed += 1
            self._rebuild_deploy(tid)
        if replayed:
            log.info("pipeline rehidratado desde SQLite: %s jobs re-proyectados", replayed)
        return replayed

    # ------------------------------------------------------------------
    def _phase_logs(self, pid, task, impact, mvt, lab, proto, deploy):
        ts = iso(NOW)
        A = "Devin"
        SN = "ServiceNow"
        if pid == "detection":
            return [
                {"actor": SN, "phase": pid, "msg": f"Hallazgo {task['cve']} ingerido y normalizado; VI {task['vulnerable_item_id']} creado."},
                {"actor": SN, "phase": pid, "msg": f"Asociado a CI {task['ci_id']} ({task['ci_name']}); track {task['track']} asignado."},
                {"actor": A, "phase": pid, "msg": "Deduplicación y enriquecimiento de fuentes completados."},
            ]
        if pid == "prioritization":
            return [
                {"actor": A, "phase": pid, "msg": f"Análisis de contexto: CVSS {task_cvss(task,self)}, KEV/EPSS y exposición evaluados."},
                {"actor": A, "phase": pid, "msg": f"Reachability analysis del componente '{task['component']}' → {'ALCANZABLE en runtime' if task['exposed'] else 'no alcanzable directamente'}."},
                {"actor": SN, "phase": pid, "msg": f"Prioridad calculada: {task['priority'].upper()} (score {task['risk_score']}/100). Change type: {task['change_type']}."},
            ]
        if pid == "pre_implementation":
            return [
                {"actor": A, "phase": pid, "msg": f"Impact Graph construido: {impact['affected_count']} CIs, capas {', '.join(impact['affected_layers'])}."},
                {"actor": A, "phase": pid, "msg": f"Consulta al catálogo de tests (Git) → propuesto MVT con {len(mvt['selected'])} pruebas (confianza {mvt['confidence']}%)."},
                {"actor": A, "phase": pid, "msg": f"Excluidas {len(mvt['excluded'])} pruebas no aplicables con justificación."},
            ]
        if pid == "lab_testing":
            return [
                {"actor": A, "phase": pid, "msg": "Ejecutando MVT en laboratorio vía CI/CD y frameworks de test..."},
                {"actor": A, "phase": pid, "msg": f"Resultados: {lab['passed']}/{lab['total']} OK. Veredicto agregado: {lab['verdict'].upper()}."},
            ]
        if pid == "prototype":
            return [
                {"actor": A, "phase": pid, "msg": f"Aprovisionando lab ({proto['approach']}) con {len(proto['lab_blueprint'])} componentes vía {proto['provision_tool']}."},
                {"actor": A, "phase": pid, "msg": f"Parche aplicado y pruebas ejecutadas. Error rate {proto['metrics']['error_rate_pct']}%, p95 {proto['metrics']['p95_latency_ms']}ms."},
                {"actor": A, "phase": pid, "msg": f"Veredicto prototipo: {proto['verdict'].upper()}. Teardown: {proto['teardown']}."},
            ]
        if pid == "deployment":
            logs = [{"actor": SN, "phase": pid, "msg": f"Change Request {task['change_type']} autorizado. Estrategia: {deploy['strategy']} ({deploy['executor']})."}]
            if deploy.get("pr_url"):
                logs.append({"actor": A, "phase": pid, "msg": f"PR de remediación abierto: {deploy['pr_url']}"})
            for r in deploy["rings"]:
                if r["status"] == "completed":
                    logs.append({"actor": SN, "phase": pid, "msg": f"{r['label']}: {r['assets']} activos desplegados y validados → {r['result']}."})
                elif r["status"] == "in_progress":
                    logs.append({"actor": SN, "phase": pid, "msg": f"{r['label']}: despliegue en curso sobre {r['assets']} activos."})
            return logs
        return []

    # ------------------------------------------------------------------
    # API de lectura
    # ------------------------------------------------------------------
    def overview(self):
        tasks = list(self.tasks.values())
        by_priority = {}
        for t in tasks:
            by_priority[t["priority"]] = by_priority.get(t["priority"], 0) + 1
        by_phase = {}
        for p in self.pipelines.values():
            pid = engine.PHASE_IDS[p["phase_index"]]
            by_phase[pid] = by_phase.get(pid, 0) + 1
        journey_summaries = [self._journey_summary(t) for t in tasks]
        by_track = {"A": 0, "B": 0, "C": 0}
        for t in tasks:
            by_track[t["track"]] = by_track.get(t["track"], 0) + 1
        by_lane = {"critical": 0, "accelerated": 0, "standard": 0}
        for t in tasks:
            ln = t.get("lane", "standard")
            by_lane[ln] = by_lane.get(ln, 0) + 1
        by_criticality = {}
        for t in tasks:
            c = t.get("criticality", "medium")
            by_criticality[c] = by_criticality.get(c, 0) + 1
        remediated = sum(1 for t in tasks if t.get("status") == "remediated")
        kev = sum(1 for v in self.vulnerable_items.values() if v["kev"])
        # stats de despliegue / rollback (para el panel del dashboard)
        rings_deployed = sum(p["rings_done"] for p in self.pipelines.values())
        rollbacks = sum(1 for p in self.pipelines.values() if p["rollback"].get("triggered"))
        in_deployment = sum(1 for p in self.pipelines.values()
                            if engine.PHASE_IDS[p["phase_index"]] == "deployment")
        cmdb = self.cmdb_summary()
        return {
            "funnel": self._funnel(tasks),
            "kpis": {
                "open_findings": len(self.findings),
                "vulnerable_items": len(self.vulnerable_items),
                "remediation_tasks": len(tasks),
                "kev_count": kev,
                "remediated": remediated,
                "in_flight": len(tasks) - remediated,
                "cis": len(self.cis),
                "avg_risk": round(sum(t["risk_score"] for t in tasks) / len(tasks)),
            },
            "by_priority": by_priority,
            "by_phase": by_phase,
            "journey": journey.aggregate(journey_summaries),
            "by_track": by_track,
            "by_lane": by_lane,
            "by_criticality": by_criticality,
            "tracks": seed.TRACKS,
            "lanes": seed.LANE_META,
            "deployment": {
                "rings_deployed": rings_deployed,
                "rollbacks": rollbacks,
                "in_deployment": in_deployment,
            },
            "cmdb": cmdb,
            "sla": self._sla_overview(tasks),
        }

    def _funnel(self, tasks):
        """Embudo de curación derivado de los datos reales, de ruido a acción."""
        active = [t for t in tasks if t.get("status") != "remediated"]
        return [
            {"label": "Hallazgos de los escáneres", "value": len(self.findings)},
            {"label": "Activos afectados", "value": len({f["ci_id"] for f in self.findings})},
            {"label": "CVE distintas", "value": len({f["cve"] for f in self.findings})},
            {"label": "Vulnerable Items curados", "value": len(self.vulnerable_items)},
            {"label": "Remediation Tasks activas", "value": len(active)},
        ]

    def _journey_summary(self, task):
        """Proyección de las 8 fases del journey sobre el pipeline de la tarea."""
        summary = journey.summary(task, self.pipelines[task["id"]],
                                  sla_state(task.get("sla_due", "")))
        return {**summary, "task_id": task["id"], "cve": task["cve"],
                "title": task["title"], "ci_name": task["ci_name"],
                "lane": task.get("lane", "standard"), "priority": task["priority"],
                "risk_score": task["risk_score"]}

    def _sla_overview(self, tasks):
        active = [t for t in tasks if t.get("status") != "remediated"]
        states = [sla_state(t.get("sla_due", "")) for t in active]
        overdue = sum(1 for s in states if s["overdue"])
        due_soon = sum(1 for s in states if s.get("due_soon"))
        return {
            "overdue": overdue,
            "due_soon": due_soon,
            "on_track": max(0, len(active) - overdue - due_soon),
            "at_risk": sum(1 for t in tasks if t["priority"] in ("critical", "high")),
        }

    def cmdb_tables(self):
        return seed.cmdb_manifest()

    # ------------------------------------------------------------------
    # CMDB (estandarizada, ~10k CIs) — resumen, listado paginado y subgrafo
    # ------------------------------------------------------------------
    def cmdb_summary(self):
        by_class, by_track, by_crit, by_env = {}, {}, {}, {}
        for c in self.cis:
            by_class[c["ci_class"]] = by_class.get(c["ci_class"], 0) + 1
            tr = c.get("track")
            if tr:
                by_track[tr] = by_track.get(tr, 0) + 1
            by_crit[c.get("criticality", "medium")] = by_crit.get(c.get("criticality", "medium"), 0) + 1
            by_env[c.get("environment", "-")] = by_env.get(c.get("environment", "-"), 0) + 1
        return {
            "total": len(self.cis),
            "edges": len(self.edges),
            "source": seed.CMDB_SOURCE,
            "by_class": by_class,
            "by_track": by_track,
            "by_criticality": by_crit,
            "by_environment": by_env,
        }

    def cmdb_cis(self, cls="all", track="all", crit="all", q="", limit=100, offset=0):
        res = []
        ql = q.lower().strip()
        for c in self.cis:
            if cls != "all" and c["ci_class"] != cls:
                continue
            if track != "all" and c.get("track") != track:
                continue
            if crit != "all" and c.get("criticality") != crit:
                continue
            if ql and ql not in c["name"].lower() and ql not in c["id"].lower():
                continue
            res.append(c)
        return {"total": len(res), "items": res[offset:offset + limit]}

    def cmdb_ci_raw(self, ci_id):
        """Contrato de datos: el CI normalizado + su registro nativo de ServiceNow."""
        ci = self.ci_by_id.get(ci_id)
        if not ci:
            return None
        record = seed.servicenow_record(ci)
        return {
            "ci_id": ci_id,
            "table": record["sys_class_name"],
            "endpoint": f"GET /api/now/table/{record['sys_class_name']}/{record['sys_id']}?sysparm_display_value=all",
            "source": seed.CMDB_SOURCE,
            "servicenow_record": record,
            "normalized": ci,
            "field_map": seed.CMDB_FIELD_MAP,
        }

    def cmdb_graph(self, service_id):
        """Subgrafo (blast radius) de un servicio, calculado en servidor."""
        if service_id not in self.ci_by_id:
            return {"nodes": [], "edges": []}
        seen = {service_id}
        frontier = [service_id]
        for _ in range(4):
            nxt = []
            for cid in frontier:
                for neighbor, _e in self.adj.get(cid, []):
                    if neighbor not in seen and len(seen) < 120:
                        seen.add(neighbor)
                        nxt.append(neighbor)
            frontier = nxt
        nodes = [{**self.ci_by_id[i], "is_root": i == service_id} for i in seen if i in self.ci_by_id]
        edges = [e for e in self.edges if e["source"] in seen and e["target"] in seen]
        return {"nodes": nodes, "edges": edges}

    def list_tasks(self):
        out = []
        for tid, t in self.tasks.items():
            p = self.pipelines[tid]
            out.append({
                **t,
                "phase": engine.PHASE_IDS[p["phase_index"]],
                "phase_label": engine.PHASES[p["phase_index"]][1],
                "phase_index": p["phase_index"],
                "phase_status": p["statuses"][engine.PHASE_IDS[p["phase_index"]]],
                "affected_count": p["artifacts"]["impact"]["affected_count"],
                "kev": self.vulnerable_items[t["vulnerable_item_id"]]["kev"],
                "sla": sla_state(t.get("sla_due", "")),
                "journey": self._journey_summary(t),
            })
        return sorted(out, key=lambda x: -x["risk_score"])

    def task_detail(self, tid, reconcile: bool = True):
        if tid not in self.tasks:
            return None
        if reconcile:
            # Reconciliación perezosa: el estado real lo dicta el provider.
            active = self.repo.active_job_for_task(tid)
            if active is not None:
                self.reconcile_job(active)
        t = self.tasks[tid]
        p = self.pipelines[tid]
        vi = self.vulnerable_items[t["vulnerable_item_id"]]
        lane = t.get("lane", "standard")
        active_job = self.repo.active_job_for_task(tid)
        phases = []
        for j, (pid, label) in enumerate(engine.PHASES):
            phases.append({"id": pid, "label": label, "index": j,
                           "status": p["statuses"][pid],
                           "automation": engine.phase_automation(lane, j)})
        return {
            "task": t, "vulnerable_item": vi,
            "phase_index": p["phase_index"],
            "phases": phases,
            "lane": lane,
            "journey": {
                **self._journey_summary(t),
                "phases": journey.phase_states(t, p),
                "rings": journey.ring_states(p),
            },
            "lane_meta": seed.LANE_META.get(lane, seed.LANE_META["standard"]),
            "lane_flow": engine.lane_flow(lane),
            "artifacts": p["artifacts"],
            "logs": p["logs"],
            "rings_done": p["rings_done"],
            "sla": sla_state(t.get("sla_due", "")),
            "active_job": active_job.as_dict() if active_job else None,
            "jobs": [j.as_dict() for j in self.repo.list_jobs_for_task(tid, limit=20)],
            "execution": {
                "patch_provider": self.patch_provider.name,
                "restore_provider": self.restore_provider.name,
                "dry_run": self.settings.effective_dry_run(self.patch_provider.name),
                "poll_interval_seconds": self.settings.job_poll_interval_seconds,
                "mode": self.settings.execution_mode(),
                "strict_policy": self.settings.real_aws_execution(),
            },
        }

    # ------------------------------------------------------------------
    # API de acciones (HITL / avance)
    # ------------------------------------------------------------------
    def approve_phase(self, tid, idempotency_key: str | None = None):
        """Aprobación humana de la fase actual.

        Fases 1-5: síncrono (sin cambios funcionales).
        Fase de despliegue: crea un job de parcheo y devuelve el detalle con el
        job activo; el anillo NO avanza hasta que el provider reporte éxito.
        """
        if tid not in self.pipelines:
            return None
        p = self.pipelines[tid]
        idx = p["phase_index"]
        pid = engine.PHASE_IDS[idx]
        t = self.tasks[tid]

        if pid == "deployment":
            self.start_ring_patch_job(tid, idempotency_key)
            return self.task_detail(tid)

        # Resto de fases: marcar aprobada y pasar a la siguiente
        p["statuses"][pid] = "approved"
        self._log(tid, {"actor": "Owner (HITL)", "phase": pid, "msg": f"Fase '{engine.PHASES[idx][1]}' aprobada."})
        if idx + 1 < len(engine.PHASE_IDS):
            p["phase_index"] = idx + 1
            nxt = engine.PHASE_IDS[idx + 1]
            p["statuses"][nxt] = "awaiting_approval"
            # el agente "trabaja" la nueva fase (logs)
            a = p["artifacts"]
            for l in self._phase_logs(nxt, t, a["impact"], a["mvt"], a["lab"], a["prototype"], a["deployment"]):
                self._log(tid, l)
        return self.task_detail(tid)

    # ------------------------------------------------------------------
    def preapprove_ring(self, tid, ring_no, approver=None, note=None):
        """Revisión y pre-aprobación Human-Driven del informe pre-anillo."""
        if tid not in self.pipelines:
            return None
        p = self.pipelines[tid]
        t = self.tasks[tid]
        approver = approver or t.get("owner", "owner@bank.example")
        p.setdefault("ring_preapprovals", {})[ring_no] = {
            "required": "Human-Driven", "preapproved": True,
            "approver": approver, "ts": iso(NOW),
            "note": note or "Informe pre-anillo revisado y verificado.",
        }
        excl = p.get("ring_exclusions", {}).get(ring_no) or []
        self._log(tid, {"actor": "Owner (HITL · Human-Driven)", "phase": "deployment",
                        "msg": f"[Auditoría] Informe pre-anillo del anillo {ring_no} verificado y PRE-APROBADO por {approver}"
                               + (f" · {len(excl)} activo(s) excluido(s) de la selección." if excl else ".")})
        self._rebuild_deploy(tid)
        return self.task_detail(tid)

    def update_ring_assets(self, tid, ring_no, excluded_ids):
        """Edición de la selección de activos de un anillo antes de aprobar."""
        if tid not in self.pipelines:
            return None
        p = self.pipelines[tid]
        p.setdefault("ring_exclusions", {})[ring_no] = list(excluded_ids or [])
        # Editar la selección invalida la pre-aprobación previa (debe re-verificarse).
        if ring_no in p.get("ring_preapprovals", {}):
            p["ring_preapprovals"].pop(ring_no, None)
        self._log(tid, {"actor": "Owner (HITL)", "phase": "deployment",
                        "msg": f"Selección de activos del anillo {ring_no} editada: {len(excluded_ids or [])} excluido(s). Requiere re-verificación."})
        self._rebuild_deploy(tid)
        return self.task_detail(tid)

    # ------------------------------------------------------------------
    def _rebuild_deploy(self, tid):
        """Reconstruye el despliegue preservando estado de rollback y auditoría."""
        p = self.pipelines[tid]
        t = self.tasks[tid]
        a = p["artifacts"]
        deploy = engine.build_deployment(
            t, a["impact"], p["rings_done"],
            rollback=p["rollback"], rolled_back_rings=p["rolled_back_rings"],
            preapprovals=p.get("ring_preapprovals"), exclusions=p.get("ring_exclusions"),
            evidence=p.get("ring_evidence"), active_jobs=self._jobs_by_ring(tid))
        a["deployment"] = deploy
        a["audit"] = engine.build_audit(t, a["impact"], a["mvt"], a["lab"], a["prototype"], deploy)
        return deploy

    def rollback(self, tid, reason=None, trigger="manual", idempotency_key: str | None = None):
        """Rollback del último anillo desplegado a través de un job de restauración.

        El progreso (`rings_done`) sólo retrocede cuando la restauración termina
        con éxito; en dry-run no se retrocede nada.
        """
        if tid not in self.pipelines:
            return None
        p = self.pipelines[tid]
        if p["rings_done"] <= 0:
            return self.task_detail(tid)
        self.start_restore_job(tid, reason=reason, trigger=trigger,
                               idempotency_key=idempotency_key)
        return self.task_detail(tid)

    def _apply_rollback(self, tid, job: PatchJob):
        """Efecto del rollback una vez el provider confirma la restauración."""
        p = self.pipelines[tid]
        t = self.tasks[tid]
        payload = job.request_payload
        ring_no = job.ring_number
        trigger = payload.get("trigger", "manual")
        reason = payload.get("reason", "Rollback solicitado por el owner")
        plan = p["artifacts"]["deployment"]["rollback_plan"]
        self._log(tid, {"actor": "ServiceNow", "phase": "deployment",
                        "msg": f"⟲ ROLLBACK ({trigger}) del anillo {ring_no}. Motivo: {reason}. RTO objetivo {plan['rto_minutes']} min."})
        for s in job.steps() or plan["steps"]:
            self._log(tid, {"actor": s.get("actor", "Devin"), "phase": "deployment",
                            "msg": f"$ {s.get('command')} → {s.get('output') or s.get('desc')}"})
        if ring_no not in p["rolled_back_rings"]:
            p["rolled_back_rings"].append(ring_no)
        p["rings_done"] = max(0, p["rings_done"] - 1)
        p["ring_evidence"].pop(ring_no, None)
        p["rollback"] = {
            "status": "completed", "triggered": True, "trigger_type": trigger,
            "reason": reason, "ring": ring_no, "ts": iso(NOW),
            "restored_version": payload.get("target_version") or plan["target_version"],
            "verdict": "healthy tras rollback",
            "job_id": job.id, "provider": job.provider,
        }
        vi = self.vulnerable_items[t["vulnerable_item_id"]]
        vi["status"] = "in_progress"
        if t.get("status") == "remediated":
            t["status"] = "in_flight"
        self._rebuild_deploy(tid)
        self._log(tid, {"actor": "Devin", "phase": "deployment",
                        "msg": f"Rollback completado. Versión restaurada: {p['rollback']['restored_version']}. "
                               f"Servicio healthy; anillo {ring_no} marcado como revertido para re-análisis."})

    def simulate_incident(self, tid):
        """Simula una anomalía post-despliegue que dispara rollback automático."""
        if tid not in self.pipelines:
            return None
        p = self.pipelines[tid]
        if p["rings_done"] <= 0:
            return self.task_detail(tid)
        ring_no = engine.RING_DEFS[p["rings_done"] - 1][0]
        self._log(tid, {"actor": "ServiceNow", "phase": "deployment",
                        "msg": f"⚠ Anomalía detectada en anillo {ring_no}: error rate 4.7% (SLO 1%), p95 1.8s. Post-check FAILED → disparando rollback automático."})
        return self.rollback(tid, reason="Post-check falló: error rate 4.7% > SLO, p95 1.8s", trigger="auto")

    # ==================================================================
    # Jobs de ejecución (parcheo / restauración)
    # ==================================================================
    def _jobs_by_ring(self, tid) -> dict:
        """Job más reciente por anillo, para adjuntarlo al artefacto de deployment."""
        by_ring: dict[int, dict] = {}
        for job in self.repo.list_jobs_for_task(tid, limit=20):
            by_ring.setdefault(job.ring_number, job.as_dict())
        return by_ring

    def _ring_assets(self, tid, ring_no) -> list[dict]:
        deploy = self.pipelines[tid]["artifacts"]["deployment"]
        for ring in deploy["rings"]:
            if ring["ring"] == ring_no:
                return [a for a in ring["plan"]["assets"] if not a.get("excluded")]
        return []

    def _asset_target(self, asset: dict) -> Target:
        """Objetivo de un activo de la CMDB.

        Los Instance ID no se fijan en ninguna variable de entorno ni en la CMDB:
        el activo del laboratorio se resuelve dinámicamente por tags en AWS, y el
        resto de activos son sintéticos (mock) y no tienen instancia real.
        """
        logical_id = asset.get("logical_target_id") or asset["id"]
        instance_id = asset.get("instance_id")
        region = asset.get("region")
        if logical_id == self.settings.lab_logical_id:
            try:
                instance = self._resolve_lab_instance(logical_id)
            except LabResolutionError as exc:
                raise ValidationError(exc.message, code=exc.code) from exc
            # El entorno del laboratorio es el del activo real (tag msr-environment),
            # no el del anillo («Laboratorio»), que es el nombre de una etapa del
            # despliegue y nunca coincide con la allowlist de entornos.
            return instance.as_target()
        return Target(
            logical_target_id=logical_id, instance_id=instance_id,
            account_id=asset.get("account_id"), region=region,
            tags=dict(asset.get("tags") or {}),
            operating_system=asset.get("os"), environment=asset.get("environment"),
            ssm_managed=bool(asset.get("ssm_managed")), name=asset.get("name"))

    def _resolve_ring_targets(self, tid, ring_no) -> list[Target]:
        """Todos los activos seleccionados del anillo, en orden de dependencia."""
        assets = self._ring_assets(tid, ring_no)
        if not assets:
            raise ValidationError(
                f"El anillo {ring_no} no tiene activos seleccionados para desplegar.",
                code="NO_TARGET_SELECTED")
        return [self._asset_target(a) for a in assets]

    def _resolve_target(self, tid, ring_no) -> Target:
        """Objetivo único del anillo (mock multiactivo): CI raíz o el primero."""
        assets = self._ring_assets(tid, ring_no)
        if not assets:
            raise ValidationError(
                f"El anillo {ring_no} no tiene activos seleccionados para desplegar.",
                code="NO_TARGET_SELECTED")
        return self._asset_target(next((a for a in assets if a.get("is_root")), assets[0]))

    def _aws_single_target(self, tid, ring_no, track: str) -> Target:
        """Con provider AWS un job representa exactamente UNA instancia real."""
        if (track or "") != "A":
            raise ValidationError(
                f"El track {track or 'sin valor'} no se ejecuta en AWS Systems Manager: "
                "sólo el track A (infraestructura) está soportado en esta fase.",
                code="UNSUPPORTED_REMEDIATION_TRACK")
        targets = self._resolve_ring_targets(tid, ring_no)
        real = [t for t in targets
                if t.instance_id and INSTANCE_ID_RE.match(t.instance_id)]
        if len(real) != 1:
            raise ValidationError(
                f"El anillo {ring_no} resuelve {len(real)} instancias EC2 reales de "
                f"{len(targets)} activos y el provider AWS admite exactamente una en esta fase.",
                code="RING_TARGET_COUNT_UNSUPPORTED")
        return real[0]

    # ------------------------------------------------------------------
    def _provider_error(self, exc: ProviderError):
        if exc.code in _UNAVAILABLE_CODES:
            return DependencyUnavailableError(exc.message, code=exc.code)
        if exc.code.startswith("TARGET_"):
            return TargetNotAllowedError(exc.message, code=exc.code)
        return ValidationError(exc.message, code=exc.code)

    def _fail_job(self, job: PatchJob, code: str, message: str) -> PatchJob:
        target_state = (JobState.RESTORE_FAILED if job.job_type is not JobType.PATCH
                        else JobState.FAILED)
        job.transition_to(target_state, error_code=code, error_message=sanitize_text(message))
        self.repo.append_event(job.id, job.state, f"{code}: {sanitize_text(message, 500)}")
        # Fallo controlado: el laboratorio queda libre para el siguiente intento.
        self._release_lab_lock_for_job(job)
        return self.repo.save_job(job)

    # --- lock de operación del laboratorio ------------------------------
    def _lab_id_for_task(self, tid: str) -> str:
        """Laboratorio asociado a la tarea, si la tarea es la del laboratorio."""
        return str((self.tasks.get(tid) or {}).get("logical_lab_id") or "")

    def _take_lab_lock(self, lab_id: str, owner: str, operation: str, reason: str) -> bool:
        """Toma el lock del laboratorio. True si esta operación debe liberarlo.

        Devuelve False cuando el lock ya es del mismo dueño: la reconciliación
        propaga su `correlation_id` al reset que lanza, así que el reset reentra
        sin apropiarse de la liberación.
        """
        if not lab_id:
            return False
        held = self.lab_locks.state(lab_id) or {}
        if held.get("owner") == owner:
            return False
        self.lab_locks.acquire_or_conflict(lab_id, owner, operation, reason=reason)
        return True

    def _release_lab_lock_for_job(self, job: PatchJob, *, force: bool = False) -> None:
        """Libera el lock del laboratorio cuando su job mutativo ya es terminal.

        `force` cubre el caso en que el job ni siquiera llega a crearse: el lock
        tomado un instante antes no puede quedarse retenido.
        """
        lock = job.request_payload.get("lab_lock")
        if not isinstance(lock, dict) or lock.get("released"):
            return
        if not (force or job.terminal):
            return
        lab_id = str(lock.get("lab_id") or "")
        owner = str(lock.get("owner") or "")
        if not lab_id or not owner:
            return
        self.lab_locks.release(lab_id, owner)
        job.request_payload["lab_lock"] = {**lock, "released": True}

    def _replay(self, idempotency_key: str | None) -> PatchJob | None:
        """Idempotencia: la misma clave devuelve el job original, nunca uno nuevo."""
        if not idempotency_key:
            return None
        job = self.repo.get_job_by_idempotency_key(idempotency_key)
        return self.reconcile_job(job) if job is not None else None

    # ------------------------------------------------------------------
    def start_ring_patch_job(self, tid, idempotency_key: str | None = None) -> PatchJob:
        """Crea (y arranca) el job de parcheo del siguiente anillo del despliegue."""
        if tid not in self.pipelines:
            raise NotFoundError(f"La tarea {tid} no existe.")
        replay = self._replay(idempotency_key)
        if replay is not None:
            return replay
        p = self.pipelines[tid]
        t = self.tasks[tid]
        if engine.PHASE_IDS[p["phase_index"]] != "deployment":
            raise ValidationError("La tarea no está en la fase de despliegue.",
                                  code="PHASE_NOT_DEPLOYMENT")
        if p["rings_done"] >= len(engine.RING_DEFS):
            raise ValidationError("El despliegue ya ha completado todos los anillos.",
                                  code="DEPLOYMENT_COMPLETED")
        ring_no = engine.RING_DEFS[p["rings_done"]][0]
        preapproval = p.get("ring_preapprovals", {}).get(ring_no)
        if not (preapproval and preapproval.get("preapproved")):
            self._log(tid, {"actor": "ServiceNow", "phase": "deployment",
                            "msg": f"Despliegue del anillo {ring_no} bloqueado: requiere revisión y "
                                   "pre-aprobación Human-Driven del informe pre-anillo."})
            raise ValidationError(
                f"El anillo {ring_no} requiere pre-aprobación Human-Driven antes de desplegarse.",
                code="RING_NOT_PREAPPROVED")

        active = self.repo.active_job_for_task(tid)
        if active is not None:
            active = self.reconcile_job(active)
            if active.active:
                raise ConflictError(
                    f"La tarea {tid} ya tiene un job activo ({active.id}, estado {active.state.value}).",
                    correlation_id=active.correlation_id)

        deploy = p["artifacts"]["deployment"]
        ring = next(r for r in deploy["rings"] if r["ring"] == ring_no)
        track = t.get("track", "A")
        aws = self.patch_provider.name == PROVIDER_AWS_AUTOMATION
        if aws:
            target = self._aws_single_target(tid, ring_no, track)
            assets_count = 1
        else:
            target = self._resolve_target(tid, ring_no)
            assets_count = max(1, ring["assets"])
        busy = self.repo.active_job_for_target(target.logical_target_id)
        if busy is not None and busy.active:
            raise ConflictError(
                f"El objetivo {target.logical_target_id} ya tiene un job activo ({busy.id}).",
                correlation_id=busy.correlation_id)

        from_version = engine._prev_version(t)
        request_job_id = new_job_id()
        dry_run = self.settings.effective_dry_run(self.patch_provider.name)
        # En una ejecución AWS real la versión corregida la determina el runbook:
        # no se calcula una versión ficticia como evidencia.
        to_version = "" if (aws and not dry_run) else engine._fixed_version(from_version)
        request = PatchRequest(
            job_id=request_job_id, task_id=tid, ring_number=ring_no,
            targets=(target,),
            spec=PatchSpec(component=t.get("component", t["ci_name"]),
                           from_version=from_version, to_version=to_version,
                           cve=t.get("cve"), track=track),
            dry_run=dry_run, ring_label=ring["label"], executor=deploy["executor"],
            assets_count=assets_count, task_snapshot=_task_snapshot(t))
        job = PatchJob(
            id=request_job_id, job_type=JobType.PATCH, task_id=tid, ring_number=ring_no,
            provider=self.patch_provider.name, dry_run=dry_run, targets=(target,),
            idempotency_key=idempotency_key or f"auto:{request_job_id}",
            request_payload=_patch_request_payload(request))
        job.request_payload["correlation_id"] = job.correlation_id
        # Parcheo del laboratorio: no puede empezar mientras un reset o una
        # reconciliación tengan el laboratorio tomado (409 si lo tienen).
        lab_id = self._lab_id_for_task(tid)
        if self._take_lab_lock(lab_id, job.correlation_id, LOCK_OPERATION_PATCH,
                               f"patch:{tid}:ring-{ring_no}"):
            job.request_payload["lab_lock"] = {"lab_id": lab_id, "owner": job.correlation_id,
                                               "operation": LOCK_OPERATION_PATCH}
        request = _patch_request_from_payload(job.request_payload)

        try:
            job, created = self.repo.create_job(job, scope="approve")
        except TargetBusyError as exc:
            self._release_lab_lock_for_job(job, force=True)
            raise ConflictError(
                f"El objetivo {exc.logical_target_id} ya tiene un job activo.") from exc
        if not created:
            self._release_lab_lock_for_job(job, force=True)
            return job  # idempotencia: misma clave → mismo job

        self.repo.append_event(job.id, job.state,
                               f"Job creado para el anillo {ring_no} ({ring['label']}).")
        self._log(tid, {"actor": "Owner (HITL)", "phase": "deployment",
                        "msg": f"[HITL] Aprobado despliegue de {ring['label']} ({assets_count} activos). "
                               f"Job {job.id} ({job.provider}"
                               + (", dry-run)" if dry_run else ")") + " creado."})

        job.transition_to(JobState.VALIDATING)
        self.repo.save_job(job)
        try:
            policy = self.patch_provider.validate_target(request)
        except ProviderError as exc:
            self._fail_job(job, exc.code, exc.message)
            raise self._provider_error(exc) from exc
        job.result_payload["policy"] = policy.as_dict()
        if not policy.allowed:
            self._fail_job(job, policy.error_code or "TARGET_NOT_ALLOWED", policy.message)
            self._log(tid, {"actor": "msr-platform", "phase": "deployment",
                            "msg": f"Objetivo rechazado por política: {policy.message}"})
            raise TargetNotAllowedError(policy.message,
                                        code=policy.error_code or "TARGET_NOT_ALLOWED",
                                        correlation_id=job.correlation_id)

        try:
            execution = self.patch_provider.start(request, job.idempotency_key)
        except ProviderError as exc:
            self._fail_job(job, exc.code, exc.message)
            raise self._provider_error(exc) from exc

        job.provider_reference = execution.provider_reference
        job.dry_run = execution.dry_run
        self._absorb_execution(job, execution)
        self.repo.save_job(job)
        if job.terminal:
            self._apply_job_outcome(tid, job)
        return job

    # ------------------------------------------------------------------
    def start_restore_job(self, tid, reason=None, trigger="manual",
                          idempotency_key: str | None = None,
                          restore_kind: str = "rollback") -> PatchJob:
        """Crea el job de restauración del último anillo desplegado."""
        if tid not in self.pipelines:
            raise NotFoundError(f"La tarea {tid} no existe.")
        replay = self._replay(idempotency_key)
        if replay is not None:
            return replay
        p = self.pipelines[tid]
        t = self.tasks[tid]
        if p["rings_done"] <= 0:
            raise ValidationError("No hay ningún anillo desplegado que restaurar.",
                                  code="NOTHING_TO_RESTORE")
        active = self.repo.active_job_for_task(tid)
        if active is not None:
            active = self.reconcile_job(active)
            if active.active:
                raise ConflictError(
                    f"La tarea {tid} ya tiene un job activo ({active.id}).",
                    correlation_id=active.correlation_id)

        ring_no = engine.RING_DEFS[p["rings_done"] - 1][0]
        plan = p["artifacts"]["deployment"]["rollback_plan"]
        reason = reason or ("Fallo de post-checks / breach de health-check" if trigger == "auto"
                           else "Rollback solicitado por el owner")
        if self.restore_provider.name == PROVIDER_AWS_AUTOMATION:
            target = self._aws_single_target(tid, ring_no, t.get("track", "A"))
        else:
            target = self._resolve_target(tid, ring_no)
        job_id = new_job_id()
        dry_run = self.settings.effective_dry_run(self.restore_provider.name)
        job_type = JobType.RESET_LAB if restore_kind == "reset_lab" else JobType.ROLLBACK
        request = RestoreRequest(
            job_id=job_id, task_id=tid, ring_number=ring_no, targets=(target,),
            reason=reason, target_version=plan["target_version"],
            snapshot_ref=plan.get("snapshot_ref"), dry_run=dry_run,
            restore_kind=restore_kind, task_snapshot=_task_snapshot(t))
        job = PatchJob(
            id=job_id, job_type=job_type, task_id=tid, ring_number=ring_no,
            provider=self.restore_provider.name, dry_run=dry_run, targets=(target,),
            state=JobState.RESTORE_QUEUED,
            idempotency_key=idempotency_key or f"auto:{job_id}",
            request_payload=_restore_request_payload(request))
        job.request_payload.update({"trigger": trigger, "correlation_id": job.correlation_id})
        request = _restore_request_from_payload(job.request_payload)

        try:
            job, created = self.repo.create_job(job, scope="rollback")
        except TargetBusyError as exc:
            raise ConflictError(
                f"El objetivo {exc.logical_target_id} ya tiene un job activo.") from exc
        if not created:
            return job

        self.repo.append_event(job.id, job.state,
                               f"Job de restauración creado para el anillo {ring_no}.")
        job.transition_to(JobState.VALIDATING)
        self.repo.save_job(job)
        try:
            policy = self.restore_provider.validate_target(request)
            job.result_payload["policy"] = policy.as_dict()
            if not policy.allowed:
                self._fail_job(job, policy.error_code or "TARGET_NOT_ALLOWED", policy.message)
                raise TargetNotAllowedError(policy.message,
                                            code=policy.error_code or "TARGET_NOT_ALLOWED",
                                            correlation_id=job.correlation_id)
            execution = self.restore_provider.start(request, job.idempotency_key)
        except ProviderError as exc:
            self._fail_job(job, exc.code, exc.message)
            raise self._provider_error(exc) from exc

        job.provider_reference = execution.provider_reference
        job.dry_run = execution.dry_run
        self._absorb_execution(job, execution)
        self.repo.save_job(job)
        if job.terminal:
            self._apply_job_outcome(tid, job)
        else:
            job = self.reconcile_job(job)
        return job

    # ------------------------------------------------------------------
    def _absorb_execution(self, job: PatchJob, execution) -> PatchJob:
        """Copia el resultado del provider al job y ajusta el estado interno."""
        if execution.steps:
            job.set_steps(execution.steps)
        job.result_payload.update({
            "provider_detail": sanitize_text(execution.detail, 500),
            "raw_status": execution.raw_status,
        })
        for key in ("from_version", "to_version", "restored_version", "new_instance_id"):
            value = getattr(execution, key, None)
            if value:
                job.result_payload[key] = value
        if execution.report:
            # Outputs declarados del runbook: evidencia auditable del resultado.
            job.result_payload["report"] = dict(execution.report)
        warning_code = execution.warning_code
        if warning_code:
            message = (f"[{warning_code}] "
                       f"{sanitize_text(execution.warning_message, 500)}")
            job.result_payload["warning"] = {
                "code": warning_code,
                "message": sanitize_text(execution.warning_message, 500)}
            if not self.repo.has_event(job.id, message):
                self.repo.append_event(job.id, job.state, message)
        target_state = state_for_execution(execution.status, job.job_type)
        if execution.error_code:
            job.error_code = execution.error_code
            job.error_message = sanitize_text(execution.error_message, self.settings.max_output_chars)
        if target_state != job.state:
            job.transition_to(target_state, error_code=execution.error_code,
                              error_message=execution.error_message)
            self.repo.append_event(job.id, job.state,
                                   sanitize_text(execution.detail, 500) or f"Estado {job.state.value}.")
        return job

    def _provider_for(self, job: PatchJob):
        return self.patch_provider if job.job_type is JobType.PATCH else self.restore_provider

    def _request_for(self, job: PatchJob):
        if job.job_type is JobType.PATCH:
            return _patch_request_from_payload(job.request_payload)
        return _restore_request_from_payload(job.request_payload)

    def _job_lock(self, job_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._job_locks.setdefault(job_id, threading.Lock())

    def reconcile_job(self, job: PatchJob) -> PatchJob:
        """Consulta al provider y aplica el resultado. Idempotente y sin duplicar logs.

        Un mismo job nunca se consulta en paralelo (frontend + reconciliador):
        si otro hilo lo está reconciliando, se devuelve el estado conocido.
        """
        if job.terminal or not job.provider_reference:
            return job
        lock = self._job_lock(job.id)
        if not lock.acquire(blocking=False):
            return job
        try:
            return self._reconcile_locked(job)
        finally:
            lock.release()

    def _reconcile_locked(self, job: PatchJob) -> PatchJob:
        elapsed = (utcnow() - job.created_at).total_seconds()
        if elapsed > self.settings.job_timeout_seconds or job.unconfirmed:
            return self._handle_timeout(job)
        execution = self._poll_provider(job)
        if execution is None:
            return job
        self._absorb_execution(job, execution)
        self.repo.save_job(job)
        if job.terminal:
            self._apply_job_outcome(job.task_id, job)
        return job

    def _poll_provider(self, job: PatchJob):
        """Consulta al provider; None si la consulta no pudo completarse."""
        try:
            return self._provider_for(job).poll(job.provider_reference or "",
                                                self._request_for(job))
        except ProviderError as exc:
            message = f"No se pudo reconciliar el job: {exc.code}"
            if not self.repo.has_event(job.id, message):
                self.repo.append_event(job.id, job.state, message)
            return None

    def _mark_unconfirmed(self, job: PatchJob, state: JobState, code: str,
                          message: str) -> PatchJob:
        """Estado no terminal: el lock del objetivo se mantiene deliberadamente."""
        if job.state is not state:
            job.transition_to(state, error_code=code, error_message=message)
            self.repo.append_event(job.id, job.state, message)
            self.repo.save_job(job)
        return job

    def _handle_timeout(self, job: PatchJob) -> PatchJob:
        """Timeout local: nunca es por sí mismo un estado terminal en AWS.

        Sin ejecución remota viva (mock o dry-run) el job caduca. Con ejecución
        remota se vuelve a consultar el estado, se solicita la parada y el job
        queda en un estado no confirmado que mantiene el objetivo bloqueado
        hasta que AWS confirme un estado terminal (o hasta una reconciliación
        manual administrativa).
        """
        remote = job.provider != PROVIDER_MOCK and not job.dry_run
        if not remote:
            job.transition_to(JobState.TIMED_OUT, error_code="JOB_TIMED_OUT",
                              error_message="El job excedió MSR_JOB_TIMEOUT_SECONDS.")
            self.repo.append_event(job.id, job.state, "Job caducado por timeout.")
            self.repo.save_job(job)
            self._apply_job_outcome(job.task_id, job)
            return job

        self._mark_unconfirmed(
            job, JobState.TIMEOUT_PENDING_CONFIRMATION, "JOB_TIMEOUT_PENDING_CONFIRMATION",
            "Timeout local alcanzado: la ejecución remota puede seguir activa, "
            "el objetivo permanece bloqueado hasta confirmar su estado.")
        execution = self._poll_provider(job)
        if execution is None:
            return self._mark_unconfirmed(
                job, JobState.REMOTE_STATUS_UNKNOWN, "REMOTE_STATUS_UNKNOWN",
                "No se pudo obtener el estado remoto de la ejecución: el objetivo "
                "sigue ocupado y requiere reconciliación manual.")
        if is_terminal(state_for_execution(execution.status, job.job_type)):
            self._absorb_execution(job, execution)
            self.repo.save_job(job)
            self._apply_job_outcome(job.task_id, job)
            return job
        if job.state is JobState.STOP_REQUESTED:
            return job
        try:
            self._provider_for(job).cancel(job.provider_reference or "",
                                           self._request_for(job))
        except ProviderError as exc:
            return self._mark_unconfirmed(
                job, JobState.REMOTE_STATUS_UNKNOWN, exc.code,
                f"No se pudo solicitar la parada de la ejecución remota: {exc.code}. "
                "El objetivo sigue ocupado.")
        return self._mark_unconfirmed(
            job, JobState.STOP_REQUESTED, "STOP_REQUESTED",
            "Parada solicitada al proveedor tras el timeout local: el job no se "
            "marca como cancelado hasta que la ejecución remota lo confirme.")

    # ------------------------------------------------------------------
    def admin_resolve_job(self, job_id: str, state: str, note: str,
                          actor: str = "admin") -> PatchJob:
        """Reconciliación manual de un job sin estado remoto confirmado.

        Sólo cierra jobs en estado no confirmado y deja evento de auditoría; no
        puede declarar un éxito que AWS no haya confirmado.
        """
        job = self.repo.get_job(job_id, with_events=True)
        if job is None:
            raise NotFoundError(f"El job {job_id} no existe.")
        if not job.unconfirmed:
            raise ValidationError(
                f"El job {job_id} no está en un estado no confirmado ({job.state.value}).",
                code="JOB_NOT_UNCONFIRMED")
        allowed = {s.value for s in ADMIN_RESOLVABLE_STATES}
        if state not in allowed:
            raise ValidationError(
                f"Estado no permitido para reconciliación manual: {state}. "
                f"Permitidos: {', '.join(sorted(allowed))}.",
                code="ADMIN_STATE_NOT_ALLOWED")
        target_state = JobState(state)
        if job.job_type is not JobType.PATCH and target_state is JobState.FAILED:
            target_state = JobState.RESTORE_FAILED
        detail = sanitize_text(note, 500) or "sin detalle"
        job.transition_to(target_state, error_code="ADMIN_RECONCILED", error_message=detail)
        self.repo.append_event(
            job.id, job.state,
            f"[Auditoría] Reconciliación manual a {job.state.value} por {actor}: {detail}",
            actor=actor)
        self.repo.save_job(job)
        self._apply_job_outcome(job.task_id, job)
        return job

    def reconcile_active_jobs(self) -> int:
        """Reconciliación de todos los jobs activos persistidos (reconciliador)."""
        reconciled = 0
        for job in self.repo.list_active_jobs():
            self.reconcile_job(job)
            reconciled += 1
        return reconciled

    # ------------------------------------------------------------------
    def _apply_job_outcome(self, tid, job: PatchJob, *, persist: bool = True) -> None:
        """Proyecta el resultado de un job terminal sobre el estado en memoria.

        El resultado persistido del job y su proyección son cosas distintas: la
        proyección se controla en memoria (`_projected`), de modo que reiniciar
        el backend puede volver a reconstruirla desde SQLite.
        """
        # El lock del laboratorio se libera con el estado terminal del job, no al
        # arrancarlo: la Automation sigue viva mientras el job está activo.
        self._release_lab_lock_for_job(job)
        if tid not in self.pipelines or job.id in self._projected:
            return
        self._projected.add(job.id)
        job.result_payload["outcome_applied"] = True
        p = self.pipelines[tid]
        t = self.tasks[tid]

        if job.state is JobState.DRY_RUN:
            self._log(tid, {"actor": "msr-platform", "phase": "deployment",
                            "msg": f"Dry-run completado (job {job.id}, provider {job.provider}): "
                                   f"no se ha aplicado ningún cambio y el anillo {job.ring_number} "
                                   "no avanza."})
        elif job.job_type is JobType.PATCH and job.state is JobState.SUCCEEDED:
            ring_no = job.ring_number
            p["rings_done"] = max(p["rings_done"], ring_no)
            # Sólo se declaran desplegados los objetivos realmente ejecutados.
            executed = [tg.instance_id or tg.logical_target_id for tg in job.targets]
            p["ring_evidence"][ring_no] = {
                "steps": job.steps(),
                "from_version": job.result_payload.get("from_version"),
                "to_version": job.result_payload.get("to_version"),
                "job_id": job.id, "provider": job.provider,
                "executed_assets": job.request_payload.get("assets_count") or len(executed),
                "executed_targets": executed,
            }
            deploy = self._rebuild_deploy(tid)
            ring = next(r for r in deploy["rings"] if r["ring"] == ring_no)
            for step in job.steps():
                self._log(tid, {"actor": step.get("actor", "Devin"), "phase": "deployment",
                                "msg": f"$ {step.get('command')} → {step.get('output')} "
                                       f"({step.get('duration_s', 0)}s)"})
            self._log(tid, {"actor": "ServiceNow", "phase": "deployment",
                            "msg": f"{ring['label']}: {ring['assets']} activos desplegados y validados → healthy "
                                   f"({', '.join(executed) or 'sin objetivos'})."})
            self._apply_lab_patch(job)
            if p["rings_done"] >= len(engine.RING_DEFS):
                t["status"] = "remediated"
                self.vulnerable_items[t["vulnerable_item_id"]]["status"] = "fixed"
                self._log(tid, {"actor": "ServiceNow", "phase": "deployment",
                                "msg": "Reescaneo verificado. Vulnerable Item → FIXED. Informe de auditoría generado."})
        elif job.job_type is JobType.RESET_LAB and job.state is JobState.RESTORED:
            self._apply_lab_reset(tid, job)
        elif job.job_type is not JobType.PATCH and job.state is JobState.RESTORED:
            self._apply_rollback(tid, job)
        elif job.state in (JobState.FAILED, JobState.RESTORE_FAILED, JobState.TIMED_OUT,
                           JobState.CANCELLED):
            self._log(tid, {"actor": "msr-platform", "phase": "deployment",
                            "msg": f"Job {job.id} finalizado en estado {job.state.value} "
                                   f"({job.error_code or 'sin código'}): "
                                   f"{sanitize_text(job.error_message or '-', 300)}. "
                                   f"El anillo {job.ring_number} no avanza."})
            self._rebuild_deploy(tid)
        if persist:
            self.repo.save_job(job)

    # ------------------------------------------------------------------
    # Laboratorio reutilizable (modelo persistente; sin operaciones EC2)
    # ------------------------------------------------------------------
    def list_lab_targets(self) -> list[dict]:
        return [lab.as_dict() for lab in self.repo.list_lab_targets()]

    def get_lab_target(self, logical_lab_id: str) -> dict:
        lab = self.repo.get_lab_target(logical_lab_id)
        if lab is None:
            raise NotFoundError(f"El laboratorio {logical_lab_id} no está registrado.")
        return lab.as_dict()

    def register_lab_target(self, payload: dict) -> dict:
        """Registra o actualiza la instancia vulnerable reutilizable de la PoC."""
        logical_lab_id = (payload.get("logical_lab_id") or "").strip()
        if not logical_lab_id:
            raise ValidationError("logical_lab_id es obligatorio.",
                                  code="LAB_TARGET_INVALID")
        instance_id = payload.get("current_instance_id") or None
        if instance_id and not INSTANCE_ID_RE.match(instance_id):
            raise ValidationError(f"current_instance_id no es un Instance ID válido: {instance_id}",
                                  code="LAB_TARGET_INVALID")
        existing = self.repo.get_lab_target(logical_lab_id)
        lab = LabTarget(
            logical_lab_id=logical_lab_id,
            current_instance_id=instance_id,
            account_id=payload.get("account_id"),
            region=payload.get("region") or self.settings.aws_region or None,
            vulnerable_ami_id=payload.get("vulnerable_ami_id"),
            launch_template_id=payload.get("launch_template_id"),
            launch_template_version=payload.get("launch_template_version"),
            # El ASG lo fija la configuración (IaC): nunca llega en el payload.
            autoscaling_group_name=self.settings.lab_autoscaling_group_name or None,
            expected_vulnerable_package=payload.get("expected_vulnerable_package"),
            expected_vulnerable_version=payload.get("expected_vulnerable_version"),
            # Igual que el ASG: advisory, releasever y kernel corregido son
            # contrato de la IaC; el payload no puede sobreescribirlos.
            candidate_releasever=self.settings.patch_releasever or None,
            expected_fixed_kernel=self.settings.patch_expected_fixed_kernel or None,
            required_tags=dict(payload.get("required_tags") or {}))
        if existing is not None:
            # El registro describe el laboratorio; no borra el estado operativo
            # ya reconciliado con AWS.
            lab.last_reset_job_id = existing.last_reset_job_id
            lab.previous_instance_id = existing.previous_instance_id
            lab.lab_state = existing.lab_state
            lab.current_kernel = existing.current_kernel
            lab.advisory_applicable = existing.advisory_applicable
            lab.ssm_state = existing.ssm_state
            lab.health_state = existing.health_state
            lab.evidence_source = existing.evidence_source
            lab.last_patch_job_id = existing.last_patch_job_id
            lab.last_patch_execution_id = existing.last_patch_execution_id
            lab.last_reset_execution_id = existing.last_reset_execution_id
            lab.reconciliation_state = existing.reconciliation_state
            lab.last_reconciled_at = existing.last_reconciled_at
            lab.last_reconciliation_error = existing.last_reconciliation_error
            lab.last_correlation_id = existing.last_correlation_id
        return self.repo.upsert_lab_target(lab).as_dict()

    # --- resolución dinámica por identificador lógico -------------------
    def _lab_or_404(self, logical_lab_id: str) -> LabTarget:
        lab = self.repo.get_lab_target(logical_lab_id)
        if lab is None:
            raise NotFoundError(f"El laboratorio {logical_lab_id} no está registrado.")
        return lab

    def _lab_task_id(self, logical_lab_id: str) -> str:
        """Tarea de remediación track A asociada al laboratorio."""
        for tid, task in self.tasks.items():
            if task.get("logical_lab_id") == logical_lab_id:
                return tid
        raise NotFoundError(
            f"No hay ninguna tarea de remediación asociada al laboratorio {logical_lab_id}.")

    def _resolve_lab_instance(self, logical_lab_id: str) -> LabInstance:
        """Instance ID actual del laboratorio, resuelto por tags (nunca fijado)."""
        instance = self.lab_resolver.resolve(logical_lab_id)
        lab = self.repo.get_lab_target(logical_lab_id)
        if lab is not None and lab.current_instance_id != instance.instance_id:
            lab.current_instance_id = instance.instance_id
            lab.account_id = instance.account_id or lab.account_id
            lab.region = instance.region or lab.region
            lab.vulnerable_ami_id = instance.image_id or lab.vulnerable_ami_id
            self.repo.upsert_lab_target(lab)
        return instance

    def _lab_state(self, logical_lab_id: str, tid: str) -> dict:
        """Estado operativo del laboratorio según la evidencia persistida.

        La evidencia observada en AWS manda: el histórico de jobs sólo aporta las
        referencias de los últimos jobs. Mientras no haya evidencia se declara
        `unknown`, nunca «parcheado» ni «vulnerable confirmado».
        """
        lab = self.repo.get_lab_target(logical_lab_id)
        last_patch = last_reset = None
        for job in self.repo.list_jobs_for_task_chronological(tid):
            if job.job_type is JobType.PATCH and job.state is JobState.SUCCEEDED:
                last_patch = job
            elif job.job_type is JobType.RESET_LAB and job.state is JobState.RESTORED:
                last_reset = job
        state = lab.lab_state if lab else LAB_STATE_UNKNOWN
        return {
            "vulnerable_state": state,
            "advisory_confirmed": bool(lab and lab.advisory_applicable is not None),
            "advisory_applicable": lab.advisory_applicable if lab else None,
            "current_kernel": lab.current_kernel if lab else None,
            "health_state": lab.health_state if lab else None,
            "ssm_state": lab.ssm_state if lab else None,
            "evidence_source": lab.evidence_source if lab else None,
            "reconciliation_state": lab.reconciliation_state if lab else None,
            "last_reconciled_at": (lab.as_dict()["last_reconciled_at"] if lab else None),
            "last_reconciliation_error": lab.last_reconciliation_error if lab else None,
            "last_patch_execution_id": lab.last_patch_execution_id if lab else None,
            "last_reset_execution_id": lab.last_reset_execution_id if lab else None,
            "previous_instance_id": lab.previous_instance_id if lab else None,
            "last_patch_job_id": last_patch.id if last_patch else None,
            "last_reset_job_id": last_reset.id if last_reset else None,
        }

    def lab_snapshot(self, logical_lab_id: str) -> dict:
        """Vista de sólo lectura del laboratorio para la UI (`GET /api/labs/{id}`)."""
        lab = self._lab_or_404(logical_lab_id)
        tid = self._lab_task_id(logical_lab_id)
        instance: dict | None = None
        resolution_error: dict | None = None
        try:
            instance = self._resolve_lab_instance(logical_lab_id).as_dict()
        except LabResolutionError as exc:
            resolution_error = {"code": exc.code, "message": exc.message,
                                "candidates": list(exc.candidates)}
        except ProviderError as exc:
            resolution_error = {"code": exc.code, "message": exc.message, "candidates": []}
        active = self.active_job(tid)
        return {
            "lab": self.repo.get_lab_target(logical_lab_id).as_dict() if lab else None,
            "instance": instance,
            "resolution_error": resolution_error,
            "task_id": tid,
            "advisory_id": self.settings.patch_advisory_id,
            "package_family": self.settings.patch_package_family,
            "releasever": self.settings.patch_releasever,
            "expected_fixed_kernel": self.settings.patch_expected_fixed_kernel,
            "environment": self.settings.lab_environment,
            "required_tags": required_lab_tags(self.settings, logical_lab_id),
            "execution_mode": self.settings.execution_mode(),
            "dry_run": self.settings.effective_dry_run(self.patch_provider.name),
            "patch_provider": self.patch_provider.name,
            "restore_provider": self.restore_provider.name,
            "active_job": active.as_dict() if active else None,
            "reconciliation": self.lab_lifecycle.status(logical_lab_id),
            **self._lab_state(logical_lab_id, tid),
        }

    def validate_lab(self, logical_lab_id: str) -> dict:
        """Validación de sólo lectura: no inicia ninguna Automation ni muta nada."""
        self._lab_or_404(logical_lab_id)
        tid = self._lab_task_id(logical_lab_id)
        checks: list[dict] = [{"check": "Laboratorio registrado", "ok": True,
                               "detail": f"Laboratorio {logical_lab_id} presente en SQLite."}]
        instance = None
        try:
            instance = self._resolve_lab_instance(logical_lab_id)
            checks.append({"check": "Instancia resuelta por tags", "ok": True,
                           "detail": f"{instance.instance_id} ({instance.source})."})
        except (LabResolutionError, ProviderError) as exc:
            checks.append({"check": "Instancia resuelta por tags", "ok": False,
                           "detail": exc.message, "code": exc.code})

        evidence = None
        if instance is not None:
            missing = check_lab_tags(instance.tags, self.settings, logical_lab_id)
            checks.append({"check": "Tags obligatorios", "ok": not missing,
                           "detail": ("Todos los tags obligatorios presentes."
                                      if not missing else f"Faltan: {', '.join(missing)}")})
            checks.append({"check": "Instancia en ejecución", "ok": instance.state == "running",
                           "detail": f"Estado EC2: {instance.state}."})
            checks.append({"check": "Nodo gestionado por SSM", "ok": instance.ssm_managed,
                           "detail": f"PingStatus: {instance.ping_status or 'desconocido'}."})
            policy = evaluate_target(
                instance.as_target(self.settings.lab_environment), self.settings,
                instance_state=instance.state, require_instance=True,
                strict=self.settings.real_aws_execution())
            checks.extend(policy.checks)
            # Evidencia de sólo lectura: es la que decide si el laboratorio está
            # listo, y se persiste para que la UI no muestre un estado obsoleto.
            evidence = self.lab_precheck.inspect(instance)
            checks.extend(evidence.checks)
            self.lab_lifecycle.record_observation(logical_lab_id, instance, evidence)

        for operation in (OPERATION_PATCH, OPERATION_RESET_LAB):
            try:
                runbook = resolve_runbook(self.settings, operation)
                detail = f"{runbook.name} (Automation)."
                ok = True
            except RunbookContractError as exc:
                detail, ok = exc.message, False
            checks.append({"check": f"Runbook de {operation} configurado", "ok": ok,
                           "detail": detail})

        return {
            "logical_lab_id": logical_lab_id,
            "read_only": True,
            "allowed": all(c.get("ok") for c in checks),
            "checks": checks,
            "instance": instance.as_dict() if instance else None,
            "evidence": evidence.as_dict() if evidence else None,
            "task_id": tid,
            "advisory_id": self.settings.patch_advisory_id,
            "releasever": self.settings.patch_releasever,
            "expected_fixed_kernel": self.settings.patch_expected_fixed_kernel,
            "note": ("La aplicabilidad real del advisory sólo se confirma con el precheck "
                     "del runbook; esta validación no ejecuta nada en la instancia."),
            **self._lab_state(logical_lab_id, tid),
        }

    def lab_jobs(self, logical_lab_id: str) -> list[dict]:
        """Historial completo de jobs del laboratorio (parcheo y resets)."""
        self._lab_or_404(logical_lab_id)
        tid = self._lab_task_id(logical_lab_id)
        return [job.as_dict() for job in self.list_task_jobs(tid)]

    def start_lab_reset_job(self, logical_lab_id: str,
                            idempotency_key: str | None = None, *,
                            correlation_id: str | None = None,
                            trigger: str = "lab_reset") -> PatchJob:
        """`reset_lab`: recreación deliberada de la instancia vulnerable.

        Distinto de `rollback` (recuperación de una ejecución fallida): no
        depende de que haya anillos desplegados, no toca `rings_done` al
        crearse y termina actualizando el Instance ID del laboratorio.
        """
        lab = self._lab_or_404(logical_lab_id)
        tid = self._lab_task_id(logical_lab_id)
        replay = self._replay(idempotency_key)
        if replay is not None:
            return replay
        try:
            instance = self._resolve_lab_instance(logical_lab_id)
        except LabResolutionError as exc:
            raise ValidationError(exc.message, code=exc.code) from exc
        target = instance.as_target(self.settings.lab_environment)

        active = self.repo.active_job_for_task(tid)
        if active is not None:
            active = self.reconcile_job(active)
            if active.active:
                raise ConflictError(f"El laboratorio {logical_lab_id} ya tiene un job activo "
                                    f"({active.id}).", correlation_id=active.correlation_id)

        job_id = new_job_id()
        dry_run = self.settings.effective_dry_run(self.restore_provider.name)
        request = RestoreRequest(
            job_id=job_id, task_id=tid, ring_number=0, targets=(target,),
            reason=f"Reset del laboratorio {logical_lab_id}", target_version="",
            snapshot_ref=None, dry_run=dry_run, restore_kind=RESTORE_KIND_RESET_LAB,
            task_snapshot=_task_snapshot(self.tasks[tid]))
        job = PatchJob(
            id=job_id, job_type=JobType.RESET_LAB, task_id=tid, ring_number=0,
            provider=self.restore_provider.name, dry_run=dry_run, targets=(target,),
            state=JobState.RESTORE_QUEUED,
            idempotency_key=idempotency_key or f"auto:{job_id}",
            request_payload=_restore_request_payload(request))
        # La reconciliación propaga su correlation ID para que el job, la
        # Automation y el estado del laboratorio compartan la misma traza.
        if correlation_id:
            job.correlation_id = correlation_id
        job.request_payload.update({
            "trigger": trigger, "correlation_id": job.correlation_id,
            "logical_lab_id": logical_lab_id,
            "previous_instance_id": instance.instance_id,
        })
        # Reset del laboratorio: excluye cualquier otra mutación (parcheo desde
        # la UI u otra reconciliación). Una reconciliación que ya tiene el lock
        # reentra con el mismo dueño y conserva su responsabilidad de liberarlo.
        if self._take_lab_lock(logical_lab_id, job.correlation_id, LOCK_OPERATION_RESET,
                               f"reset:{trigger}"):
            job.request_payload["lab_lock"] = {"lab_id": logical_lab_id,
                                               "owner": job.correlation_id,
                                               "operation": LOCK_OPERATION_RESET}
        request = _restore_request_from_payload(job.request_payload)

        try:
            job, created = self.repo.create_job(job, scope="lab_reset")
        except TargetBusyError as exc:
            self._release_lab_lock_for_job(job, force=True)
            raise ConflictError(
                f"El objetivo {exc.logical_target_id} ya tiene un job activo.") from exc
        if not created:
            self._release_lab_lock_for_job(job, force=True)
            return job
        self.repo.record_lab_reset(logical_lab_id, job.id)
        self.repo.append_event(job.id, job.state,
                               f"Reset del laboratorio {logical_lab_id} solicitado sobre "
                               f"{instance.instance_id}.")
        job.transition_to(JobState.VALIDATING)
        self.repo.save_job(job)
        try:
            policy = self.restore_provider.validate_target(request)
            job.result_payload["policy"] = policy.as_dict()
            if not policy.allowed:
                self._fail_job(job, policy.error_code or "TARGET_NOT_ALLOWED", policy.message)
                raise TargetNotAllowedError(policy.message,
                                            code=policy.error_code or "TARGET_NOT_ALLOWED",
                                            correlation_id=job.correlation_id)
            execution = self.restore_provider.start(request, job.idempotency_key)
        except ProviderError as exc:
            self._fail_job(job, exc.code, exc.message)
            raise self._provider_error(exc) from exc

        job.provider_reference = execution.provider_reference
        job.dry_run = execution.dry_run
        self._absorb_execution(job, execution)
        self.repo.save_job(job)
        if job.terminal:
            self._apply_job_outcome(tid, job)
        else:
            job = self.reconcile_job(job)
        _ = lab
        return job

    def _apply_lab_reset(self, tid: str, job: PatchJob) -> None:
        """Efecto de un reset confirmado: nueva instancia y laboratorio vulnerable.

        No modifica el historial de jobs ni incrementa `rings_done`: devuelve el
        laboratorio a su línea base para poder repetir el ciclo completo.
        """
        logical_lab_id = job.request_payload.get("logical_lab_id") or ""
        previous = job.request_payload.get("previous_instance_id")
        report = job.result_payload.get("report") or {}
        new_instance_id = self._rediscovered_instance_id(logical_lab_id, previous)
        if new_instance_id is None and not self.settings.uses_aws():
            # Sólo en modo simulado: sin AWS no hay dónde redescubrir la instancia.
            new_instance_id = job.result_payload.get("new_instance_id")
        lab = self.repo.get_lab_target(logical_lab_id) if logical_lab_id else None
        if lab is not None:
            if new_instance_id and new_instance_id != previous:
                lab.previous_instance_id = previous or lab.previous_instance_id
                lab.current_instance_id = new_instance_id
            lab.last_reset_job_id = job.id
            lab.last_reset_execution_id = job.provider_reference or lab.last_reset_execution_id
            lab.last_correlation_id = job.correlation_id
            lab.lab_state = LAB_STATE_VULNERABLE
            lab.advisory_applicable = True
            lab.current_kernel = report.get("RunningKernel") or None
            lab.health_state = (report.get("HealthState") or "").lower() or lab.health_state
            lab.last_patch_execution_id = None
            lab.last_patch_job_id = None
            self.repo.upsert_lab_target(lab)

        p = self.pipelines[tid]
        t = self.tasks[tid]
        p["rings_done"] = 0
        p["ring_evidence"] = {}
        p["rolled_back_rings"] = []
        t["status"] = "in_flight" if t.get("status") == "remediated" else t.get("status")
        self.vulnerable_items[t["vulnerable_item_id"]]["status"] = "open"
        self._rebuild_deploy(tid)
        self._log(tid, {"actor": "msr-platform", "phase": "deployment",
                        "msg": f"↺ Reset del laboratorio {logical_lab_id or '-'} completado "
                               f"(job {job.id}): instancia {previous or '-'} → "
                               f"{new_instance_id or 'pendiente de resolver'}. "
                               "El laboratorio vuelve a estado vulnerable."})

    def _apply_lab_patch(self, job: PatchJob) -> None:
        """Efecto de un parcheo confirmado sobre el estado del laboratorio.

        El estado pasa a `patched` con la evidencia que devuelve el Automation
        Report (kernel y salud), de modo que la UI deja de mostrar el estado
        anterior en cuanto AWS confirma el parcheo.
        """
        logical_lab_id = self.settings.lab_logical_id
        lab = self.repo.get_lab_target(logical_lab_id) if logical_lab_id else None
        if lab is None:
            return
        instance_ids = {target.instance_id for target in job.targets if target.instance_id}
        if lab.current_instance_id and lab.current_instance_id not in instance_ids:
            return
        report = job.result_payload.get("report") or {}
        lab.lab_state = LAB_STATE_PATCHED
        lab.last_patch_job_id = job.id
        lab.last_patch_execution_id = job.provider_reference or lab.last_patch_execution_id
        lab.last_correlation_id = job.correlation_id
        lab.current_kernel = (report.get("CurrentKernel")
                              or job.result_payload.get("to_version")
                              or lab.expected_fixed_kernel)
        lab.advisory_applicable = False
        health = (report.get("HealthStatus") or "").lower()
        lab.health_state = health or "healthy"
        lab.evidence_source = job.provider
        self.repo.upsert_lab_target(lab)

    def _rediscovered_instance_id(self, logical_lab_id: str, previous: str | None) -> str | None:
        """Instance ID redescubierto en AWS tras un reset (nunca el del provider).

        La fuente de verdad es el descubrimiento por tags en AWS: el
        `NewInstanceId` que devuelve la Automation nunca lo sustituye. Si el
        descubrimiento devuelve la instancia anterior, no se acepta como
        reemplazo.
        """
        if not logical_lab_id:
            return None
        try:
            instance = self.lab_resolver.resolve(logical_lab_id)
        except (LabResolutionError, ProviderError):
            return None
        if previous and instance.instance_id == previous:
            return None
        return instance.instance_id

    # --- reconciliación del laboratorio (fase 2.6) ----------------------
    def ensure_lab_ready(self, logical_lab_id: str | None = None, *,
                         confirmed: bool = False, reason: str = "api") -> dict:
        """`ensure_lab_ready`: deja el laboratorio listo para una nueva demostración."""
        return self.lab_lifecycle.ensure_lab_ready(logical_lab_id, confirmed=confirmed,
                                                   reason=reason)

    def lab_reconciliation_status(self, logical_lab_id: str | None = None) -> dict:
        """Estado del reconciliador de laboratorio (sin llamadas a AWS)."""
        return self.lab_lifecycle.status(logical_lab_id)

    # ------------------------------------------------------------------
    def get_job(self, job_id: str) -> PatchJob:
        job = self.repo.get_job(job_id, with_events=True)
        if job is None:
            raise NotFoundError(f"El job {job_id} no existe.")
        return self.reconcile_job(job)

    def list_task_jobs(self, tid: str) -> list[PatchJob]:
        if tid not in self.tasks:
            raise NotFoundError(f"La tarea {tid} no existe.")
        active = self.repo.active_job_for_task(tid)
        if active is not None:
            self.reconcile_job(active)
        return self.repo.list_jobs_for_task(tid)

    def active_job(self, tid: str) -> PatchJob | None:
        if tid not in self.tasks:
            raise NotFoundError(f"La tarea {tid} no existe.")
        job = self.repo.active_job_for_task(tid)
        return self.reconcile_job(job) if job is not None else None

    def cancel_job(self, job_id: str) -> PatchJob:
        job = self.get_job(job_id)
        if job.terminal:
            raise ConflictError(f"El job {job_id} ya ha finalizado ({job.state.value}).",
                                code="JOB_ALREADY_TERMINAL", correlation_id=job.correlation_id)
        if job.job_type is not JobType.PATCH:
            raise ValidationError("La cancelación sólo está soportada para jobs de parcheo.",
                                  code="CANCEL_NOT_SUPPORTED")
        request = _patch_request_from_payload(job.request_payload)
        try:
            execution = self.patch_provider.cancel(job.provider_reference or "", request)
        except ProviderError as exc:
            raise self._provider_error(exc) from exc
        if job.state is not JobState.CANCELLING:
            job.transition_to(JobState.CANCELLING)
            self.repo.append_event(job.id, job.state, "Cancelación solicitada al provider.")
        self._absorb_execution(job, execution)
        self.repo.save_job(job)
        if job.terminal:
            self._apply_job_outcome(job.task_id, job)
        return job

    def _log(self, tid, entry):
        entry = {**entry, "ts": iso(NOW), "task_id": tid}
        self.pipelines[tid]["logs"].append(entry)
        self.activity.insert(0, entry)
        self.activity[:] = self.activity[:200]


def task_cvss(task, store):
    return store.vulnerable_items[task["vulnerable_item_id"]]["cvss"]


STORE = Store()
