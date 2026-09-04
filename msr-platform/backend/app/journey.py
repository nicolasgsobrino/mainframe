"""Patching Journey: proyección de las 8 fases del modelo sobre el pipeline.

El pipeline operativo sigue teniendo 6 fases (`engine.PHASES`) porque son las
que gobiernan las aprobaciones HITL. Las 8 fases del journey son una *lectura*
de ese mismo estado, no un segundo motor: aquí no se guarda estado ni se muta
nada, sólo se traduce.

Dos reglas del modelo condicionan la proyección:

- las fases 0-3 ocurren una vez por vulnerabilidad;
- las fases 4-7 se repiten en cada anillo, con su propio gobierno de cambio.
"""
from __future__ import annotations

from . import engine

BANDS = [
    ("demand_risk", "0-3 · Cualificación de demanda y riesgo"),
    ("change_planning", "4 · Gestión del cambio y planificación"),
    ("execution_closure", "5-7 · Ejecución controlada y cierre"),
]
BAND_LABELS = dict(BANDS)

# (id, label, nombre original de la slide, banda, ¿se repite por anillo?)
PHASES = [
    ("cyber_trigger", "Disparador de ciberseguridad",
     "Cybersecurity trigger", "demand_risk", False),
    ("asset_identification", "Confirmación de activos afectados",
     "Affected asset confirmation", "demand_risk", False),
    ("applicability_assessment", "Aplicabilidad y remediación",
     "Applicability & remediation assessment", "demand_risk", False),
    ("blast_radius", "Análisis de blast radius",
     "Blast radius analysis", "demand_risk", False),
    ("change_planning", "Marco de cambio y planificación",
     "Change framework & rollout planning", "change_planning", True),
    ("ring_execution", "Ejecución por anillos",
     "Patch execution by deployment rings", "execution_closure", True),
    ("gate_validation", "Validación de gate y rollback",
     "Gate validation & rollback decision", "execution_closure", True),
    ("evidence_closure", "Evidencias y cierre",
     "Evidence & closure", "execution_closure", True),
]
PHASE_IDS = [p[0] for p in PHASES]
PHASE_INDEX = {pid: i for i, pid in enumerate(PHASE_IDS)}
PHASE_LABELS = {p[0]: p[1] for p in PHASES}
PHASE_BANDS = {p[0]: p[3] for p in PHASES}


def phase_catalog() -> list[dict]:
    """Metadatos de las 8 fases, en orden, para que la UI no los duplique."""
    return [
        {"id": pid, "index": i, "label": label, "label_en": label_en,
         "band": band, "band_label": BAND_LABELS[band], "per_ring": per_ring}
        for i, (pid, label, label_en, band, per_ring) in enumerate(PHASES)
    ]


# Fase del pipeline activa → fase del journey en la que está la vulnerabilidad.
# `detection` cubre también la identificación de activos (correlación CMDB) y se
# cierra con la misma aprobación; `lab_testing`/`prototype` son la ejecución y el
# gate del anillo de laboratorio, que es un entorno aislado y pre-aprobado.
_PIPELINE_TO_JOURNEY = {
    "detection": ("cyber_trigger", None),
    "prioritization": ("applicability_assessment", None),
    "pre_implementation": ("blast_radius", None),
    "lab_testing": ("ring_execution", 1),
    "prototype": ("gate_validation", 1),
}

_FAILED_JOB_STATES = frozenset({"failed", "timed_out", "restore_failed"})
_UNCONFIRMED_JOB_STATES = frozenset({
    "timeout_pending_confirmation", "remote_status_unknown"})


def _ring_label(ring: int | None) -> str | None:
    if ring is None:
        return None
    return dict(engine.RING_DEFS).get(ring)


