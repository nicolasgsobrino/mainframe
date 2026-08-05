"""Adaptador de AWS Systems Manager Automation (desactivado por defecto).

Diseño:
- `validate_target()` sólo realiza llamadas de SÓLO LECTURA (EC2 DescribeInstances,
  SSM DescribeInstanceInformation, SSM DescribeDocument).
- `start()` con `MSR_DRY_RUN=true` NO llama a `StartAutomationExecution`.
- El runbook y sus parámetros salen del contrato declarado en `runbooks.py`:
  sólo documentos de tipo `Automation` y sólo los parámetros que el runbook
  declara. Nunca llegan desde el frontend.
- Los clientes boto3 se pueden inyectar para poder testear con `botocore.stub.Stubber`.
- No se realiza ninguna llamada a AWS durante el import ni durante el arranque.
"""
from __future__ import annotations

import re
import uuid
from datetime import timedelta

from ..config import PROVIDER_AWS_AUTOMATION, ConfigurationError, Settings
from ..policy import INSTANCE_ID_RE, evaluate_target, sanitize_text
from ..runbooks import (
    OPERATION_PATCH,
    OPERATION_RESET_LAB,
    OPERATION_ROLLBACK,
    ResolvedRunbook,
    RunbookContractError,
    assert_document_type,
    assert_operating_system_supported,
    assert_track_supported,
    resolve_runbook,
    validate_parameters,
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

_SESSION_NAME_RE = re.compile(r"[^\w+=,.@-]")
_PERMISSION_ERRORS = ("AccessDenied", "UnauthorizedOperation", "AuthFailure",
                      "NotAuthorized", "ExpiredToken", "InvalidClientTokenId")
_THROTTLING_ERRORS = ("Throttling", "ThrottlingException", "RequestLimitExceeded",
                      "TooManyRequests", "RequestThrottled")


def map_status(aws_status: str | None) -> ExecutionStatus:
    """Estados desconocidos se tratan defensivamente como 'en curso'."""
    if not aws_status:
        return ExecutionStatus.RUNNING
    return STATUS_MAP.get(aws_status, ExecutionStatus.RUNNING)


def classify_error(exc: Exception) -> tuple[str, str]:
    """Diferencia permisos, throttling y fallo transitorio (código, descripción)."""
    code = ""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = str((response.get("Error") or {}).get("Code") or "")
    text = f"{code} {exc}"
    if any(token in text for token in _PERMISSION_ERRORS):
        return "PERMISSION_DENIED", "falta de permisos IAM"
    if any(token in text for token in _THROTTLING_ERRORS):
        return "THROTTLED", "throttling de la API de AWS"
    return "TRANSIENT_FAILURE", "fallo transitorio"


def _automation_output(execution: dict, key: str) -> str | None:
    """Output declarado del runbook (p. ej. `NewInstanceId`), sanitizado.

    Los outputs de Automation llegan como `{'Paso.Output': ['valor']}`; sólo se
    aceptan los que declara el contrato y con el formato esperado.
    """
    outputs = execution.get("Outputs") or {}
    for name, values in outputs.items():
        if not str(name).endswith(key):
            continue
        items = values if isinstance(values, list) else [values]
        for item in items:
            candidate = sanitize_text(str(item), 64).strip()
            if key.endswith("InstanceId") and not INSTANCE_ID_RE.match(candidate):
                continue
            if candidate:
                return candidate
    return None


def sanitize_session_name(value: str) -> str:
    """RoleSessionName: sólo [\\w+=,.@-] y como máximo 64 caracteres."""
    cleaned = _SESSION_NAME_RE.sub("-", value or "")
    return (cleaned or "msr-platform")[:64]


class _AutomationBase:
    """Lógica compartida por los adaptadores de parcheo y restauración."""

    name = PROVIDER_AWS_AUTOMATION

    def __init__(self, settings: Settings, ssm_client=None, ec2_client=None, sts_client=None,
                 now_fn=utcnow):
        self._settings = settings
        # Los clientes inyectados (tests) nunca se reemplazan automáticamente.
        self._injected_ssm = ssm_client
        self._injected_ec2 = ec2_client
        self._sts = sts_client
        self._now = now_fn
        self._correlation_id = ""
        self._assumed: dict | None = None
        self._assumed_expiry = None
        # Generación de credenciales: cuando STS las renueva invalida los
        # clientes construidos con las anteriores.
        self._credentials_generation = 0
        self._clients: dict[str, object] = {}
        self._clients_generation = -1

    # -- clientes -------------------------------------------------------
    def _boto3(self):
        try:
            import boto3  # import diferido: sin AWS con provider mock
        except ImportError as exc:  # pragma: no cover - dependencia declarada
            raise ProviderError("PROVIDER_UNAVAILABLE",
                                "boto3 no está instalado en el backend.") from exc
        return boto3

    def _session_kwargs(self) -> dict:
        kwargs: dict = {}
        if self._settings.aws_region:
            kwargs["region_name"] = self._settings.aws_region
        if self._settings.aws_profile:
            kwargs["profile_name"] = self._settings.aws_profile
        return kwargs

    @property
    def sts(self):
        if self._sts is None:
            self._sts = self._boto3().Session(**self._session_kwargs()).client("sts")
        return self._sts

    def _assume_role_credentials(self) -> dict:
        """Credenciales temporales de `MSR_AWS_ROLE_ARN` vía STS AssumeRole.

        La sesión se renueva cuando caduca; los valores nunca se registran.
        """
        now = self._now()
        if self._assumed and self._assumed_expiry and now < self._assumed_expiry:
            return self._assumed
        session_name = sanitize_session_name(
            f"msr-{self._correlation_id or uuid.uuid4().hex[:12]}")
        try:
            response = self.sts.assume_role(RoleArn=self._settings.aws_role_arn,
                                            RoleSessionName=session_name,
                                            DurationSeconds=3600)
        except Exception as exc:
            code, kind = classify_error(exc)
            raise ProviderError(code, f"No se pudo asumir MSR_AWS_ROLE_ARN ({kind}).") from exc
        credentials = response.get("Credentials") or {}
        if not credentials.get("AccessKeyId"):
            raise ProviderError("PERMISSION_DENIED",
                                "STS no devolvió credenciales temporales para el rol configurado.")
        self._assumed = {
            "aws_access_key_id": credentials["AccessKeyId"],
            "aws_secret_access_key": credentials["SecretAccessKey"],
            "aws_session_token": credentials.get("SessionToken"),
        }
        expiration = credentials.get("Expiration")
        # Margen de 60 s para no usar credenciales a punto de caducar.
        self._assumed_expiry = (expiration - timedelta(seconds=60)
                                if expiration is not None else now + timedelta(minutes=50))
        self._credentials_generation += 1
        return self._assumed

    def _client(self, service: str):
        boto3 = self._boto3()
        if not self._settings.aws_region:
            raise ConfigurationError("MSR_AWS_REGION es obligatorio para el provider aws-automation.")
        session_kwargs = self._session_kwargs()
        if self._settings.aws_role_arn:
            session_kwargs.pop("profile_name", None)
            session_kwargs.update(self._assume_role_credentials())
        session = boto3.Session(**session_kwargs)
        client_kwargs = {}
        if self._settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = self._settings.aws_endpoint_url
        return session.client(service, **client_kwargs)

    def _service_client(self, service: str):
        """Cliente vigente del servicio.

        Con `MSR_AWS_ROLE_ARN` los clientes se construyen con credenciales
        temporales: al renovarlas cambia la generación y se descartan los
        clientes anteriores, de forma que ninguna operación reutilice un cliente
        con credenciales caducadas.
        """
        if self._settings.aws_role_arn:
            self._assume_role_credentials()
            if self._clients_generation != self._credentials_generation:
                self._clients.clear()
                self._clients_generation = self._credentials_generation
        client = self._clients.get(service)
        if client is None:
            client = self._client(service)
            self._clients[service] = client
        return client

    @property
    def ssm(self):
        return self._injected_ssm if self._injected_ssm is not None else self._service_client("ssm")

    @property
    def ec2(self):
        return self._injected_ec2 if self._injected_ec2 is not None else self._service_client("ec2")

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

    def _evaluate(self, target: Target, *, dry_run: bool) -> TargetPolicyResult:
        resolved, state = self._resolve_target(target)
        return evaluate_target(resolved, self._settings, instance_state=state,
                               require_instance=True, strict=not dry_run)

    @staticmethod
    def _as_provider_error(exc: Exception, code: str, message: str) -> ProviderError:
        detail = sanitize_text(str(exc), 400)
        return ProviderError(code, f"{message} Detalle: {detail}")

    # -- contrato de runbook ---------------------------------------------
    def _runbook(self, operation: str) -> ResolvedRunbook:
        try:
            return resolve_runbook(self._settings, operation)
        except RunbookContractError as exc:
            raise ProviderError(exc.code, exc.message) from exc

    def _assert_document_is_automation(self, runbook: ResolvedRunbook) -> str:
        """`DescribeDocument` (lectura) antes de cualquier ejecución real."""
        try:
            described = self.ssm.describe_document(Name=runbook.name)
        except Exception as exc:
            code, kind = classify_error(exc)
            raise ProviderError(
                "RUNBOOK_NOT_FOUND",
                f"No se pudo describir el runbook '{runbook.name}' ({kind}, {code}).") from exc
        document = described.get("Document") or {}
        try:
            assert_document_type(runbook.name, document.get("DocumentType"), runbook.contract)
        except RunbookContractError as exc:
            raise ProviderError(exc.code, exc.message) from exc
        return document.get("DocumentType") or ""

    def _check_contract(self, runbook: ResolvedRunbook, track: str | None,
                        target: Target, parameters: dict) -> dict:
        try:
            assert_track_supported(track, runbook.contract)
            assert_operating_system_supported(target.operating_system, runbook.contract)
            return validate_parameters(runbook.contract, parameters)
        except RunbookContractError as exc:
            raise ProviderError(exc.code, exc.message) from exc

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

    def _start_automation(self, runbook: ResolvedRunbook, parameters: dict, correlation_id: str,
                          task_id: str, idempotency_key: str) -> str:
        # Última barrera antes de mutar: el documento debe existir y ser Automation.
        self._assert_document_is_automation(runbook)
        request = {
            "DocumentName": runbook.name,
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

    def _describe(self, provider_reference: str):
        try:
            response = self.ssm.get_automation_execution(AutomationExecutionId=provider_reference)
        except Exception as exc:
            raise self._as_provider_error(exc, "PROVIDER_UNAVAILABLE",
                                          "No se pudo consultar la automatización en Systems Manager.") from exc
        execution = response.get("AutomationExecution") or {}
        raw_status = execution.get("AutomationExecutionStatus")
        steps: tuple[ExecutionStep, ...] = ()
        warning: tuple[str, str] | None = None
        if raw_status:
            steps, warning = self._describe_steps(provider_reference)
        return map_status(raw_status), execution, steps, warning

    def _describe_steps(self, provider_reference: str):
        """El detalle de pasos es complementario: si falla, se degrada con aviso."""
        try:
            response = self.ssm.describe_automation_step_executions(
                AutomationExecutionId=provider_reference)
        except Exception as exc:
            code, kind = classify_error(exc)
            # No se oculta la excepción: se conserva el estado de
            # GetAutomationExecution y se emite un aviso sanitizado.
            return (), (code, f"No se pudo leer el detalle de pasos ({kind}): "
                              f"{sanitize_text(str(exc), 300)}")
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
        return tuple(steps), None

    def _request_stop(self, provider_reference: str, stop_type: str = "Cancel") -> None:
        try:
            self.ssm.stop_automation_execution(AutomationExecutionId=provider_reference,
                                               Type=stop_type)
        except Exception as exc:
            raise self._as_provider_error(exc, "CANCEL_NOT_POSSIBLE",
                                          "Systems Manager no aceptó la parada de la ejecución.") from exc


class AwsSsmAutomationPatchProvider(_AutomationBase):
    """Parcheo de paquetes de sistema operativo en una EC2 Linux vía Automation."""

    operation = OPERATION_PATCH

    def validate_target(self, request: PatchRequest) -> TargetPolicyResult:
        self._correlation_id = request.correlation_id
        runbook = self._runbook(self.operation)
        target = request.primary_target()
        try:
            assert_track_supported(request.spec.track, runbook.contract)
        except RunbookContractError as exc:
            raise ProviderError(exc.code, exc.message) from exc
        return self._evaluate(target, dry_run=request.dry_run)

    def _parameters(self, runbook: ResolvedRunbook, target: Target) -> dict:
        """Parámetros derivados del esquema del runbook, nunca genéricos."""
        declared = runbook.contract.declared_parameters
        params: dict = {}
        if "InstanceId" in declared:
            params["InstanceId"] = [target.instance_id or ""]
        if "AutomationAssumeRole" in declared and self._settings.automation_assume_role_arn:
            params["AutomationAssumeRole"] = [self._settings.automation_assume_role_arn]
        if "CorrelationId" in declared and self._correlation_id:
            params["CorrelationId"] = [self._correlation_id]
        return params

    def start(self, request: PatchRequest, idempotency_key: str) -> PatchExecution:
        self._correlation_id = request.correlation_id
        runbook = self._runbook(self.operation)
        target = request.primary_target()
        policy = self.validate_target(request)
        if not policy.allowed:
            raise ProviderError(policy.error_code or "TARGET_NOT_ALLOWED", policy.message)
        resolved = policy.target or target
        if (runbook.contract.requires_assume_role and not request.dry_run
                and not self._settings.automation_assume_role_arn):
            raise ProviderError("PROVIDER_MISCONFIGURED",
                                "El runbook requiere MSR_AUTOMATION_ASSUME_ROLE_ARN para ejecutarse.")
        parameters = self._check_contract(runbook, request.spec.track, resolved,
                                         self._parameters(runbook, resolved))

        started = self._now()
        if request.dry_run:
            document_type = self._assert_document_is_automation(runbook)
            summary = ExecutionStep(
                seq=1, actor="msr-platform", tool="Systems Manager Automation (dry-run)",
                command=f"StartAutomationExecution DocumentName={runbook.name}",
                output="[dry-run] no se ha invocado ninguna API mutativa de AWS. "
                       f"Documento {runbook.name} ({document_type}). Parámetros: "
                       f"{sanitize_text(str(sorted(parameters)), 300)}",
                status="planned",
                why="Con MSR_DRY_RUN=true se registra la intención sin ejecutar el runbook.")
            return PatchExecution(
                provider=self.name, provider_reference=f"{DRY_RUN_PREFIX}{request.job_id}",
                status=ExecutionStatus.DRY_RUN, dry_run=True, steps=(summary,),
                started_at=iso_utc(started), completed_at=iso_utc(started),
                detail=f"Dry-run validado contra {resolved.instance_id} sin cambios aplicados.")

        execution_id = self._start_automation(runbook, parameters, request.correlation_id,
                                              request.task_id, idempotency_key)
        # Sin versión objetivo inventada: la evidencia sale del runbook, no del store.
        return PatchExecution(
            provider=self.name, provider_reference=execution_id, status=ExecutionStatus.RUNNING,
            dry_run=False, started_at=iso_utc(started), raw_status="InProgress",
            detail=f"Automation {runbook.name} iniciada sobre {resolved.instance_id}.")

    def poll(self, provider_reference: str, request: PatchRequest | None = None) -> PatchExecution:
        if request is not None:
            self._correlation_id = request.correlation_id
        if provider_reference.startswith(DRY_RUN_PREFIX):
            return PatchExecution(provider=self.name, provider_reference=provider_reference,
                                  status=ExecutionStatus.DRY_RUN, dry_run=True,
                                  detail="Ejecución dry-run: sin estado remoto que consultar.")
        status, execution, steps, warning = self._describe(provider_reference)
        failure = execution.get("FailureMessage")
        return PatchExecution(
            provider=self.name, provider_reference=provider_reference, status=status,
            dry_run=False, steps=steps,
            started_at=iso_utc(execution.get("ExecutionStartTime")),
            completed_at=iso_utc(execution.get("ExecutionEndTime")),
            error_code="AUTOMATION_FAILED" if failure else None,
            error_message=sanitize_text(failure, self._settings.max_output_chars) if failure else None,
            raw_status=execution.get("AutomationExecutionStatus"),
            detail=sanitize_text(execution.get("CurrentStepName") or "", 200),
            warning_code=warning[0] if warning else None,
            warning_message=warning[1] if warning else None)

    def cancel(self, provider_reference: str, request: PatchRequest | None = None) -> PatchExecution:
        if request is not None:
            self._correlation_id = request.correlation_id
        if provider_reference.startswith(DRY_RUN_PREFIX):
            raise ProviderError("CANCEL_NOT_POSSIBLE",
                                "Una ejecución dry-run ya ha terminado; no puede cancelarse.")
        self._request_stop(provider_reference)
        # No se marca cancelado localmente: el estado real lo dicta AWS.
        return self.poll(provider_reference, request)


class AwsSsmAutomationRestoreProvider(_AutomationBase):
    """Restauración (rollback) mediante un runbook de Automation dedicado."""

    def _operation(self, request: RestoreRequest) -> str:
        return OPERATION_RESET_LAB if request.restore_kind == "reset_lab" else OPERATION_ROLLBACK

    def validate_target(self, request: RestoreRequest) -> TargetPolicyResult:
        self._correlation_id = request.correlation_id
        runbook = self._runbook(self._operation(request))
        if not runbook.contract.implemented:
            raise ProviderError(
                "RESET_LAB_NOT_IMPLEMENTED",
                f"La operación '{runbook.contract.operation}' no está implementada en AWS.")
        if request.restore_kind == "reset_lab" and not (
                self._settings.lab_launch_template_id
                and self._settings.lab_launch_template_version):
            raise ProviderError(
                "PROVIDER_MISCONFIGURED",
                "El reset del laboratorio exige MSR_LAB_LAUNCH_TEMPLATE_ID y "
                "MSR_LAB_LAUNCH_TEMPLATE_VERSION (versión fija, nunca $Latest).")
        return self._evaluate(request.primary_target(), dry_run=request.dry_run)

    def _parameters(self, runbook: ResolvedRunbook, target: Target,
                    request: RestoreRequest) -> dict:
        declared = runbook.contract.declared_parameters
        params: dict = {}
        if "InstanceId" in declared:
            params["InstanceId"] = [target.instance_id or ""]
        # Reset del laboratorio: instancia actual + versión FIJA del Launch Template.
        if "CurrentInstanceId" in declared:
            params["CurrentInstanceId"] = [target.instance_id or ""]
        if "LaunchTemplateId" in declared:
            params["LaunchTemplateId"] = [self._settings.lab_launch_template_id]
        if "LaunchTemplateVersion" in declared:
            params["LaunchTemplateVersion"] = [self._settings.lab_launch_template_version]
        if "CorrelationId" in declared and request.correlation_id:
            params["CorrelationId"] = [request.correlation_id]
        if "AutomationAssumeRole" in declared and self._settings.automation_assume_role_arn:
            params["AutomationAssumeRole"] = [self._settings.automation_assume_role_arn]
        # `TargetVersion`/`SnapshotId` sólo se envían si el runbook los declara.
        if "TargetVersion" in declared and request.target_version:
            params["TargetVersion"] = [request.target_version]
        if "SnapshotId" in declared and request.snapshot_ref:
            params["SnapshotId"] = [request.snapshot_ref]
        return params

    def start(self, request: RestoreRequest, idempotency_key: str) -> RestoreExecution:
        self._correlation_id = request.correlation_id
        runbook = self._runbook(self._operation(request))
        policy = self.validate_target(request)
        if not policy.allowed:
            raise ProviderError(policy.error_code or "TARGET_NOT_ALLOWED", policy.message)
        resolved = policy.target or request.primary_target()
        track = (request.task_snapshot or {}).get("track", "A")
        parameters = self._check_contract(runbook, track, resolved,
                                          self._parameters(runbook, resolved, request))

        started = self._now()
        if request.dry_run:
            document_type = self._assert_document_is_automation(runbook)
            summary = ExecutionStep(
                seq=1, actor="msr-platform", tool="Systems Manager Automation (dry-run)",
                command=f"StartAutomationExecution DocumentName={runbook.name}",
                output="[dry-run] no se ha invocado ninguna API mutativa de AWS. "
                       f"Documento {runbook.name} ({document_type}).",
                status="planned",
                why="Con MSR_DRY_RUN=true la restauración sólo se registra.")
            return RestoreExecution(
                provider=self.name, provider_reference=f"{DRY_RUN_PREFIX}{request.job_id}",
                status=ExecutionStatus.DRY_RUN, dry_run=True, steps=(summary,),
                started_at=iso_utc(started), completed_at=iso_utc(started),
                detail=f"Dry-run de restauración sobre {resolved.instance_id}.")

        execution_id = self._start_automation(runbook, parameters, request.correlation_id,
                                              request.task_id, idempotency_key)
        return RestoreExecution(
            provider=self.name, provider_reference=execution_id, status=ExecutionStatus.RUNNING,
            dry_run=False, started_at=iso_utc(started), raw_status="InProgress",
            detail=f"Automation {runbook.name} iniciada sobre {resolved.instance_id}.")

    def poll(self, provider_reference: str,
             request: RestoreRequest | None = None) -> RestoreExecution:
        if request is not None:
            self._correlation_id = request.correlation_id
        if provider_reference.startswith(DRY_RUN_PREFIX):
            return RestoreExecution(provider=self.name, provider_reference=provider_reference,
                                    status=ExecutionStatus.DRY_RUN, dry_run=True,
                                    detail="Ejecución dry-run: sin estado remoto que consultar.")
        status, execution, steps, warning = self._describe(provider_reference)
        failure = execution.get("FailureMessage")
        return RestoreExecution(
            provider=self.name, provider_reference=provider_reference, status=status,
            dry_run=False, steps=steps,
            new_instance_id=_automation_output(execution, "NewInstanceId"),
            restored_version=request.target_version if request else None,
            started_at=iso_utc(execution.get("ExecutionStartTime")),
            completed_at=iso_utc(execution.get("ExecutionEndTime")),
            error_code="AUTOMATION_FAILED" if failure else None,
            error_message=sanitize_text(failure, self._settings.max_output_chars) if failure else None,
            raw_status=execution.get("AutomationExecutionStatus"),
            detail=sanitize_text(execution.get("CurrentStepName") or "", 200),
            warning_code=warning[0] if warning else None,
            warning_message=warning[1] if warning else None)

    def cancel(self, provider_reference: str,
               request: RestoreRequest | None = None) -> RestoreExecution:
        if provider_reference.startswith(DRY_RUN_PREFIX):
            raise ProviderError("CANCEL_NOT_POSSIBLE",
                                "Una ejecución dry-run ya ha terminado; no puede cancelarse.")
        self._request_stop(provider_reference)
        return self.poll(provider_reference, request)
