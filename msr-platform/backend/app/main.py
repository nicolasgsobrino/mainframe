"""API FastAPI de la plataforma Machine Speed Remediation (demo)."""
from __future__ import annotations

import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import engine
from .config import get_settings
from .errors import DomainError, NotFoundError, ValidationError
from .reconciler import JobReconciler
from .store import STORE

log = logging.getLogger("msr.api")
settings = get_settings()

RECONCILER = JobReconciler(STORE, settings.reconciler_interval_seconds,
                           enabled=settings.reconciler_enabled)


def _reconcile_lab_on_startup() -> None:
    """Hook de arranque opcional (`MSR_LAB_RECONCILE_ON_STARTUP`).

    Está desactivado por defecto: un reset es destructivo y no debe dispararse
    cada vez que se reinicia una réplica. La forma recomendada de dejar el
    laboratorio listo en un despliegue es el hook de ejecución única
    `python -m app.lab_hook`, que toma el mismo lock durable.
    """
    try:
        result = STORE.ensure_lab_ready(reason="startup")
        log.info("lab_reconcile_on_startup state=%s action=%s instance=%s",
                 result.get("state"), result.get("action"), result.get("instance_id"))
    except DomainError as exc:
        log.error("lab_reconcile_on_startup falló code=%s correlation_id=%s",
                  exc.code, exc.correlation_id)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # El estado funcional se reconstruye desde SQLite antes de servir tráfico.
    STORE.rehydrate_pipeline_state()
    RECONCILER.start()
    if settings.lab_reconcile_on_startup:
        # En un hilo aparte: la API sirve tráfico mientras el laboratorio se
        # reconcilia, y el lock durable evita que dos réplicas lo hagan a la vez.
        threading.Thread(target=_reconcile_lab_on_startup, name="lab-reconcile",
                         daemon=True).start()
    try:
        yield
    finally:
        await RECONCILER.stop()


