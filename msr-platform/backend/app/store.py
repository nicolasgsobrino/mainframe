"""Estado en memoria de la plataforma + orquestación de fases (plano de control)."""
from __future__ import annotations
import random
from datetime import datetime, timedelta

from . import seed, engine
from .seed import NOW, iso


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


class Store:
    def __init__(self):
        self.reset()

    def reset(self):
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
                {"actor": A, "phase": pid, "msg": f"Deduplicación y enriquecimiento de fuentes completados."},
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
                {"actor": A, "phase": pid, "msg": f"Ejecutando MVT en laboratorio vía CI/CD y frameworks de test..."},
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

    def task_detail(self, tid):
        if tid not in self.tasks:
            return None
        t = self.tasks[tid]
        p = self.pipelines[tid]
        vi = self.vulnerable_items[t["vulnerable_item_id"]]
        lane = t.get("lane", "standard")
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
        }

    # ------------------------------------------------------------------
    # API de acciones (HITL / avance)
    # ------------------------------------------------------------------
    def approve_phase(self, tid):
        """Aprobación humana de la fase actual → avanza a la siguiente."""
        if tid not in self.pipelines:
            return None
        p = self.pipelines[tid]
        idx = p["phase_index"]
        pid = engine.PHASE_IDS[idx]
        t = self.tasks[tid]

        # Fase de despliegue: aprobar avanza un anillo (requiere pre-aprobación del anillo)
        if pid == "deployment":
            if p["rings_done"] < len(engine.RING_DEFS):
                next_ring = engine.RING_DEFS[p["rings_done"]][0]
                pa = p.get("ring_preapprovals", {}).get(next_ring)
                if not (pa and pa.get("preapproved")):
                    self._log(tid, {"actor": "ServiceNow", "phase": pid,
                                    "msg": f"Despliegue del anillo {next_ring} bloqueado: requiere revisión y pre-aprobación Human-Driven del informe pre-anillo."})
                    return self.task_detail(tid)
                p["rings_done"] += 1
                deploy = self._rebuild_deploy(tid)
                ring = deploy["rings"][p["rings_done"] - 1]
                self._log(tid, {"actor": "Owner (HITL)", "phase": pid,
                                "msg": f"[HITL] Aprobado despliegue de {ring['label']} ({ring['assets']} activos)."})
                # registrar las acciones ejecutadas (evidencia de ejecución)
                if ring.get("actions"):
                    for s in ring["actions"]["steps"]:
                        self._log(tid, {"actor": s["actor"], "phase": pid,
                                        "msg": f"$ {s['command']} → {s['output']} ({s['duration_s']}s)"})
                self._log(tid, {"actor": "ServiceNow", "phase": pid,
                                "msg": f"{ring['label']}: {ring['assets']} activos desplegados y validados → healthy."})
                if p["rings_done"] >= len(engine.RING_DEFS):
                    t["status"] = "remediated"
                    vi = self.vulnerable_items[t["vulnerable_item_id"]]
                    vi["status"] = "fixed"
                    self._log(tid, {"actor": "ServiceNow", "phase": pid,
                                    "msg": "Reescaneo verificado. Vulnerable Item → FIXED. Informe de auditoría generado."})
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
            preapprovals=p.get("ring_preapprovals"), exclusions=p.get("ring_exclusions"))
        a["deployment"] = deploy
        a["audit"] = engine.build_audit(t, a["impact"], a["mvt"], a["lab"], a["prototype"], deploy)
        return deploy

    def rollback(self, tid, reason=None, trigger="manual"):
        """Ejecuta el rollback del último anillo desplegado (manual o automático)."""
        if tid not in self.pipelines:
            return None
        p = self.pipelines[tid]
        t = self.tasks[tid]
        if p["rings_done"] <= 0:
            return self.task_detail(tid)
        ring_no = engine.RING_DEFS[p["rings_done"] - 1][0]
        plan = p["artifacts"]["deployment"]["rollback_plan"]
        reason = reason or ("Fallo de post-checks / breach de health-check" if trigger == "auto" else "Rollback solicitado por el owner")
        self._log(tid, {"actor": "ServiceNow", "phase": "deployment",
                        "msg": f"⟲ ROLLBACK ({trigger}) del anillo {ring_no}. Motivo: {reason}. RTO objetivo {plan['rto_minutes']} min."})
        # ejecutar los pasos del plan de rollback (evidencia)
        for s in plan["steps"]:
            self._log(tid, {"actor": s["actor"], "phase": "deployment",
                            "msg": f"$ {s['command']} → {s['desc']}"})
        # marcar anillo revertido y retroceder el progreso
        if ring_no not in p["rolled_back_rings"]:
            p["rolled_back_rings"].append(ring_no)
        p["rings_done"] -= 1
        p["rollback"] = {
            "status": "completed", "triggered": True, "trigger_type": trigger,
            "reason": reason, "ring": ring_no, "ts": iso(NOW),
            "restored_version": plan["target_version"],
            "verdict": "healthy tras rollback",
        }
        # el VI vuelve a estar abierto/en riesgo
        vi = self.vulnerable_items[t["vulnerable_item_id"]]
        vi["status"] = "in_progress"
        if t.get("status") == "remediated":
            t["status"] = "in_flight"
        self._rebuild_deploy(tid)
        self._log(tid, {"actor": "Devin", "phase": "deployment",
                        "msg": f"Rollback completado. Versión restaurada: {plan['target_version']}. Servicio healthy; anillo {ring_no} marcado como revertido para re-análisis."})
        return self.task_detail(tid)

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

    def _log(self, tid, entry):
        entry = {**entry, "ts": iso(NOW), "task_id": tid}
        self.pipelines[tid]["logs"].append(entry)
        self.activity.insert(0, entry)
        self.activity[:] = self.activity[:200]


def task_cvss(task, store):
    return store.vulnerable_items[task["vulnerable_item_id"]]["cvss"]


STORE = Store()