def _deployment_position(task: dict, pipeline: dict) -> tuple[str, int | None, list[str]]:
    """Posición dentro del ciclo 4→7, que se repite en cada anillo."""
    deploy = pipeline["artifacts"]["deployment"]
    rings = deploy["rings"]
    blockers: list[str] = []

    rolled_back = [r for r in rings if r["status"] == "rolled_back"]
    if pipeline.get("rollback", {}).get("triggered") and rolled_back:
        return "gate_validation", rolled_back[-1]["ring"], ["rollback"]

    active = next((r for r in rings if r["status"] == "in_progress"), None)
    if active is None:
        # Sin anillo activo: o está todo cerrado, o el histórico dejó el
        # despliegue completo. En ambos casos toca evidencia y cierre.
        return "evidence_closure", None, blockers

    job = active.get("job")
    if job:
        state = job.get("state")
        if state in _FAILED_JOB_STATES:
            return "gate_validation", active["ring"], ["job_failed"]
        if state in _UNCONFIRMED_JOB_STATES:
            return "gate_validation", active["ring"], ["job_unconfirmed"]
        if not job.get("terminal"):
            return "ring_execution", active["ring"], blockers

    approval = active["plan"]["approval"]
    if not approval.get("preapproved"):
        return "change_planning", active["ring"], ["awaiting_approval"]
    return "ring_execution", active["ring"], blockers


def position(task: dict, pipeline: dict) -> dict:
    """Fase del journey en la que se encuentra la vulnerabilidad, y por qué."""
    pipeline_phase = engine.PHASE_IDS[pipeline["phase_index"]]
    verified = pipeline.get("hitl_verifications") or {}
    if task.get("status") == "remediated":
        phase_id, ring, blockers = "evidence_closure", None, []
    elif pipeline_phase in _PIPELINE_TO_JOURNEY:
        phase_id, ring = _PIPELINE_TO_JOURNEY[pipeline_phase]
        # La confirmación de activos vive dentro de la misma fase del motor que
        # el disparador: es su verificación humana la que la hace visible.
        if phase_id == "cyber_trigger" and "scope_confirmation" in verified:
            phase_id = "asset_identification"
        blockers = []
    else:
        phase_id, ring, blockers = _deployment_position(task, pipeline)

    return {
        "phase": phase_id,
        "phase_index": PHASE_INDEX[phase_id],
        "phase_label": PHASE_LABELS[phase_id],
        "band": PHASE_BANDS[phase_id],
        "ring": ring,
        "ring_label": _ring_label(ring),
        "pipeline_phase": pipeline_phase,
        "blockers": blockers,
    }


def resource_rollup(pipeline: dict) -> dict:
    """Reparto de los recursos afectados entre parcheados, pendientes y fallidos.

    Es una derivación del estado de los anillos, no un estado por activo: el
    modelo no sigue cada CI de forma independiente. Los anillos de laboratorio y
    pre-producción son réplicas, así que sólo cuentan como parcheados los
    activos reales de los anillos productivos completados.
    """
    deploy = pipeline["artifacts"]["deployment"]
    total = deploy["total_assets"]

    patched = 0
    rolled_back = 0
    failed = 0
    for ring in deploy["rings"]:
        stage = engine.RING_STAGES[ring["ring"]]
        if not stage["prod"]:
            continue
        count = ring.get("executed_assets")
        count = ring["assets"] if count is None else int(count)
        if ring["status"] == "completed":
            patched = max(patched, count)
            # Un intento posterior fallido sobre un anillo ya desplegado no
            # devuelve sus activos a «fallidos»: la evidencia del despliegue manda.
            continue
        if ring["status"] == "rolled_back":
            rolled_back = max(rolled_back, count)
        job = ring.get("job") or {}
        if job.get("state") in _FAILED_JOB_STATES:
            failed = max(failed, len(job.get("targets") or []) or 1)

    excluded = len(deploy.get("exceptions") or [])
    pending = max(0, total - patched - failed - excluded)
    return {
        "total": total,
        "patched": min(patched, total),
        "pending": pending,
        "failed": min(failed, total),
        "excluded": min(excluded, total),
        "rolled_back": min(rolled_back, total),
        "rings_done": pipeline["rings_done"],
        "rings_total": len(engine.RING_DEFS),
    }


