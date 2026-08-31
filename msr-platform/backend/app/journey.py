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
    ("asset_identification", "Identificación de activos afectados",
     "Affected asset identification", "demand_risk", False),
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
    if task.get("status") == "remediated":
        phase_id, ring, blockers = "evidence_closure", None, []
    elif pipeline_phase in _PIPELINE_TO_JOURNEY:
        phase_id, ring = _PIPELINE_TO_JOURNEY[pipeline_phase]
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
        out.append({**meta, "status": status,
                    "ring": pos["ring"] if meta["index"] == current else None})
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
        phases.append({
            **meta,
            "count": len(here),
            "by_lane": by_lane,
            "blockers": blockers,
            "resources": resources,
            "rings": sorted({s["ring"] for s in here if s["ring"] is not None}),
        })
    return {
        "phases": phases,
        "bands": [{"id": bid, "label": label} for bid, label in BANDS],
        "total": len(summaries),
    }
