"""Adaptador de AWS Systems Manager Automation (desactivado por defecto).

Diseño:
- `validate_target()` sólo realiza llamadas de SÓLO LECTURA (EC2 DescribeInstances,
  SSM DescribeInstanceInformation).
- `start()` con `MSR_DRY_RUN=true` NO llama a `StartAutomationExecution`.
- El runbook y los parámetros los decide el backend a partir de la configuración
  y de una allowlist interna; nunca llegan desde el frontend.
- Los clientes boto3 se pueden inyectar para poder testear con `botocore.stub.Stubber`.
- No se realiza ninguna llamada a AWS durante el import ni durante el arranque.
"""
from __future__ import annotations

import uuid

from ..config import PROVIDER_AWS_AUTOMATION, ConfigurationError, Settings
from ..policy import (
    PolicyViolation,
    assert_parameters_allowed,
    assert_runbook_allowed,
    evaluate_target,
    sanitize_text,
)
from .base import (
    ExecutionStatus,
    ExecutionStep,
    PatchExecution,
    PatchRequest,
    ProviderError,
    RestoreExecution,
    RestoreRequest,
    Target,
    TargetPolicyResult,
    iso_utc,
    utcnow,
)

DRY_RUN_PREFIX = "dryrun:"

# Mapeo de estados de Systems Manager Automation → estados de ejecución internos.
STATUS_MAP: dict[str, ExecutionStatus] = {
    "Pending": ExecutionStatus.PENDING,
    "Scheduled": ExecutionStatus.PENDING,
    "PendingApproval": ExecutionStatus.PENDING,
    "PendingChangeCalendarOverride": ExecutionStatus.PENDING,
    "Approved": ExecutionStatus.RUNNING,
    "ChangeCalendarOverrideApproved": ExecutionStatus.RUNNING,
    "InProgress": ExecutionStatus.RUNNING,
    "RunbookInProgress": ExecutionStatus.RUNNING,
    "Waiting": ExecutionStatus.RUNNING,
    "Success": ExecutionStatus.SUCCEEDED,
    "CompletedWithSuccess": ExecutionStatus.SUCCEEDED,
    "Failed": ExecutionStatus.FAILED,
    "CompletedWithFailure": ExecutionStatus.FAILED,
    "Rejected": ExecutionStatus.FAILED,
    "ChangeCalendarOverrideRejected": ExecutionStatus.FAILED,
    "Exited": ExecutionStatus.FAILED,
    "TimedOut": ExecutionStatus.TIMED_OUT,
    "Cancelling": ExecutionStatus.CANCELLING,
    "Cancelled": ExecutionStatus.CANCELLED,
}
STEP_STATUS_MAP = {"Success": "ok", "Failed": "failed", "TimedOut": "timed_out",
                   "Cancelled": "cancelled", "InProgress": "running", "Pending": "pending",
                   "Waiting": "waiting"}

# Parámetros que el backend puede enviar a los runbooks permitidos.
ALLOWED_PARAMETER_KEYS = {"InstanceId", "AutomationAssumeRole", "Operation", "RebootOption",
                          "SnapshotId", "TargetVersion"}


def map_status(aws_status: str | None) -> ExecutionStatus:
    """Estados desconocidos se tratan defensivamente como 'en curso'."""
    if not aws_status:
        return ExecutionStatus.RUNNING
    return STATUS_MAP.get(aws_status, ExecutionStatus.RUNNING)


