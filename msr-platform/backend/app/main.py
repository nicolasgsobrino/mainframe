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


@app.get("/api/cmdb")
def cmdb():
    return {"cis": STORE.cis, "edges": STORE.edges}


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
        {"name": "ServiceNow CMDB / CSDM", "role": "Contexto", "status": "connected", "type": "control", "detail": f"{len(STORE.cis)} CIs, relaciones e Impact Graph"},
        {"name": "ServiceNow Change Management", "role": "Gobierno del cambio", "status": "connected", "type": "control", "detail": "CAB, standard/normal/emergency"},
        {"name": "Devin Agent", "role": "Capa agente", "status": "active", "type": "agent", "detail": "Blast radius, MVT, tests, IaC, PR, informe"},
        {"name": "Qualys VMDR", "role": "Scanner infra", "status": "connected", "type": "source", "detail": "Fuente Track A"},
        {"name": "Tenable.io", "role": "Scanner infra", "status": "connected", "type": "source", "detail": "Fuente Track A"},
        {"name": "Snyk (SCA/SBOM)", "role": "Dependencias", "status": "connected", "type": "source", "detail": "Fuente Track B"},
        {"name": "Ansible / BigFix / SCCM", "role": "Ejecución Track A", "status": "connected", "type": "executor", "detail": "Aplica parches infra"},
        {"name": "GitHub Actions (CI/CD)", "role": "Ejecución Track B", "status": "connected", "type": "executor", "detail": "PR → build → test → deploy"},
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
