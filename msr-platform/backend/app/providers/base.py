"""Contratos y modelos de dominio de los providers de parcheo/restauración.

Estos modelos son el límite entre el plano de control (store/API) y la
ejecución técnica (mock o AWS Systems Manager Automation). No contienen
credenciales ni objetos de boto3.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, runtime_checkable

MAX_TEXT = 2000

RESTORE_KIND_ROLLBACK = "rollback"
RESTORE_KIND_RESET_LAB = "reset_lab"


def synthetic_instance_id(logical_lab_id: str, generation: str) -> str:
    """Instance ID simulado y determinista del laboratorio en modo mock.

    Cambia en cada reset (la generación es el job que lo recreó), igual que una
    instancia real recreada desde el Launch Template.
    """
    digest = hashlib.sha256(f"{logical_lab_id}:{generation}".encode()).hexdigest()
    return f"i-{digest[:17]}"


def utcnow() -> datetime:
    """Instante actual en UTC real (nunca `seed.NOW`, que es la fecha de demo)."""
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ExecutionStatus(str, Enum):
    """Estado de una ejecución tal y como lo reporta el provider."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    DRY_RUN = "dry_run"

    @property
    def terminal(self) -> bool:
        return self in (ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED,
                        ExecutionStatus.CANCELLED, ExecutionStatus.TIMED_OUT,
                        ExecutionStatus.DRY_RUN)


class ProviderError(Exception):
    """Error tipado y sanitizado emitido por un provider."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message[:MAX_TEXT]
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class Target:
    """Objetivo lógico de una operación. `instance_id` sólo existe con AWS."""

    logical_target_id: str
    instance_id: str | None = None
    account_id: str | None = None
    region: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    operating_system: str | None = None
    environment: str | None = None
    ssm_managed: bool = False
    name: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Target:
        allowed = {f for f in cls.__dataclass_fields__}  # noqa: C416 - claridad
        return cls(**{k: v for k, v in (data or {}).items() if k in allowed})


@dataclass(frozen=True, slots=True)
class PatchSpec:
    """Qué se parchea. El runbook y los comandos NO viajan aquí: los resuelve
    el provider a partir de la configuración y de su allowlist interna."""

    component: str
    from_version: str
    to_version: str
    cve: str | None = None
    track: str = "A"


@dataclass(frozen=True, slots=True)
class PatchRequest:
    job_id: str
    task_id: str
    ring_number: int
    targets: tuple[Target, ...]
    spec: PatchSpec
    dry_run: bool = True
    correlation_id: str = ""
    ring_label: str = ""
    executor: str = ""
    assets_count: int = 1
    task_snapshot: dict = field(default_factory=dict)

    def primary_target(self) -> Target:
        if not self.targets:
            raise ProviderError("TARGET_NOT_RESOLVED", "La petición no contiene ningún objetivo.")
        return self.targets[0]


@dataclass(frozen=True, slots=True)
class RestoreRequest:
    job_id: str
    task_id: str
    ring_number: int
    targets: tuple[Target, ...]
    reason: str
    target_version: str
    snapshot_ref: str | None = None
    dry_run: bool = True
    correlation_id: str = ""
    restore_kind: str = "rollback"  # rollback | reset_lab
    task_snapshot: dict = field(default_factory=dict)

    def primary_target(self) -> Target:
        if not self.targets:
            raise ProviderError("TARGET_NOT_RESOLVED", "La petición no contiene ningún objetivo.")
        return self.targets[0]


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    """Paso de ejecución. Mantiene los campos que ya consume el frontend
    (`RingAction.steps`) para no romper la vista de evidencias."""

    seq: int
    actor: str
    tool: str
    command: str
    output: str
    status: str = "ok"
    why: str = ""
    duration_s: int = 0
    started_at: str | None = None
    ended_at: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PatchExecution:
    provider: str
    provider_reference: str
    status: ExecutionStatus
    dry_run: bool = True
    steps: tuple[ExecutionStep, ...] = ()
    from_version: str | None = None
    to_version: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_status: str | None = None
    detail: str = ""
    # Degradación parcial (p. ej. no se pudo leer el detalle de pasos): no
    # invalida `status`, pero debe quedar registrada como evento auditable.
    warning_code: str | None = None
    warning_message: str | None = None
    # Outputs declarados del runbook (Automation Report), ya saneados: son la
    # evidencia real del estado del objetivo tras la ejecución.
    report: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["steps"] = [s.as_dict() for s in self.steps]
        return data

    def with_steps(self, steps: tuple[ExecutionStep, ...]) -> PatchExecution:
        return replace(self, steps=steps)


@dataclass(frozen=True, slots=True)
class RestoreExecution:
    provider: str
    provider_reference: str
    status: ExecutionStatus
    dry_run: bool = True
    steps: tuple[ExecutionStep, ...] = ()
    restored_version: str | None = None
    # Sólo en `reset_lab`: la instancia recreada tiene un Instance ID nuevo.
    new_instance_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_status: str | None = None
    detail: str = ""
    warning_code: str | None = None
    warning_message: str | None = None
    report: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["steps"] = [s.as_dict() for s in self.steps]
        return data


@dataclass(frozen=True, slots=True)
class TargetPolicyResult:
    allowed: bool
    checks: tuple[dict, ...] = ()
    violations: tuple[str, ...] = ()
    error_code: str | None = None
    message: str = ""
    target: Target | None = None

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "checks": list(self.checks),
            "violations": list(self.violations),
            "error_code": self.error_code,
            "message": self.message,
            "target": self.target.as_dict() if self.target else None,
        }


@runtime_checkable
class PatchProvider(Protocol):
    """Contrato de un ejecutor de parcheo.

    `poll`/`cancel` reciben opcionalmente la petición original: los providers son
    sin estado y el plano de control rehidrata la petición desde SQLite, lo que
    evita almacenar contexto en el propio `provider_reference`.
    """

    name: str

    def validate_target(self, request: PatchRequest) -> TargetPolicyResult:
        ...

    def start(self, request: PatchRequest, idempotency_key: str) -> PatchExecution:
        ...

    def poll(self, provider_reference: str, request: PatchRequest | None = None) -> PatchExecution:
        ...

    def cancel(self, provider_reference: str, request: PatchRequest | None = None) -> PatchExecution:
        ...


@runtime_checkable
class RestoreProvider(Protocol):
    name: str

    def validate_target(self, request: RestoreRequest) -> TargetPolicyResult:
        ...

    def start(self, request: RestoreRequest, idempotency_key: str) -> RestoreExecution:
        ...

    def poll(self, provider_reference: str, request: RestoreRequest | None = None) -> RestoreExecution:
        ...