# ---------------------------------------------------------------------------
# Human in the Loop: capa transversal
# ---------------------------------------------------------------------------
# El control humano no es una fase del recorrido, es un tipo de evento que se
# repite a lo largo de él. Todas las puertas bloquean el motor: el recorrido no
# continúa mientras una esté pendiente. Lo que cambia es cómo se cierran
# (`closes_with`): la aprobación del cambio y la pre-aprobación de anillo tienen
# su propia acción histórica; el resto se cierra con una verificación humana
# registrada.
CLOSE_VERIFICATION = "verification"
CLOSE_PHASE_APPROVAL = "phase_approval"
CLOSE_RING_PREAPPROVAL = "ring_preapproval"

# (id, label, pregunta, fase del journey, fase del pipeline, cómo se cierra,
#  ¿se repite por anillo?)
GATES = [
    ("scope_confirmation", "Confirmación de alcance",
     "Los activos correlacionados con la CMDB son los correctos",
     "asset_identification", "detection", CLOSE_VERIFICATION, False),
    ("ai_proposal", "Validación de la propuesta de remediación",
     "Tipo de remediación, aplicabilidad y blast radius calculado",
     "blast_radius", "pre_implementation", CLOSE_VERIFICATION, False),
    ("change_approval", "Aprobación del cambio y del plan",
     "Cambio ITSM, ventana, secuencia de anillos y rollback armado",
     "change_planning", "prototype", CLOSE_PHASE_APPROVAL, False),
    ("ring_preapproval", "Pre-aprobación del anillo",
     "Autorización para ejecutar este lote concreto ahora",
     "ring_execution", None, CLOSE_RING_PREAPPROVAL, True),
    ("ring_result", "Validación del resultado del anillo",
     "Post-checks, salud y evidencia antes de promocionar",
     "gate_validation", None, CLOSE_VERIFICATION, True),
    ("closure", "Aceptación de evidencias y cierre",
     "Informe de auditoría y cierre del Vulnerable Item",
     "evidence_closure", None, CLOSE_VERIFICATION, False),
]

GATE_DONE = "done"
GATE_PENDING = "pending"
GATE_UPCOMING = "upcoming"

GATE_IDS = [g[0] for g in GATES]
GATE_PER_RING = {g[0]: g[6] for g in GATES}
GATE_CLOSES_WITH = {g[0]: g[5] for g in GATES}
# Puertas que se cierran registrando la verificación humana (el resto tienen su
# propia acción: aprobar la fase o pre-aprobar el anillo).
GATE_VERIFIABLE = {g[0]: g[5] == CLOSE_VERIFICATION for g in GATES}
GATE_LABELS = {g[0]: g[1] for g in GATES}


def verification_key(gate_id: str, ring: int | None) -> str:
    """Clave con la que se archiva la verificación humana de una puerta."""
    if GATE_PER_RING.get(gate_id) and ring is not None:
        return f"{gate_id}:{ring}"
    return gate_id


def gate_catalog() -> list[dict]:
    """Metadatos de las puertas humanas, para que la UI no los duplique."""
    return [
        {"id": gid, "label": label, "question": question, "phase": phase,
         # Todas bloquean el recorrido; `verifiable` dice si se cierran con una
         # verificación humana registrada o con su propia acción de aprobación.
         "enforced": True, "verifiable": closes_with == CLOSE_VERIFICATION,
         "closes_with": closes_with, "per_ring": per_ring}
        for gid, label, question, phase, _pipeline, closes_with, per_ring in GATES
    ]


def _phase_gate_status(pipeline: dict, pipeline_phase: str, remediated: bool) -> str:
    """Estado de una puerta ligada a la aprobación de una fase del pipeline."""
    if remediated or pipeline["statuses"].get(pipeline_phase) == "approved":
        return GATE_DONE
    if engine.PHASE_IDS[pipeline["phase_index"]] == pipeline_phase:
        return GATE_PENDING
    return GATE_UPCOMING


