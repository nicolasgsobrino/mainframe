"""API FastAPI de la plataforma Machine Speed Remediation (demo)."""
from __future__ import annotations
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .store import STORE

app = FastAPI(title="Machine Speed Remediation Platform", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


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
def approve(tid: str):
    d = STORE.approve_phase(tid)
    if not d:
        raise HTTPException(404, "task not found")
    return d


@app.post("/api/tasks/{tid}/rollback")
def rollback(tid: str):
    d = STORE.rollback(tid, trigger="manual")
    if not d:
        raise HTTPException(404, "task not found")
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
