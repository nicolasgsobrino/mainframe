"""Provider de restauración/rollback simulado (determinista).

Contiene la lógica del plan de rollback que antes vivía en
`engine.build_rollback_plan()` (que ahora delega aquí para compatibilidad).
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import PROVIDER_MOCK, Settings
from .base import (
    RESTORE_KIND_RESET_LAB,
    ExecutionStatus,
    ExecutionStep,
    ProviderError,
    RestoreExecution,
    RestoreRequest,
    TargetPolicyResult,
    iso_utc,
    synthetic_instance_id,
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
        strategy = "GitOps rollback (previous revision + signed image)"
        steps = [
            {"actor": "Devin", "tool": "Argo CD", "command": f"argocd app rollback {ci} <previous-revision>",
             "desc": f"Syncs the previous stable revision (image {ci}:{prev})."},
            {"actor": "Argo CD", "tool": "Helm", "command": f"kubectl rollout undo deploy/{ci}",
             "desc": "Reverts the rollout to the healthy ReplicaSet; 100% of traffic to the previous image."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + smoke-test",
             "desc": "Checks pod health after the rollback."},
        ]
        snapshot_ref = f"registry/{ci}:{prev}"
    elif task["track"] == "B":
        strategy = "artifact-redeploy (previous image)"
        steps = [
            {"actor": "Devin", "tool": "Helm", "command": f"helm rollback {ci} <previous-revision>",
             "desc": f"Redeploys image {ci}:{prev} (previous stable revision)."},
            {"actor": "GitHub Actions", "tool": "CI/CD", "command": f"deploy {ci}:{prev} --canary.weight=100",
             "desc": "Restores 100% of traffic to the healthy artefact."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + smoke-test",
             "desc": "Checks health after the rollback."},
        ]
        snapshot_ref = f"registry/{ci}:{prev}"
    else:
        strategy = "snapshot-restore (VM / package)"
        steps = [
            {"actor": "Devin", "tool": "Ansible", "command": f"package downgrade {comp} {fixed} → {prev}",
             "desc": f"Restores the previous version {comp}-{prev}."},
            {"actor": "Ansible", "tool": "IaC", "command": "restore snapshot <pre-patch>",
             "desc": "Restores the snapshot taken before the patch if the downgrade is not enough."},
            {"actor": "Ansible", "tool": "OS", "command": "systemctl restart affected-services",
             "desc": "Restarts services and validates startup."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + synthetic-probe",
             "desc": "Checks health after the rollback."},
        ]
        snapshot_ref = f"snap-pre-{task['cve'].lower()}"
    return {
        "strategy": strategy,
        "snapshot_ref": snapshot_ref,
        "target_version": prev,
        "from_version": fixed,
        "rto_minutes": rng.choice([5, 8, 10, 15]),
        "auto_trigger": "post-check failure / health-check breach after a ring",
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
                            "The execution reference does not belong to the mock restore provider.")
    try:
        started = datetime.fromtimestamp(int(parts[2]), tz=timezone.utc)
    except (ValueError, OSError) as exc:
        raise ProviderError("PROVIDER_REFERENCE_INVALID",
                            "The mock execution reference is unreadable.") from exc
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
            {"check": "Target resolved", "ok": True,
             "detail": f"Logical target {target.logical_target_id} ({target.name or '-'})."},
            {"check": "Rollback plan tested in the lab", "ok": True,
             "detail": "The rollback plan was validated in the lab ring (simulated)."},
        )
        return TargetPolicyResult(allowed=True, checks=checks, target=target,
                                  message="Target valid for simulated restore.")

    @staticmethod
    def _reset_instance_id(request: RestoreRequest) -> str | None:
        """Instance ID de la instancia recreada (simulada) tras un reset."""
        if request.restore_kind != RESTORE_KIND_RESET_LAB:
            return None
        return synthetic_instance_id(request.primary_target().logical_target_id,
                                     request.job_id)

    def _reset_steps(self, request: RestoreRequest) -> tuple[ExecutionStep, ...]:
        """Plan simulado del reset: terminar la instancia y recrearla desde el LT."""
        target = request.primary_target()
        new_instance_id = self._reset_instance_id(request) or ""
        plan = [
            ("validate mandatory tags", f"describe-instances {target.instance_id or '-'}",
             "Tags msr-poc/msr-lab-id/msr-resettable verified before destroying anything."),
            ("terminate the current instance", f"terminate-instances {target.instance_id or '-'}",
             "Lab instance terminated (simulated)."),
            ("recreate from the Launch Template", "run-instances --launch-template <pinned version>",
             f"New vulnerable instance {new_instance_id} (simulated)."),
            ("wait for the managed node and health check", "describe-instance-information + /health",
             "The new instance responds and is back in a vulnerable state."),
        ]
        return tuple(
            ExecutionStep(seq=i + 1, actor="msr-platform", tool="lab reset (simulated)",
                          command=command, output=output, status="ok",
                          why=f"Lab reset: {request.reason}")
            for i, (_name, command, output) in enumerate(plan))

    def _steps(self, request: RestoreRequest) -> tuple[ExecutionStep, ...]:
        if request.restore_kind == RESTORE_KIND_RESET_LAB:
            return self._reset_steps(request)
        task = request.task_snapshot
        if not task:
            raise ProviderError("REQUEST_INCOMPLETE",
                                "The request does not include the task context.")
        plan = build_rollback_plan(task, {"nodes": [], "edges": []})
        return tuple(
            ExecutionStep(seq=i + 1, actor=s["actor"], tool=s["tool"], command=s["command"],
                          output=s["desc"], status="ok",
                          why=f"Restore ({request.restore_kind}): {request.reason}")
            for i, s in enumerate(plan["steps"]))

    def start(self, request: RestoreRequest, idempotency_key: str) -> RestoreExecution:
        started = self._now()
        if request.dry_run:
            planned = tuple(
                ExecutionStep(seq=s.seq, actor=s.actor, tool=s.tool, command=s.command,
                              output="[dry-run] not executed", status="planned", why=s.why)
                for s in self._steps(request))
            return RestoreExecution(
                provider=self.name, provider_reference=f"dryrun:{request.job_id}",
                status=ExecutionStatus.DRY_RUN, dry_run=True, steps=planned,
                restored_version=request.target_version, started_at=iso_utc(started),
                new_instance_id=None,
                completed_at=iso_utc(started),
                detail="Dry-run restore: no change is applied.")
        return RestoreExecution(
            provider=self.name, provider_reference=_encode_reference(request.job_id, started),
            status=ExecutionStatus.RUNNING, dry_run=False, steps=(),
            restored_version=request.target_version, started_at=iso_utc(started),
            detail=f"Simulated restore started (idempotency-key {idempotency_key[:12]}…).")

    def poll(self, provider_reference: str, request: RestoreRequest | None = None) -> RestoreExecution:
        if request is None:
            raise ProviderError("REQUEST_INCOMPLETE",
                                "The mock provider needs the original request to rebuild the plan.")
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
            new_instance_id=self._reset_instance_id(request) if done else None,
            started_at=iso_utc(started),
            completed_at=iso_utc(self._now()) if done else None,
            detail="Simulated restore completed." if done else "Simulated restore in progress.")
