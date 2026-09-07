"""Modelo de job de parcheo/restauración y su máquina de estados.

Los jobs son la unidad duradera que sobrevive a un reinicio del backend: el
plano de control nunca controla la ejecución con hilos o workers locales, sino
que reconcilia el estado consultando al provider (`poll`).
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum

from .providers.base import ExecutionStatus, ExecutionStep, Target, iso_utc, utcnow


class JobType(str, Enum):
    PATCH = "patch"
    ROLLBACK = "rollback"
    RESET_LAB = "reset_lab"

    @property
    def mutating(self) -> bool:
        return True


class JobState(str, Enum):
    QUEUED = "queued"
    VALIDATING = "validating"
    DRY_RUN = "dry_run"
    STARTING = "starting"
    RUNNING = "running"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    RESTORE_QUEUED = "restore_queued"
    RESTORING = "restoring"
    RESTORED = "restored"
    RESTORE_FAILED = "restore_failed"
    TIMED_OUT = "timed_out"
    # Estados de seguridad: el timeout es local, la ejecución remota puede seguir
    # viva. Ninguno es terminal, de modo que el lock del objetivo NO se libera.
    TIMEOUT_PENDING_CONFIRMATION = "timeout_pending_confirmation"
    REMOTE_STATUS_UNKNOWN = "remote_status_unknown"
    STOP_REQUESTED = "stop_requested"


TERMINAL_STATES: frozenset[JobState] = frozenset({
    JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED,
    JobState.RESTORED, JobState.RESTORE_FAILED, JobState.TIMED_OUT,
    JobState.DRY_RUN,
})
ACTIVE_STATES: frozenset[JobState] = frozenset(set(JobState) - set(TERMINAL_STATES))
# Estados en los que el resultado remoto no está confirmado: el job sigue
# ocupando su objetivo y sólo puede resolverse con confirmación de AWS o con una
# reconciliación administrativa auditada.
UNCONFIRMED_STATES: frozenset[JobState] = frozenset({
    JobState.TIMEOUT_PENDING_CONFIRMATION, JobState.REMOTE_STATUS_UNKNOWN,
    JobState.STOP_REQUESTED,
})

_UNCONFIRMED_EXITS: frozenset[JobState] = frozenset({
    JobState.RUNNING, JobState.RESTORING, JobState.VERIFYING, JobState.SUCCEEDED,
    JobState.FAILED, JobState.CANCELLING, JobState.CANCELLED, JobState.RESTORED,
    JobState.RESTORE_FAILED, JobState.TIMED_OUT, JobState.TIMEOUT_PENDING_CONFIRMATION,
    JobState.REMOTE_STATUS_UNKNOWN, JobState.STOP_REQUESTED,
})

# Transiciones permitidas. Cualquier otra combinación es un error de programación.
ALLOWED_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.VALIDATING, JobState.CANCELLING, JobState.FAILED,
                                JobState.TIMED_OUT, JobState.RESTORE_QUEUED}),
    JobState.VALIDATING: frozenset({JobState.DRY_RUN, JobState.STARTING, JobState.RUNNING,
                                    JobState.RESTORING, JobState.FAILED,
                                    JobState.RESTORE_FAILED, JobState.CANCELLING,
                                    JobState.TIMED_OUT}),
    JobState.STARTING: frozenset({JobState.RUNNING, JobState.VERIFYING, JobState.SUCCEEDED,
                                  JobState.FAILED, JobState.CANCELLING, JobState.TIMED_OUT,
                                  JobState.RESTORING, JobState.TIMEOUT_PENDING_CONFIRMATION,
                                  JobState.REMOTE_STATUS_UNKNOWN}),
    JobState.RUNNING: frozenset({JobState.RUNNING, JobState.VERIFYING, JobState.SUCCEEDED,
                                 JobState.FAILED, JobState.CANCELLING, JobState.TIMED_OUT,
                                 JobState.RESTORING, JobState.TIMEOUT_PENDING_CONFIRMATION,
                                 JobState.REMOTE_STATUS_UNKNOWN}),
    JobState.VERIFYING: frozenset({JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLING,
                                   JobState.TIMED_OUT, JobState.TIMEOUT_PENDING_CONFIRMATION,
                                   JobState.REMOTE_STATUS_UNKNOWN}),
    JobState.CANCELLING: frozenset({JobState.CANCELLED, JobState.FAILED, JobState.SUCCEEDED,
                                    JobState.TIMED_OUT, JobState.STOP_REQUESTED,
                                    JobState.REMOTE_STATUS_UNKNOWN,
                                    JobState.TIMEOUT_PENDING_CONFIRMATION}),
    JobState.RESTORE_QUEUED: frozenset({JobState.VALIDATING, JobState.RESTORING, JobState.DRY_RUN,
                                        JobState.RESTORE_FAILED, JobState.TIMED_OUT}),
    JobState.RESTORING: frozenset({JobState.RESTORING, JobState.RESTORED, JobState.RESTORE_FAILED,
                                   JobState.TIMED_OUT, JobState.TIMEOUT_PENDING_CONFIRMATION,
                                   JobState.REMOTE_STATUS_UNKNOWN}),
    # Desde un estado no confirmado sólo se sale con información del ejecutor
    # remoto (o con una resolución administrativa registrada como evento).
    JobState.TIMEOUT_PENDING_CONFIRMATION: _UNCONFIRMED_EXITS,
    JobState.REMOTE_STATUS_UNKNOWN: _UNCONFIRMED_EXITS,
    JobState.STOP_REQUESTED: _UNCONFIRMED_EXITS,
    # Estados terminales: sin salidas.
    JobState.SUCCEEDED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
    JobState.RESTORED: frozenset(),
    JobState.RESTORE_FAILED: frozenset(),
    JobState.TIMED_OUT: frozenset(),
    JobState.DRY_RUN: frozenset(),
}


class InvalidTransition(ValueError):
    """Transición de estado no permitida por la máquina de estados."""


def is_terminal(state: JobState) -> bool:
    return state in TERMINAL_STATES


def can_transition(current: JobState, new: JobState) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())


def assert_transition(current: JobState, new: JobState) -> None:
    if not can_transition(current, new):
        raise InvalidTransition(f"transition not allowed: {current.value} → {new.value}")


def state_for_execution(status: ExecutionStatus, job_type: JobType) -> JobState:
    """Traduce el estado reportado por un provider al estado interno del job."""
    restore = job_type in (JobType.ROLLBACK, JobType.RESET_LAB)
    if status is ExecutionStatus.DRY_RUN:
        return JobState.DRY_RUN
    if status in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING):
        return JobState.RESTORING if restore else JobState.RUNNING
    if status is ExecutionStatus.SUCCEEDED:
        return JobState.RESTORED if restore else JobState.SUCCEEDED
    if status is ExecutionStatus.FAILED:
        return JobState.RESTORE_FAILED if restore else JobState.FAILED
    if status is ExecutionStatus.CANCELLING:
        return JobState.CANCELLING
    if status is ExecutionStatus.CANCELLED:
        return JobState.CANCELLED
    if status is ExecutionStatus.TIMED_OUT:
        return JobState.TIMED_OUT
    # Estado desconocido: se trata defensivamente como "en curso".
    return JobState.RESTORING if restore else JobState.RUNNING


def new_job_id() -> str:
    return f"job-{uuid.uuid4().hex[:16]}"


def new_correlation_id() -> str:
    return f"corr-{uuid.uuid4().hex[:16]}"


@dataclass(slots=True)
class JobEvent:
    job_id: str
    state: str
    message: str
    created_at: datetime = field(default_factory=utcnow)
    actor: str = "msr-platform"
    id: int | None = None

    def as_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = iso_utc(self.created_at)
        return data


@dataclass(slots=True)
class PatchJob:
    """Job persistido. `state` sólo debe cambiar mediante `transition_to`."""

    id: str
    job_type: JobType
    task_id: str
    ring_number: int
    provider: str
    state: JobState = JobState.QUEUED
    dry_run: bool = True
    provider_reference: str | None = None
    correlation_id: str = field(default_factory=new_correlation_id)
    idempotency_key: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_payload: dict = field(default_factory=dict)
    result_payload: dict = field(default_factory=dict)
    targets: tuple[Target, ...] = ()
    events: tuple[JobEvent, ...] = ()

    # ------------------------------------------------------------------
    @property
    def terminal(self) -> bool:
        return is_terminal(self.state)

    @property
    def active(self) -> bool:
        return not self.terminal

    @property
    def unconfirmed(self) -> bool:
        """El resultado remoto no está confirmado: el lock del objetivo sigue tomado."""
        return self.state in UNCONFIRMED_STATES

    def transition_to(self, new_state: JobState, *, error_code: str | None = None,
                      error_message: str | None = None) -> None:
        assert_transition(self.state, new_state)
        self.state = new_state
        self.updated_at = utcnow()
        if (new_state in (JobState.STARTING, JobState.RUNNING, JobState.RESTORING)
                and self.started_at is None):
            self.started_at = self.updated_at
        if is_terminal(new_state):
            self.completed_at = self.updated_at
        if error_code:
            self.error_code = error_code
        if error_message:
            self.error_message = error_message[:2000]

    def steps(self) -> list[dict]:
        return list(self.result_payload.get("steps") or [])

    def set_steps(self, steps: tuple[ExecutionStep, ...] | list[dict]) -> None:
        self.result_payload["steps"] = [
            s.as_dict() if isinstance(s, ExecutionStep) else dict(s) for s in steps]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "job_type": self.job_type.value,
            "task_id": self.task_id,
            "ring_number": self.ring_number,
            "provider": self.provider,
            "provider_reference": self.provider_reference,
            "state": self.state.value,
            "terminal": self.terminal,
            "unconfirmed": self.unconfirmed,
            "dry_run": self.dry_run,
            "correlation_id": self.correlation_id,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
            "started_at": iso_utc(self.started_at),
            "completed_at": iso_utc(self.completed_at),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "targets": [t.as_dict() for t in self.targets],
            "steps": self.steps(),
            "result": {k: v for k, v in self.result_payload.items() if k != "steps"},
            "request": {k: v for k, v in self.request_payload.items() if k != "task_snapshot"},
            "events": [e.as_dict() for e in self.events],
        }