app = FastAPI(title="Machine Speed Remediation Platform", version="1.1.0",
              lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


@app.exception_handler(DomainError)
def domain_error_handler(request: Request, exc: DomainError):
    """Formato de error uniforme: {"error": {code, message, correlation_id}}."""
    log.warning("domain_error code=%s correlation_id=%s path=%s",
                exc.code, exc.correlation_id, request.url.path)
    return JSONResponse(status_code=exc.http_status, content=exc.to_payload())


def _idempotency_key(provided: str | None, tid: str, suffix: str) -> str:
    """Clave efectiva: la del cliente o una temporal única por petición."""
    return provided or f"transient:{suffix}:{tid}:{uuid.uuid4().hex}"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/execution")
def execution_config():
    """Configuración de ejecución visible por la UI (sin secretos)."""
    return {
        "patch_provider": STORE.patch_provider.name,
        "restore_provider": STORE.restore_provider.name,
        "dry_run": settings.effective_dry_run(STORE.patch_provider.name),
        "poll_interval_seconds": settings.job_poll_interval_seconds,
        "region": settings.aws_region or None,
        "mode": settings.execution_mode(),
        "strict_policy": settings.real_aws_execution(),
        "reconciler": RECONCILER.status(),
    }


@app.get("/api/overview")
def overview():
    return STORE.overview()


@app.get("/api/tasks")
def tasks():
    return STORE.list_tasks()


@app.get("/api/tasks/{tid}")
def task_detail(tid: str):
    d = STORE.task_detail(tid)
    if not d:
        raise HTTPException(404, "task not found")
    return d


@app.post("/api/tasks/{tid}/approve")
def approve(tid: str, response: Response,
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    """Fases 1-5: 200 síncrono. Fase de despliegue: 202 con el job creado."""
    if tid not in STORE.pipelines:
        raise NotFoundError(f"La tarea {tid} no existe.")
    phase_id = engine.PHASE_IDS[STORE.pipelines[tid]["phase_index"]]
    deploying = phase_id == "deployment"
    d = STORE.approve_phase(tid, _idempotency_key(idempotency_key, tid, "approve"))
    if not d:
        raise NotFoundError(f"La tarea {tid} no existe.")
    if deploying:
        response.status_code = status.HTTP_202_ACCEPTED
    return d


@app.get("/api/patch-jobs/{job_id}")
def patch_job(job_id: str):
    return STORE.get_job(job_id).as_dict()


@app.get("/api/tasks/{tid}/patch-jobs")
def task_patch_jobs(tid: str):
    return [j.as_dict() for j in STORE.list_task_jobs(tid)]


@app.post("/api/patch-jobs/{job_id}/cancel")
def cancel_patch_job(job_id: str):
    return STORE.cancel_job(job_id).as_dict()


class AdminResolveBody(BaseModel):
    state: str
    note: str
    actor: str = "admin"


@app.post("/api/patch-jobs/{job_id}/admin-resolve")
def admin_resolve_job(job_id: str, body: AdminResolveBody):
    """Cierre manual de un job cuyo estado remoto no ha podido confirmarse."""
    return STORE.admin_resolve_job(job_id, body.state, body.note, actor=body.actor).as_dict()


class LabTargetBody(BaseModel):
    logical_lab_id: str
    current_instance_id: str | None = None
    account_id: str | None = None
    region: str | None = None
    vulnerable_ami_id: str | None = None
    launch_template_id: str | None = None
    launch_template_version: str | None = None
    expected_vulnerable_package: str | None = None
    expected_vulnerable_version: str | None = None
    required_tags: dict[str, str] = {}


@app.get("/api/lab-targets")
def lab_targets():
    """Laboratorios reutilizables registrados (modelo; sin operaciones EC2)."""
    return STORE.list_lab_targets()


@app.get("/api/lab-targets/{logical_lab_id}")
def lab_target(logical_lab_id: str):
    return STORE.get_lab_target(logical_lab_id)


@app.post("/api/lab-targets")
def register_lab_target(body: LabTargetBody):
    return STORE.register_lab_target(body.model_dump())


# --- Laboratorio EC2 reseteable (fase 2) ---------------------------------
# El Instance ID nunca se acepta desde el cliente: sólo el identificador
# lógico del laboratorio, que se resuelve por tags en el backend.
@app.get("/api/labs/{logical_lab_id}")
def lab_status(logical_lab_id: str):
    """Estado del laboratorio: instancia resuelta, advisory, modo y job activo."""
    return STORE.lab_snapshot(logical_lab_id)


@app.post("/api/labs/{logical_lab_id}/validate")
def lab_validate(logical_lab_id: str):
    """Validación de sólo lectura: no inicia ninguna Automation ni muta nada."""
    return STORE.validate_lab(logical_lab_id)


class LabResetBody(BaseModel):
    confirmed: bool = False


@app.post("/api/labs/{logical_lab_id}/reset", status_code=status.HTTP_202_ACCEPTED)
def lab_reset(logical_lab_id: str, body: LabResetBody | None = None,
              idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    """Recrea la instancia vulnerable (`reset_lab`); no es un rollback.

    En `aws-real` la operación destruye una instancia EC2 real, así que exige
    confirmación humana explícita en el cuerpo de la petición.
    """
    if settings.real_aws_execution() and not (body is not None and body.confirmed):
        raise ValidationError(
            "El reset real termina la instancia EC2 del laboratorio: envía "
            "confirmed=true para confirmarlo explícitamente.",
            code="LAB_RESET_CONFIRMATION_REQUIRED")
    job = STORE.start_lab_reset_job(
        logical_lab_id,
        idempotency_key=_idempotency_key(idempotency_key, logical_lab_id, "lab-reset"))
    return {"job": job.as_dict(), "lab": STORE.get_lab_target(logical_lab_id)}


@app.get("/api/labs/{logical_lab_id}/reconciliation")
def lab_reconciliation(logical_lab_id: str):
    """Estado del reconciliador del laboratorio (sin llamadas a AWS)."""
    STORE.get_lab_target(logical_lab_id)
    return STORE.lab_reconciliation_status(logical_lab_id)


@app.post("/api/labs/{logical_lab_id}/reconcile")
def lab_reconcile(logical_lab_id: str, body: LabResetBody | None = None):
    """`ensure_lab_ready`: deja el laboratorio listo para una demostración nueva.

    En `aws-real` un reset destructivo exige confirmación humana explícita
    (`confirmed: true`); sin ella la operación se limita a informar de lo que
    haría. En `aws-dry-run` nunca se inicia ninguna Automation.
    """
    STORE.get_lab_target(logical_lab_id)
    confirmed = bool(body.confirmed) if body is not None else False
    return STORE.ensure_lab_ready(logical_lab_id, confirmed=confirmed, reason="api")


@app.get("/api/labs/{logical_lab_id}/jobs")
def lab_jobs(logical_lab_id: str):
    """Historial de jobs del laboratorio (parcheos y resets)."""
    return STORE.lab_jobs(logical_lab_id)


class RingPreapproveBody(BaseModel):
    approver: str | None = None
    note: str | None = None


class RingAssetsBody(BaseModel):
    excluded: list[str] = []


@app.post("/api/tasks/{tid}/rings/{ring_no}/preapprove")
def preapprove_ring(tid: str, ring_no: int, body: RingPreapproveBody | None = None):
    body = body or RingPreapproveBody()
    d = STORE.preapprove_ring(tid, ring_no, approver=body.approver, note=body.note)
    if not d:
        raise HTTPException(404, "task not found")
    return d


@app.post("/api/tasks/{tid}/rings/{ring_no}/assets")
def update_ring_assets(tid: str, ring_no: int, body: RingAssetsBody):
    d = STORE.update_ring_assets(tid, ring_no, body.excluded)
    if not d:
        raise HTTPException(404, "task not found")
    return d


@app.post("/api/tasks/{tid}/rollback")
def rollback(tid: str, response: Response,
             idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    d = STORE.rollback(tid, trigger="manual",
                       idempotency_key=_idempotency_key(idempotency_key, tid, "rollback"))
    if not d:
        raise NotFoundError(f"La tarea {tid} no existe.")
    if d.get("active_job"):
        response.status_code = status.HTTP_202_ACCEPTED
    return d


@app.post("/api/tasks/{tid}/simulate-incident")
def simulate_incident(tid: str):
    d = STORE.simulate_incident(tid)
    if not d:
        raise HTTPException(404, "task not found")
    return d


@app.get("/api/cmdb")
def cmdb():
    """Resumen de CMDB estandarizada + servicios (no vuelca los ~10k CIs)."""
    services = [c for c in STORE.cis if c["ci_class"] == "business_service"]
    return {"summary": STORE.cmdb_summary(), "services": services}


@app.get("/api/cmdb/summary")
def cmdb_summary():
    return STORE.cmdb_summary()


@app.get("/api/cmdb/cis")
def cmdb_cis(cls: str = "all", track: str = "all", crit: str = "all",
             q: str = "", limit: int = 100, offset: int = 0):
    return STORE.cmdb_cis(cls=cls, track=track, crit=crit, q=q, limit=limit, offset=offset)


@app.get("/api/cmdb/cis/{ci_id}/raw")
def cmdb_ci_raw(ci_id: str):
    """Registro nativo de ServiceNow (Table API) + mapeo al modelo interno."""
    raw = STORE.cmdb_ci_raw(ci_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="CI no encontrado")
    return raw


@app.get("/api/cmdb/tables")
def cmdb_tables():
    """Manifiesto de la CMDB versionada en el repo (tablas ServiceNow + conteos)."""
    return STORE.cmdb_tables()


@app.get("/api/cmdb/graph/{service_id}")
def cmdb_graph(service_id: str):
    return STORE.cmdb_graph(service_id)


@app.get("/api/catalog")
def catalog():
    return STORE.catalog


@app.get("/api/vulnerable-items")
def vitems():
    return list(STORE.vulnerable_items.values())


@app.get("/api/findings")
def findings():
    return STORE.findings


@app.get("/api/activity")
def activity():
    return STORE.activity


@app.get("/api/services")
def services():
    """Estado de integración de los servicios simulados (control plane + ejecutores)."""
    return [
        {"name": "ServiceNow Vulnerability Response", "role": "Plano de control", "status": "connected", "type": "control", "detail": "Ingesta, VI, Remediation Tasks"},
        {"name": "ServiceNow CMDB / CSDM", "role": "Contexto", "status": "connected", "type": "control", "detail": f"{len(STORE.cis):,} CIs estandarizados (CSDM), relaciones e Impact Graph"},
        {"name": "ServiceNow Change Management", "role": "Gobierno del cambio", "status": "connected", "type": "control", "detail": "CAB, standard/normal/emergency"},
        {"name": "Devin Agent", "role": "Capa agente", "status": "active", "type": "agent", "detail": "Blast radius, MVT, tests, IaC, PR, informe"},
        {"name": "Qualys VMDR", "role": "Scanner infra", "status": "connected", "type": "source", "detail": "Fuente Track A"},
        {"name": "Tenable.io", "role": "Scanner infra", "status": "connected", "type": "source", "detail": "Fuente Track A"},
        {"name": "Snyk (SCA/SBOM)", "role": "Dependencias", "status": "connected", "type": "source", "detail": "Fuente Track B"},
        {"name": "Wiz / Trivy (contenedores)", "role": "Scanner cloud-native", "status": "connected", "type": "source", "detail": "Fuente Track C (imágenes, IaC, K8s)"},
        {"name": "Ansible / BigFix / SCCM", "role": "Ejecución Carril A (infra)", "status": "connected", "type": "executor", "detail": "Aplica parches infra"},
        {"name": "GitHub Actions (CI/CD)", "role": "Ejecución Carril B (app)", "status": "connected", "type": "executor", "detail": "PR → build → test → deploy"},
        {"name": "Argo CD + Helm + Registry", "role": "Ejecución Carril C (contenedores)", "status": "connected", "type": "executor", "detail": "Rebuild imagen → sync GitOps → rollout"},
        {"name": "Terraform / OpenTofu", "role": "IaC labs", "status": "connected", "type": "executor", "detail": "Labs efímeros (prototipo)"},
    ]


@app.post("/api/reset")
def reset():
    STORE.reset()
    return {"status": "reset"}


# --- Servir el frontend build (producción) ---
_DIST = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        idx = os.path.join(_DIST, "index.html")
        target = os.path.join(_DIST, full_path)
        if full_path and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(idx)