class _AutomationBase:
    """Lógica compartida por los adaptadores de parcheo y restauración."""

    name = PROVIDER_AWS_AUTOMATION

    def __init__(self, settings: Settings, ssm_client=None, ec2_client=None, now_fn=utcnow):
        self._settings = settings
        self._ssm = ssm_client
        self._ec2 = ec2_client
        self._now = now_fn

    # -- clientes -------------------------------------------------------
    def _session_kwargs(self) -> dict:
        kwargs: dict = {}
        if self._settings.aws_region:
            kwargs["region_name"] = self._settings.aws_region
        if self._settings.aws_profile:
            kwargs["profile_name"] = self._settings.aws_profile
        return kwargs

    def _client(self, service: str):
        try:
            import boto3  # import diferido: sin AWS con provider mock
        except ImportError as exc:  # pragma: no cover - dependencia declarada
            raise ProviderError("PROVIDER_UNAVAILABLE",
                                "boto3 no está instalado en el backend.") from exc
        if not self._settings.aws_region:
            raise ConfigurationError("MSR_AWS_REGION es obligatorio para el provider aws-automation.")
        session = boto3.Session(**self._session_kwargs())
        client_kwargs = {}
        if self._settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = self._settings.aws_endpoint_url
        return session.client(service, **client_kwargs)

    @property
    def ssm(self):
        if self._ssm is None:
            self._ssm = self._client("ssm")
        return self._ssm

    @property
    def ec2(self):
        if self._ec2 is None:
            self._ec2 = self._client("ec2")
        return self._ec2

    # -- validación (sólo lectura) --------------------------------------
    def _resolve_target(self, target: Target) -> tuple[Target, str | None]:
        """Resuelve cuenta, región, tags, estado e inscripción en SSM."""
        instance_id = target.instance_id or ""
        if not instance_id:
            return target, None
        try:
            described = self.ec2.describe_instances(InstanceIds=[instance_id])
        except Exception as exc:  # botocore.ClientError y validaciones
            raise self._as_provider_error(exc, "TARGET_NOT_FOUND",
                                          f"No se pudo describir la instancia {instance_id}.") from exc
        reservations = described.get("Reservations") or []
        instances = (reservations[0].get("Instances") if reservations else []) or []
        if not instances:
            raise ProviderError("TARGET_NOT_FOUND",
                                f"La instancia {instance_id} no existe en la región configurada.")
        instance = instances[0]
        state = ((instance.get("State") or {}).get("Name") or "unknown")
        tags = {t.get("Key"): t.get("Value") for t in (instance.get("Tags") or [])}
        placement_az = (instance.get("Placement") or {}).get("AvailabilityZone") or ""
        region = placement_az[:-1] if placement_az else self._settings.aws_region
        account_id = reservations[0].get("OwnerId") or target.account_id
        platform = instance.get("PlatformDetails") or instance.get("Platform") or "Linux/UNIX"

        ssm_managed = False
        if state == "running":
            try:
                info = self.ssm.describe_instance_information(
                    Filters=[{"Key": "InstanceIds", "Values": [instance_id]}])
                entries = info.get("InstanceInformationList") or []
                ssm_managed = any(e.get("PingStatus") == "Online" for e in entries)
            except Exception as exc:
                raise self._as_provider_error(exc, "PROVIDER_UNAVAILABLE",
                                              "No se pudo consultar el inventario de nodos gestionados de SSM.") from exc

        resolved = Target(
            logical_target_id=target.logical_target_id, instance_id=instance_id,
            account_id=account_id, region=region, tags=tags,
            operating_system=str(platform), environment=target.environment or tags.get("Environment"),
            ssm_managed=ssm_managed, name=target.name)
        return resolved, state

    def _evaluate(self, target: Target) -> TargetPolicyResult:
        resolved, state = self._resolve_target(target)
        return evaluate_target(resolved, self._settings, instance_state=state, require_instance=True)

    @staticmethod
    def _as_provider_error(exc: Exception, code: str, message: str) -> ProviderError:
        detail = sanitize_text(str(exc), 400)
        return ProviderError(code, f"{message} Detalle: {detail}")

    # -- ejecución -------------------------------------------------------
    def _client_token(self, idempotency_key: str) -> str:
        """SSM exige un ClientToken con formato UUID; se deriva de la clave."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"msr-platform/{idempotency_key}"))

    def _tags(self, correlation_id: str, task_id: str) -> list[dict]:
        return [
            {"Key": "msr:correlation-id", "Value": correlation_id[:255]},
            {"Key": "msr:task-id", "Value": task_id[:255]},
            {"Key": "msr:managed-by", "Value": "msr-platform"},
        ]

    def _start_automation(self, runbook: str, parameters: dict, correlation_id: str,
                          task_id: str, idempotency_key: str) -> str:
        assert_runbook_allowed(runbook, self._settings)
        assert_parameters_allowed(parameters, ALLOWED_PARAMETER_KEYS)
        request = {
            "DocumentName": runbook,
            "Parameters": {k: (v if isinstance(v, list) else [v]) for k, v in parameters.items()},
            "Mode": "Auto",
            "ClientToken": self._client_token(idempotency_key),
            "Tags": self._tags(correlation_id, task_id),
        }
        try:
            response = self.ssm.start_automation_execution(**request)
        except Exception as exc:
            raise self._as_provider_error(exc, "PROVIDER_START_FAILED",
                                          "Systems Manager rechazó el arranque de la automatización.") from exc
        execution_id = response.get("AutomationExecutionId")
        if not execution_id:
            raise ProviderError("PROVIDER_START_FAILED",
                                "Systems Manager no devolvió AutomationExecutionId.")
        return execution_id

    def _describe(self, provider_reference: str) -> tuple[ExecutionStatus, dict, tuple[ExecutionStep, ...]]:
        try:
            response = self.ssm.get_automation_execution(AutomationExecutionId=provider_reference)
        except Exception as exc:
            raise self._as_provider_error(exc, "PROVIDER_UNAVAILABLE",
                                          "No se pudo consultar la automatización en Systems Manager.") from exc
        execution = response.get("AutomationExecution") or {}
        raw_status = execution.get("AutomationExecutionStatus")
        status = map_status(raw_status)
        steps = self._describe_steps(provider_reference) if raw_status else ()
        return status, execution, steps

    def _describe_steps(self, provider_reference: str) -> tuple[ExecutionStep, ...]:
        try:
            response = self.ssm.describe_automation_step_executions(
                AutomationExecutionId=provider_reference)
        except Exception:
            # La ausencia de detalle de pasos no debe invalidar la reconciliación.
            return ()
        limit = self._settings.max_output_chars
        steps: list[ExecutionStep] = []
        for i, step in enumerate(response.get("StepExecutions") or []):
            outputs = step.get("Outputs") or {}
            output = step.get("FailureMessage") or "; ".join(
                f"{k}={','.join(str(x) for x in (v if isinstance(v, list) else [v]))}"
                for k, v in outputs.items())
            steps.append(ExecutionStep(
                seq=i + 1,
                actor="AWS Systems Manager",
                tool=f"Automation · {step.get('Action', 'step')}",
                command=sanitize_text(step.get("StepName") or f"step-{i + 1}", 200),
                output=sanitize_text(output or step.get("StepStatus") or "-", limit),
                status=STEP_STATUS_MAP.get(step.get("StepStatus"), "running"),
                why="Paso del runbook de Automation ejecutado por Systems Manager.",
                started_at=iso_utc(step.get("ExecutionStartTime")),
                ended_at=iso_utc(step.get("ExecutionEndTime")),
            ))
        return tuple(steps)


class AwsSsmAutomationPatchProvider(_AutomationBase):
    """Parcheo de paquetes de sistema operativo en una EC2 Linux vía Automation."""

    def validate_target(self, request: PatchRequest) -> TargetPolicyResult:
        return self._evaluate(request.primary_target())

    def _parameters(self, target: Target) -> dict:
        params = {"InstanceId": [target.instance_id or ""]}
        if self._settings.automation_assume_role_arn:
            params["AutomationAssumeRole"] = [self._settings.automation_assume_role_arn]
        params["Operation"] = ["Install"]
        return params

    def start(self, request: PatchRequest, idempotency_key: str) -> PatchExecution:
        runbook = self._settings.patch_runbook_name
        target = request.primary_target()
        policy = self.validate_target(request)
        if not policy.allowed:
            raise ProviderError(policy.error_code or "TARGET_NOT_ALLOWED", policy.message)
        try:
            assert_runbook_allowed(runbook, self._settings)
            parameters = assert_parameters_allowed(self._parameters(policy.target or target),
                                                  ALLOWED_PARAMETER_KEYS)
        except PolicyViolation as exc:
            raise ProviderError(exc.code, exc.message) from exc

        started = self._now()
        if request.dry_run:
            summary = ExecutionStep(
                seq=1, actor="msr-platform", tool="Systems Manager Automation (dry-run)",
                command=f"StartAutomationExecution DocumentName={runbook}",
                output="[dry-run] no se ha invocado ninguna API mutativa de AWS. "
                       f"Parámetros: {sanitize_text(str(sorted(parameters)), 300)}",
                status="planned",
                why="Con MSR_DRY_RUN=true se registra la intención sin ejecutar el runbook.")
            return PatchExecution(
                provider=self.name, provider_reference=f"{DRY_RUN_PREFIX}{request.job_id}",
                status=ExecutionStatus.DRY_RUN, dry_run=True, steps=(summary,),
                from_version=request.spec.from_version, to_version=request.spec.to_version,
                started_at=iso_utc(started), completed_at=iso_utc(started),
                detail=f"Dry-run validado contra {target.instance_id} sin cambios aplicados.")

        execution_id = self._start_automation(runbook, parameters, request.correlation_id,
                                              request.task_id, idempotency_key)
        return PatchExecution(
            provider=self.name, provider_reference=execution_id, status=ExecutionStatus.RUNNING,
            dry_run=False, from_version=request.spec.from_version,
            to_version=request.spec.to_version, started_at=iso_utc(started),
            raw_status="InProgress",
            detail=f"Automation {runbook} iniciada sobre {target.instance_id}.")

    def poll(self, provider_reference: str, request: PatchRequest | None = None) -> PatchExecution:
        if provider_reference.startswith(DRY_RUN_PREFIX):
            return PatchExecution(provider=self.name, provider_reference=provider_reference,
                                  status=ExecutionStatus.DRY_RUN, dry_run=True,
                                  detail="Ejecución dry-run: sin estado remoto que consultar.")
        status, execution, steps = self._describe(provider_reference)
        failure = execution.get("FailureMessage")
        return PatchExecution(
            provider=self.name, provider_reference=provider_reference, status=status,
            dry_run=False, steps=steps,
            from_version=request.spec.from_version if request else None,
            to_version=request.spec.to_version if request else None,
            started_at=iso_utc(execution.get("ExecutionStartTime")),
            completed_at=iso_utc(execution.get("ExecutionEndTime")),
            error_code="AUTOMATION_FAILED" if failure else None,
            error_message=sanitize_text(failure, self._settings.max_output_chars) if failure else None,
            raw_status=execution.get("AutomationExecutionStatus"),
            detail=sanitize_text(execution.get("CurrentStepName") or "", 200))

    def cancel(self, provider_reference: str, request: PatchRequest | None = None) -> PatchExecution:
        if provider_reference.startswith(DRY_RUN_PREFIX):
            raise ProviderError("CANCEL_NOT_POSSIBLE",
                                "Una ejecución dry-run ya ha terminado; no puede cancelarse.")
        try:
            self.ssm.stop_automation_execution(AutomationExecutionId=provider_reference,
                                               Type="Cancel")
        except Exception as exc:
            raise self._as_provider_error(exc, "CANCEL_NOT_POSSIBLE",
                                          "Systems Manager no aceptó la cancelación.") from exc
        # No se marca cancelado localmente: el estado real lo dicta AWS.
        return self.poll(provider_reference, request)


class AwsSsmAutomationRestoreProvider(_AutomationBase):
    """Restauración (rollback) mediante un runbook de Automation dedicado."""

    def validate_target(self, request: RestoreRequest) -> TargetPolicyResult:
        return self._evaluate(request.primary_target())

    def _parameters(self, target: Target, request: RestoreRequest) -> dict:
        params = {"InstanceId": [target.instance_id or ""]}
        if self._settings.automation_assume_role_arn:
            params["AutomationAssumeRole"] = [self._settings.automation_assume_role_arn]
        if request.target_version:
            params["TargetVersion"] = [request.target_version]
        return params

    def start(self, request: RestoreRequest, idempotency_key: str) -> RestoreExecution:
        runbook = self._settings.reset_runbook_name
        target = request.primary_target()
        policy = self.validate_target(request)
        if not policy.allowed:
            raise ProviderError(policy.error_code or "TARGET_NOT_ALLOWED", policy.message)
        try:
            assert_runbook_allowed(runbook, self._settings)
            parameters = assert_parameters_allowed(self._parameters(policy.target or target, request),
                                                  ALLOWED_PARAMETER_KEYS)
        except PolicyViolation as exc:
            raise ProviderError(exc.code, exc.message) from exc

        started = self._now()
        if request.dry_run:
            summary = ExecutionStep(
                seq=1, actor="msr-platform", tool="Systems Manager Automation (dry-run)",
                command=f"StartAutomationExecution DocumentName={runbook}",
                output="[dry-run] no se ha invocado ninguna API mutativa de AWS.",
                status="planned",
                why="Con MSR_DRY_RUN=true la restauración sólo se registra.")
            return RestoreExecution(
                provider=self.name, provider_reference=f"{DRY_RUN_PREFIX}{request.job_id}",
                status=ExecutionStatus.DRY_RUN, dry_run=True, steps=(summary,),
                restored_version=request.target_version, started_at=iso_utc(started),
                completed_at=iso_utc(started),
                detail=f"Dry-run de restauración sobre {target.instance_id}.")

        execution_id = self._start_automation(runbook, parameters, request.correlation_id,
                                              request.task_id, idempotency_key)
        return RestoreExecution(
            provider=self.name, provider_reference=execution_id, status=ExecutionStatus.RUNNING,
            dry_run=False, restored_version=request.target_version, started_at=iso_utc(started),
            raw_status="InProgress",
            detail=f"Automation {runbook} iniciada sobre {target.instance_id}.")

    def poll(self, provider_reference: str, request: RestoreRequest | None = None) -> RestoreExecution:
        if provider_reference.startswith(DRY_RUN_PREFIX):
            return RestoreExecution(provider=self.name, provider_reference=provider_reference,
                                    status=ExecutionStatus.DRY_RUN, dry_run=True,
                                    detail="Ejecución dry-run: sin estado remoto que consultar.")
        status, execution, steps = self._describe(provider_reference)
        failure = execution.get("FailureMessage")
        return RestoreExecution(
            provider=self.name, provider_reference=provider_reference, status=status,
            dry_run=False, steps=steps,
            restored_version=request.target_version if request else None,
            started_at=iso_utc(execution.get("ExecutionStartTime")),
            completed_at=iso_utc(execution.get("ExecutionEndTime")),
            error_code="AUTOMATION_FAILED" if failure else None,
            error_message=sanitize_text(failure, self._settings.max_output_chars) if failure else None,
            raw_status=execution.get("AutomationExecutionStatus"),
            detail=sanitize_text(execution.get("CurrentStepName") or "", 200))
