"""Provider de restauración/rollback simulado (determinista).

Contiene la lógica del plan de rollback que antes vivía en
`engine.build_rollback_plan()` (que ahora delega aquí para compatibilidad).
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import PROVIDER_MOCK, Settings
from .base import (
    ExecutionStatus,
    ExecutionStep,
    ProviderError,
    RestoreExecution,
    RestoreRequest,
    TargetPolicyResult,
    iso_utc,
    utcnow,
)

REFERENCE_PREFIX = "mock-restore"


# ---------------------------------------------------------------------------
# Plan de rollback determinista (antes en engine.py)
# ---------------------------------------------------------------------------
def build_rollback_plan(task, impact):
    """Plan de rollback armado desde el inicio (contemplación del rollback)."""
    from .. import engine  # import diferido: engine delega en este módulo

    rng = engine._rng(task["id"] + "rbplan")
    prev = engine._prev_version(task)
    fixed = engine._fixed_version(prev)
    ci = task["ci_name"]
    comp = task.get("component", ci)
    if task["track"] == "C":
        strategy = "GitOps rollback (revisión previa + imagen firmada)"
        steps = [
            {"actor": "Devin", "tool": "Argo CD", "command": f"argocd app rollback {ci} <previous-revision>",
             "desc": f"Sincroniza la revisión estable anterior (imagen {ci}:{prev})."},
            {"actor": "Argo CD", "tool": "Helm", "command": f"kubectl rollout undo deploy/{ci}",
             "desc": "Revierte el rollout al ReplicaSet sano; 100% del tráfico a la imagen previa."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + smoke-test",
             "desc": "Verifica salud de los pods tras el rollback."},
        ]
        snapshot_ref = f"registry/{ci}:{prev}"
    elif task["track"] == "B":
        strategy = "artifact-redeploy (imagen previa)"
        steps = [
            {"actor": "Devin", "tool": "Helm", "command": f"helm rollback {ci} <previous-revision>",
             "desc": f"Redeploy de la imagen {ci}:{prev} (revisión estable anterior)."},
            {"actor": "GitHub Actions", "tool": "CI/CD", "command": f"deploy {ci}:{prev} --canary.weight=100",
             "desc": "Restablece el 100% del tráfico al artefacto sano."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + smoke-test",
             "desc": "Verifica salud tras el rollback."},
        ]
        snapshot_ref = f"registry/{ci}:{prev}"
    else:
        strategy = "snapshot-restore (VM / paquete)"
        steps = [
            {"actor": "Devin", "tool": "Ansible", "command": f"package downgrade {comp} {fixed} → {prev}",
             "desc": f"Restaura la versión previa {comp}-{prev}."},
            {"actor": "Ansible", "tool": "IaC", "command": "restore snapshot <pre-patch>",
             "desc": "Restaura el snapshot tomado antes del parche si el downgrade no basta."},
            {"actor": "Ansible", "tool": "OS", "command": "systemctl restart affected-services",
             "desc": "Reinicia servicios y valida arranque."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + synthetic-probe",
             "desc": "Verifica salud tras el rollback."},
        ]
        snapshot_ref = f"snap-pre-{task['cve'].lower()}"
    return {
        "strategy": strategy,
        "snapshot_ref": snapshot_ref,
        "target_version": prev,
        "from_version": fixed,
        "rto_minutes": rng.choice([5, 8, 10, 15]),
        "auto_trigger": "fallo de post-checks / breach de health-check tras un anillo",
        "steps": steps,
        "tested_in_lab": True,
    }


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------
def _encode_reference(job_id: str, started: datetime) -> str:
    return f"{REFERENCE_PREFIX}:{job_id}:{int(started.timestamp())}"


def decode_reference(reference: str) -> tuple[str, datetime]:
    parts = (reference or "").split(":")
    if len(parts) != 3 or parts[0] != REFERENCE_PREFIX:
        raise ProviderError("PROVIDER_REFERENCE_INVALID",
                            "La referencia de ejecución no pertenece al provider mock de restauración.")
    try:
        started = datetime.fromtimestamp(int(parts[2]), tz=timezone.utc)
    except (ValueError, OSError) as exc:
        raise ProviderError("PROVIDER_REFERENCE_INVALID",
                            "La referencia de ejecución mock es ilegible.") from exc
    return parts[1], started


class MockRestoreProvider:
    """Restauración simulada: mantiene el rollback demostrable de la demo."""

    name = PROVIDER_MOCK

    def __init__(self, settings: Settings, now_fn=utcnow):
        self._settings = settings
        self._now = now_fn

    def validate_target(self, request: RestoreRequest) -> TargetPolicyResult:
        target = request.primary_target()
        checks = (
            {"check": "Objetivo resuelto", "ok": True,
             "detail": f"Objetivo lógico {target.logical_target_id} ({target.name or '-'})."},
            {"check": "Plan de rollback probado en laboratorio", "ok": True,
             "detail": "El plan de rollback se validó en el anillo de laboratorio (simulado)."},
        )
        return TargetPolicyResult(allowed=True, checks=checks, target=target,
                                  message="Objetivo válido para restauración simulada.")

    def _steps(self, request: RestoreRequest) -> tuple[ExecutionStep, ...]:
        task = request.task_snapshot
        if not task:
            raise ProviderError("REQUEST_INCOMPLETE",
                                "La petición no incluye el contexto de la tarea.")
        plan = build_rollback_plan(task, {"nodes": [], "edges": []})
        return tuple(
            ExecutionStep(seq=i + 1, actor=s["actor"], tool=s["tool"], command=s["command"],
                          output=s["desc"], status="ok",
                          why=f"Restauración ({request.restore_kind}): {request.reason}")
            for i, s in enumerate(plan["steps"]))

    def start(self, request: RestoreRequest, idempotency_key: str) -> RestoreExecution:
        started = self._now()
        if request.dry_run:
            planned = tuple(
                ExecutionStep(seq=s.seq, actor=s.actor, tool=s.tool, command=s.command,
                              output="[dry-run] no ejecutado", status="planned", why=s.why)
                for s in self._steps(request))
            return RestoreExecution(
                provider=self.name, provider_reference=f"dryrun:{request.job_id}",
                status=ExecutionStatus.DRY_RUN, dry_run=True, steps=planned,
                restored_version=request.target_version, started_at=iso_utc(started),
                completed_at=iso_utc(started),
                detail="Restauración en dry-run: no se aplica ningún cambio.")
        return RestoreExecution(
            provider=self.name, provider_reference=_encode_reference(request.job_id, started),
            status=ExecutionStatus.RUNNING, dry_run=False, steps=(),
            restored_version=request.target_version, started_at=iso_utc(started),
            detail=f"Restauración simulada iniciada (idempotency-key {idempotency_key[:12]}…).")

    def poll(self, provider_reference: str, request: RestoreRequest | None = None) -> RestoreExecution:
        if request is None:
            raise ProviderError("REQUEST_INCOMPLETE",
                                "El provider mock necesita la petición original para reconstruir el plan.")
        if provider_reference.startswith("dryrun:"):
            return self.start(request, "replay")
        _job_id, started = decode_reference(provider_reference)
        duration = max(0, self._settings.mock_restore_duration_seconds)
        elapsed = (self._now() - started).total_seconds()
        done = elapsed >= duration
        steps = self._steps(request) if done else ()
        return RestoreExecution(
            provider=self.name, provider_reference=provider_reference,
            status=ExecutionStatus.SUCCEEDED if done else ExecutionStatus.RUNNING,
            dry_run=False, steps=steps, restored_version=request.target_version,
            started_at=iso_utc(started),
            completed_at=iso_utc(self._now()) if done else None,
            detail="Restauración simulada completada." if done else "Restauración simulada en curso.")
