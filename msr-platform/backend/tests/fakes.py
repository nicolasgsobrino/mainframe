"""Provider AWS falso: ejerce el plano de control sin tocar boto3 ni AWS."""
from __future__ import annotations

from app.config import PROVIDER_AWS_AUTOMATION
from app.providers.base import (
    ExecutionStatus,
    PatchExecution,
    ProviderError,
    TargetPolicyResult,
)

EXECUTION_REFERENCE = "22222222-3333-4444-5555-666666666666"


class FakeAwsProvider:
    """Provider con el nombre del adaptador AWS y comportamiento programable."""

    name = PROVIDER_AWS_AUTOMATION

    def __init__(self, poll_status: ExecutionStatus = ExecutionStatus.RUNNING,
                 poll_error: str | None = None, cancel_error: str | None = None):
        self.poll_status = poll_status
        self.poll_error = poll_error
        self.cancel_error = cancel_error
        self.polls = 0
        self.cancels = 0
        self.starts = 0

    def validate_target(self, request) -> TargetPolicyResult:
        return TargetPolicyResult(allowed=True, target=request.primary_target())

    def start(self, request, idempotency_key: str) -> PatchExecution:
        self.starts += 1
        return PatchExecution(provider=self.name, provider_reference=EXECUTION_REFERENCE,
                              status=ExecutionStatus.RUNNING, dry_run=request.dry_run,
                              raw_status="InProgress")

    def poll(self, provider_reference: str, request=None) -> PatchExecution:
        self.polls += 1
        if self.poll_error:
            raise ProviderError(self.poll_error, "estado remoto no disponible")
        return PatchExecution(provider=self.name, provider_reference=provider_reference,
                              status=self.poll_status, dry_run=False,
                              raw_status=self.poll_status.value)

    def cancel(self, provider_reference: str, request=None) -> PatchExecution:
        self.cancels += 1
        if self.cancel_error:
            raise ProviderError(self.cancel_error, "la parada remota no fue aceptada")
        return PatchExecution(provider=self.name, provider_reference=provider_reference,
                              status=ExecutionStatus.CANCELLING, dry_run=False,
                              raw_status="Cancelling")