def gate_states(task: dict, pipeline: dict) -> list[dict]:
    """Las puertas humanas de una vulnerabilidad, en orden de recorrido.

    Se derivan del estado que ya existe (aprobaciones de fase, pre-aprobaciones
    por anillo, resultado de cada anillo y cierre): no introducen estado nuevo.
    """
    remediated = task.get("status") == "remediated"
    # Un anillo no espera decisión mientras el recorrido no haya llegado al
    # despliegue, aunque el plan ya lo marque como el siguiente de la cola.
    deploying = engine.PHASE_IDS[pipeline["phase_index"]] == "deployment"
    rings = pipeline["artifacts"]["deployment"]["rings"]
    verifications = pipeline.get("hitl_verifications") or {}
    meta = {g["id"]: g for g in gate_catalog()}
    out: list[dict] = []

    def emit(gid: str, status: str, *, ring: int | None = None,
             approval: dict | None = None, detail: str | None = None) -> None:
        # Una verificación humana explícita cierra la puerta y aporta su autor,
        # su sello de tiempo y el resultado que dejó registrado.
        verified = verifications.get(verification_key(gid, ring))
        record = verified or approval or {}
        out.append({**meta[gid],
                    "ring": ring,
                    "status": GATE_DONE if verified else status,
                    "actor": record.get("approver") or record.get("actor"),
                    "role": record.get("role"),
                    "ts": record.get("ts"),
                    "note": record.get("note"),
                    "output": (verified or {}).get("output"),
                    "verified": bool(verified),
                    "detail": detail})

    for gid, _label, _q, _phase, pipeline_phase, _closes, per_ring in GATES:
        if not per_ring and gid != "closure":
            emit(gid, _phase_gate_status(pipeline, pipeline_phase, remediated))
        elif gid == "closure":
            if remediated:
                emit(gid, GATE_DONE)
            elif pipeline["rings_done"] >= len(engine.RING_DEFS):
                # Todos los anillos desplegados: el cierre del Vulnerable Item
                # espera a que alguien acepte las evidencias.
                emit(gid, GATE_PENDING)
            else:
                emit(gid, GATE_UPCOMING)
        elif gid == "ring_preapproval":
            for r in rings:
                approval = r["plan"]["approval"]
                if approval.get("preapproved"):
                    status = GATE_DONE
                elif deploying and r["status"] == "in_progress":
                    status = GATE_PENDING
                else:
                    status = GATE_UPCOMING
                emit(gid, status, ring=r["ring"], approval=approval,
                     detail=r["label"])
        elif gid == "ring_result":
            for r in rings:
                if r["status"] == "completed":
                    # Desplegado pero sin revisar: el siguiente anillo no sale
                    # hasta que se valide el resultado de éste.
                    status = GATE_DONE if remediated else GATE_PENDING
                elif r["status"] == "rolled_back":
                    status = GATE_PENDING
                else:
                    job = r.get("job") or {}
                    failed = (job.get("state") in _FAILED_JOB_STATES
                              or job.get("state") in _UNCONFIRMED_JOB_STATES)
                    status = GATE_PENDING if deploying and failed else GATE_UPCOMING
                emit(gid, status, ring=r["ring"], detail=r["label"])
    return out


def gate_rollup(gates: list[dict]) -> dict:
    """Cuántas decisiones humanas hay tomadas, pendientes y por venir."""
    pending = [g for g in gates if g["status"] == GATE_PENDING]
    return {
        "total": len(gates),
        "done": sum(1 for g in gates if g["status"] == GATE_DONE),
        "pending": len(pending),
        # Todas las puertas detienen el recorrido hasta que alguien decide.
        "pending_enforced": sum(1 for g in pending if g["enforced"]),
        "next": next(({"id": g["id"], "label": g["label"], "ring": g["ring"],
                       "enforced": g["enforced"], "verifiable": g["verifiable"]}
                      for g in pending), None),
    }


def ring_states(pipeline: dict) -> list[dict]:
    """Los 5 anillos en compacto, para la tira de progreso de la vista detalle."""
    return [
        {"ring": r["ring"], "label": r["label"], "status": r["status"],
         "environment": r.get("environment"), "assets": r["assets"],
         "result": r["result"],
         "preapproved": bool(r["plan"]["approval"].get("preapproved"))}
        for r in pipeline["artifacts"]["deployment"]["rings"]
    ]


