"""Estado en memoria de la plataforma + orquestación de fases (plano de control).

Las fases 1-5 siguen siendo síncronas y simuladas. La fase de despliegue delega
la ejecución en un provider (mock o AWS Systems Manager Automation) mediante un
*job* persistido en SQLite: el store no ejecuta la operación, sólo crea el job,
lo reconcilia con `provider.poll()` y aplica el efecto cuando termina.
"""
from __future__ import annotations

import random
from datetime import datetime

from . import engine, seed
from .config import Settings, get_settings
from .errors import (
    ConflictError,
    DependencyUnavailableError,
    NotFoundError,
    TargetNotAllowedError,
    ValidationError,
)
from .jobs import JobState, JobType, PatchJob, new_job_id, state_for_execution
from .policy import sanitize_text
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
from .seed import NOW, iso

# Códigos de provider que representan configuración ausente o dependencia caída.
_UNAVAILABLE_CODES = frozenset({"PROVIDER_UNAVAILABLE", "PROVIDER_MISCONFIGURED",
                                "RUNBOOK_NOT_CONFIGURED", "PROVIDER_START_FAILED"})
_TASK_SNAPSHOT_KEYS = ("id", "cve", "ci_id", "ci_name", "component", "track",
                       "vulnerable_version", "criticality", "environment")


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
        self.reset(clear_jobs=False)

    def reset(self, clear_jobs: bool = True):
        if clear_jobs:
            self.repo.clear()
        data = seed.build_all()
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
            rings_done = random.Random(hash(tid) & 0xFFFF).randint(1, 3)
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
        }
        if phase_index >= 5 and rings_done >= len(engine.RING_DEFS):
            self.tasks[tid]["status"] = "remediated"

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
            "funnel": [
                {"label": "Hallazgos totales", "value": 100000},
                {"label": "Relevantes", "value": 8000},
                {"label": "Explotables", "value": 500},
                {"label": "Críticos para banca", "value": 80},
                {"label": "Remediación inmediata", "value": 20},
            ],
            "kpis": {
                "open_findings": len(self.findings) * 420,
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
                "sla": sla_state(t.get("sla_due", "")),
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

    def _resolve_target(self, tid, ring_no) -> Target:
        """Objetivo del anillo: el CI raíz si está en el alcance, si no el primero.

        Los IDs de instancia nunca están hardcodeados en la CMDB: si el operador
        define MSR_SANDBOX_INSTANCE_ID, se superpone al objetivo correspondiente.
        """
        assets = self._ring_assets(tid, ring_no)
        if not assets:
            raise ValidationError(
                f"El anillo {ring_no} no tiene activos seleccionados para desplegar.",
                code="NO_TARGET_SELECTED")
        asset = next((a for a in assets if a.get("is_root")), assets[0])
        logical_id = asset.get("logical_target_id") or asset["id"]
        instance_id = asset.get("instance_id")
        region = asset.get("region")
        sandbox_id = self.settings.sandbox_instance_id
        sandbox_logical = self.settings.sandbox_logical_target_id
        if sandbox_id and (not sandbox_logical or sandbox_logical == logical_id):
            instance_id = sandbox_id
            region = self.settings.aws_region or region
        return Target(
            logical_target_id=logical_id, instance_id=instance_id,
            account_id=asset.get("account_id"), region=region,
            tags=dict(asset.get("tags") or {}),
            operating_system=asset.get("os"), environment=asset.get("environment"),
            ssm_managed=bool(asset.get("ssm_managed")), name=asset.get("name"))

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
        return self.repo.save_job(job)

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

        target = self._resolve_target(tid, ring_no)
        busy = self.repo.active_job_for_target(target.logical_target_id)
        if busy is not None and busy.active:
            raise ConflictError(
                f"El objetivo {target.logical_target_id} ya tiene un job activo ({busy.id}).",
                correlation_id=busy.correlation_id)

        deploy = p["artifacts"]["deployment"]
        ring = next(r for r in deploy["rings"] if r["ring"] == ring_no)
        from_version = engine._prev_version(t)
        request_job_id = new_job_id()
        dry_run = self.settings.effective_dry_run(self.patch_provider.name)
        request = PatchRequest(
            job_id=request_job_id, task_id=tid, ring_number=ring_no,
            targets=(target,),
            spec=PatchSpec(component=t.get("component", t["ci_name"]),
                           from_version=from_version,
                           to_version=engine._fixed_version(from_version),
                           cve=t.get("cve"), track=t.get("track", "A")),
            dry_run=dry_run, ring_label=ring["label"], executor=deploy["executor"],
            assets_count=max(1, ring["assets"]), task_snapshot=_task_snapshot(t))
        job = PatchJob(
            id=request_job_id, job_type=JobType.PATCH, task_id=tid, ring_number=ring_no,
            provider=self.patch_provider.name, dry_run=dry_run, targets=(target,),
            idempotency_key=idempotency_key or f"auto:{request_job_id}",
            request_payload=_patch_request_payload(request))
        job.request_payload["correlation_id"] = job.correlation_id
        request = _patch_request_from_payload(job.request_payload)

        try:
            job, created = self.repo.create_job(job, scope="approve")
        except TargetBusyError as exc:
            raise ConflictError(
                f"El objetivo {exc.logical_target_id} ya tiene un job activo.") from exc
        if not created:
            return job  # idempotencia: misma clave → mismo job

        self.repo.append_event(job.id, job.state,
                               f"Job creado para el anillo {ring_no} ({ring['label']}).")
        self._log(tid, {"actor": "Owner (HITL)", "phase": "deployment",
                        "msg": f"[HITL] Aprobado despliegue de {ring['label']} ({ring['assets']} activos). "
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
        for key in ("from_version", "to_version", "restored_version"):
            value = getattr(execution, key, None)
            if value:
                job.result_payload[key] = value
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

    def reconcile_job(self, job: PatchJob) -> PatchJob:
        """Consulta al provider y aplica el resultado. Idempotente y sin duplicar logs."""
        if job.terminal or not job.provider_reference:
            return job
        elapsed = (utcnow() - job.created_at).total_seconds()
        if elapsed > self.settings.job_timeout_seconds:
            job.transition_to(JobState.TIMED_OUT, error_code="JOB_TIMED_OUT",
                              error_message="El job excedió MSR_JOB_TIMEOUT_SECONDS.")
            self.repo.append_event(job.id, job.state, "Job caducado por timeout.")
            self.repo.save_job(job)
            self._apply_job_outcome(job.task_id, job)
            return job
        try:
            if job.job_type is JobType.PATCH:
                request = _patch_request_from_payload(job.request_payload)
                execution = self.patch_provider.poll(job.provider_reference, request)
            else:
                request = _restore_request_from_payload(job.request_payload)
                execution = self.restore_provider.poll(job.provider_reference, request)
        except ProviderError as exc:
            message = f"No se pudo reconciliar el job: {exc.code}"
            if not self.repo.has_event(job.id, message):
                self.repo.append_event(job.id, job.state, message)
            return job
        self._absorb_execution(job, execution)
        self.repo.save_job(job)
        if job.terminal:
            self._apply_job_outcome(job.task_id, job)
        return job

    # ------------------------------------------------------------------
    def _apply_job_outcome(self, tid, job: PatchJob) -> None:
        """Aplica el efecto de un job terminal exactamente una vez."""
        if tid not in self.pipelines or job.result_payload.get("outcome_applied"):
            return
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
            p["ring_evidence"][ring_no] = {
                "steps": job.steps(),
                "from_version": job.result_payload.get("from_version"),
                "to_version": job.result_payload.get("to_version"),
                "job_id": job.id, "provider": job.provider,
            }
            deploy = self._rebuild_deploy(tid)
            ring = next(r for r in deploy["rings"] if r["ring"] == ring_no)
            for step in job.steps():
                self._log(tid, {"actor": step.get("actor", "Devin"), "phase": "deployment",
                                "msg": f"$ {step.get('command')} → {step.get('output')} "
                                       f"({step.get('duration_s', 0)}s)"})
            self._log(tid, {"actor": "ServiceNow", "phase": "deployment",
                            "msg": f"{ring['label']}: {ring['assets']} activos desplegados y validados → healthy."})
            if p["rings_done"] >= len(engine.RING_DEFS):
                t["status"] = "remediated"
                self.vulnerable_items[t["vulnerable_item_id"]]["status"] = "fixed"
                self._log(tid, {"actor": "ServiceNow", "phase": "deployment",
                                "msg": "Reescaneo verificado. Vulnerable Item → FIXED. Informe de auditoría generado."})
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
        self.repo.save_job(job)

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