def phase_states(task: dict, pipeline: dict) -> list[dict]:
    """Las 8 fases con su estado para una vulnerabilidad concreta."""
    pos = position(task, pipeline)
    current = pos["phase_index"]
    remediated = task.get("status") == "remediated"
    gates = gate_states(task, pipeline)
    out = []
    for meta in phase_catalog():
        if remediated:
            status = "completed"
        elif meta["index"] < current:
            status = "completed"
        elif meta["index"] == current:
            status = "current"
        else:
            status = "pending"
        here = [g for g in gates if g["phase"] == meta["id"]]
        out.append({**meta, "status": status,
                    "ring": pos["ring"] if meta["index"] == current else None,
                    # Las puertas humanas que ocurren en esta fase del recorrido.
                    "gates": here,
                    "gates_pending": sum(1 for g in here if g["status"] == GATE_PENDING)})
    return out


def summary(task: dict, pipeline: dict, sla: dict | None = None) -> dict:
    """Resumen del journey de una vulnerabilidad (vista global y detalle)."""
    pos = position(task, pipeline)
    blockers = list(pos["blockers"])
    if sla and sla.get("overdue"):
        blockers.append("sla_overdue")
    elif sla and sla.get("due_soon"):
        blockers.append("sla_due_soon")
    deploy = pipeline["artifacts"]["deployment"]
    return {
        **pos,
        "blockers": blockers,
        "hitl": gate_rollup(gate_states(task, pipeline)),
        "resources": resource_rollup(pipeline),
        "rollback": pipeline.get("rollback", {}),
        "evidence": {
            "report_id": pipeline["artifacts"]["audit"]["report_id"],
            "evidences_count": pipeline["artifacts"]["audit"]["evidences_count"],
            "closed": task.get("status") == "remediated",
        },
        "change": {
            "number": deploy["itsm"]["number"],
            "type": deploy["itsm"]["type_label"],
            "state": deploy["itsm"]["state"],
            "requires_human": deploy["itsm"]["requires_human"],
        },
    }


def aggregate(summaries: list[dict]) -> dict:
    """Distribución de las vulnerabilidades a lo largo de las 8 fases."""
    phases = []
    for meta in phase_catalog():
        here = [s for s in summaries if s["phase"] == meta["id"]]
        resources = {"total": 0, "patched": 0, "pending": 0, "failed": 0, "excluded": 0}
        by_lane: dict[str, int] = {}
        blockers: dict[str, int] = {}
        for s in here:
            for key in resources:
                resources[key] += s["resources"][key]
            lane = s.get("lane", "standard")
            by_lane[lane] = by_lane.get(lane, 0) + 1
            for b in s["blockers"]:
                blockers[b] = blockers.get(b, 0) + 1
        gates_here = [g for g in gate_catalog() if g["phase"] == meta["id"]]
        gate_ids = {g["id"] for g in gates_here}
        phases.append({
            **meta,
            "count": len(here),
            "by_lane": by_lane,
            "blockers": blockers,
            "resources": resources,
            "rings": sorted({s["ring"] for s in here if s["ring"] is not None}),
            # Puertas humanas que ocurren en esta fase (capa transversal) y
            # cuántas de ellas esperan decisión ahora mismo.
            "gates": gates_here,
            "gates_pending": sum(
                1 for s in summaries
                if (s["hitl"].get("next") or {}).get("id") in gate_ids),
        })
    return {
        "phases": phases,
        "bands": [{"id": bid, "label": label} for bid, label in BANDS],
        "total": len(summaries),
        "hitl": {
            "pending": sum(s["hitl"]["pending"] for s in summaries),
            "pending_enforced": sum(s["hitl"]["pending_enforced"] for s in summaries),
            "done": sum(s["hitl"]["done"] for s in summaries),
            "total": sum(s["hitl"]["total"] for s in summaries),
            "tasks_awaiting": sum(1 for s in summaries if s["hitl"]["pending"]),
        },
    }
