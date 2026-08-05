"""Provider AWS con botocore Stubber: nunca se llama a AWS real ni en dry-run."""
from __future__ import annotations

import pathlib
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from botocore.stub import Stubber
from pydantic import ValidationError as PydanticValidationError
from test_providers_mock import patch_request

from app import seed
from app.config import ConfigurationError, Settings
from app.providers import get_patch_provider, get_restore_provider
from app.providers.aws_ssm_automation import (
    STATUS_MAP,
    AwsSsmAutomationPatchProvider,
    map_status,
    sanitize_session_name,
)
from app.providers.base import ExecutionStatus, ProviderError, Target
from app.runbooks import (
    DEFAULT_PATCH_RUNBOOK,
    OPERATION_PATCH,
    RunbookContractError,
    contract_for,
    resolve_runbook,
    validate_parameters,
)

INSTANCE = "i-0123456789abcdef0"
# AutomationExecutionId real: identificador con formato UUID (36 caracteres).
EXECUTION_ID = "11111111-2222-3333-4444-555555555555"
ASSUME_ROLE = "arn:aws:iam::123456789012:role/MSR-AutomationRole"
# ClientToken determinista derivado de la clave de idempotencia "key-1".
CLIENT_TOKEN = str(uuid.uuid5(uuid.NAMESPACE_URL, "msr-platform/key-1"))


def aws_target() -> Target:
    return Target(logical_target_id="SRV-1001", instance_id=INSTANCE, environment="development",
                  operating_system="Linux/UNIX")


def request_with_instance(dry_run: bool = True, target: Target | None = None,
                         track: str | None = "A"):
    request = patch_request(dry_run=dry_run)
    return replace(request, targets=(target or aws_target(),),
                   spec=replace(request.spec, track=track))


@pytest.fixture
def clients():
    ssm = boto3.client("ssm", region_name="eu-west-1", aws_access_key_id="test",
                       aws_secret_access_key="test")
    ec2 = boto3.client("ec2", region_name="eu-west-1", aws_access_key_id="test",
                       aws_secret_access_key="test")
    with Stubber(ssm) as ssm_stub, Stubber(ec2) as ec2_stub:
        yield ssm, ec2, ssm_stub, ec2_stub


def stub_describe_instance(ec2_stub, state="running", tags=None):
    ec2_stub.add_response(
        "describe_instances",
        {"Reservations": [{"OwnerId": "123456789012", "Instances": [{
            "InstanceId": INSTANCE, "State": {"Name": state},
            "Placement": {"AvailabilityZone": "eu-west-1a"},
            "PlatformDetails": "Linux/UNIX",
            "Tags": [{"Key": k, "Value": v} for k, v in (tags or {"msr-poc": "true"}).items()],
        }]}]},
        {"InstanceIds": [INSTANCE]})


def stub_describe_document(ssm_stub, document_type="Automation", name=DEFAULT_PATCH_RUNBOOK):
    ssm_stub.add_response(
        "describe_document",
        {"Document": {"Name": name, "DocumentType": document_type, "Status": "Active"}},
        {"Name": name})


def stub_instance_information(ssm_stub, online=True):
    ssm_stub.add_response(
        "describe_instance_information",
        {"InstanceInformationList": [{"InstanceId": INSTANCE,
                                      "PingStatus": "Online" if online else "ConnectionLost"}]},
        {"Filters": [{"Key": "InstanceIds", "Values": [INSTANCE]}]})


# --- factoría ---------------------------------------------------------------
def test_factory_defaults_to_mock():
    settings = Settings(_env_file=None)
    assert get_patch_provider(settings).name == "mock"
    assert get_restore_provider(settings).name == "mock"
    assert settings.dry_run is True


def test_default_advisory_releasever_and_fixed_kernel_match_the_iac():
    """Fase 2.2: el advisory vigente y su releasever son contrato de la IaC."""
    settings = Settings(_env_file=None)

    assert settings.patch_advisory_id == "ALAS2023-2026-1924"
    assert settings.patch_releasever == "2023.12.20260706"
    assert settings.patch_expected_fixed_kernel == "6.1.176-220.358.amzn2023.x86_64"
    assert seed.LAB_ADVISORY_ID == settings.patch_advisory_id
    assert seed.LAB_RELEASEVER == settings.patch_releasever
    # Y los defaults seguros no cambian.
    assert settings.dry_run is True
    assert settings.patch_provider == "mock"


def test_unknown_provider_is_rejected_at_configuration_time():
    with pytest.raises(PydanticValidationError):
        Settings(_env_file=None, patch_provider="ansible")


def test_factory_rejects_a_provider_set_after_validation():
    settings = Settings(_env_file=None)
    object.__setattr__(settings, "patch_provider", "ansible")
    with pytest.raises(ConfigurationError):
        get_patch_provider(settings)


def test_factory_requires_aws_configuration():
    settings = Settings(_env_file=None, patch_provider="aws-automation")
    with pytest.raises(ConfigurationError) as excinfo:
        get_patch_provider(settings)
    assert "MSR_AWS_REGION" in str(excinfo.value)


def test_factory_builds_aws_provider_without_calling_aws(aws_settings):
    provider = get_patch_provider(aws_settings)
    assert provider.name == "aws-automation"


# --- validate_target (sólo lectura) ----------------------------------------
def test_validate_target_only_uses_read_only_calls(aws_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    stub_describe_instance(ec2_stub)
    stub_instance_information(ssm_stub)
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    result = provider.validate_target(request_with_instance())

    assert result.allowed, result.violations
    assert result.target.account_id == "123456789012"
    assert result.target.region == "eu-west-1"
    ssm_stub.assert_no_pending_responses()
    ec2_stub.assert_no_pending_responses()


def test_validate_target_rejects_terminated_instance(aws_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    stub_describe_instance(ec2_stub, state="terminated")
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    result = provider.validate_target(request_with_instance())

    assert not result.allowed
    assert result.error_code in ("TARGET_NOT_READY", "TARGET_NOT_ALLOWED")


def test_validate_target_rejects_synthetic_cmdb_id(aws_settings, clients):
    ssm, ec2, _ssm_stub, _ec2_stub = clients
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)
    synthetic = request_with_instance(
        target=Target(logical_target_id="SRV-1001", instance_id=None))

    result = provider.validate_target(synthetic)

    assert not result.allowed


# --- start ------------------------------------------------------------------
def test_dry_run_start_does_not_call_start_automation(aws_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    stub_describe_instance(ec2_stub)
    stub_instance_information(ssm_stub)
    stub_describe_document(ssm_stub)
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.start(request_with_instance(dry_run=True), "key-1")

    assert execution.status is ExecutionStatus.DRY_RUN
    assert execution.provider_reference.startswith("dryrun:")
    # Si se hubiese llamado a StartAutomationExecution, el Stubber habría fallado.
    ssm_stub.assert_no_pending_responses()


def test_real_start_uses_configured_runbook_and_client_token(aws_real_settings, clients):
    """Parámetros exactos, sin comodines: el contrato del runbook queda verificado."""
    ssm, ec2, ssm_stub, ec2_stub = clients
    stub_describe_instance(ec2_stub)
    stub_instance_information(ssm_stub)
    stub_describe_document(ssm_stub)
    request = request_with_instance(dry_run=False)
    ssm_stub.add_response(
        "start_automation_execution", {"AutomationExecutionId": EXECUTION_ID},
        {"DocumentName": DEFAULT_PATCH_RUNBOOK,
         "Parameters": {"InstanceId": [INSTANCE],
                        "AutomationAssumeRole": [ASSUME_ROLE]},
         "Mode": "Auto",
         "ClientToken": CLIENT_TOKEN,
         "Tags": [{"Key": "msr:correlation-id", "Value": request.correlation_id},
                  {"Key": "msr:task-id", "Value": request.task_id},
                  {"Key": "msr:managed-by", "Value": "msr-platform"}]})
    provider = AwsSsmAutomationPatchProvider(aws_real_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.start(request, "key-1")

    assert execution.provider_reference == EXECUTION_ID
    assert execution.status is ExecutionStatus.RUNNING
    ssm_stub.assert_no_pending_responses()


def test_start_fails_when_runbook_not_allowlisted(aws_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    aws_settings.patch_runbook_name = "MSR-SomeOtherRunbook"
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    with pytest.raises(ProviderError) as excinfo:
        provider.start(request_with_instance(dry_run=False), "key-1")
    assert excinfo.value.code == "RUNBOOK_NOT_ALLOWED"
    ssm_stub.assert_no_pending_responses()


# --- contrato de runbooks ---------------------------------------------------
def test_command_document_cannot_be_configured_as_automation_runbook(aws_settings):
    aws_settings.patch_runbook_name = "AWS-RunPatchBaseline"
    aws_settings.allowed_runbooks = ["AWS-RunPatchBaseline"]

    with pytest.raises(RunbookContractError) as excinfo:
        resolve_runbook(aws_settings, OPERATION_PATCH)
    assert excinfo.value.code == "DOCUMENT_TYPE_NOT_SUPPORTED"


def test_run_patch_baseline_never_reaches_start_automation_execution(aws_settings, clients):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    aws_settings.patch_runbook_name = "AWS-RunPatchBaseline"
    aws_settings.allowed_runbooks = ["AWS-RunPatchBaseline"]
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    with pytest.raises(ProviderError) as excinfo:
        provider.start(request_with_instance(dry_run=False), "key-1")

    assert excinfo.value.code == "DOCUMENT_TYPE_NOT_SUPPORTED"
    # Sin respuestas consumidas: no se ha llamado a ninguna API de SSM.
    ssm_stub.assert_no_pending_responses()


def test_describe_document_rejects_a_command_document(aws_real_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    stub_describe_instance(ec2_stub)
    stub_instance_information(ssm_stub)
    stub_describe_document(ssm_stub, document_type="Command")
    provider = AwsSsmAutomationPatchProvider(aws_real_settings, ssm_client=ssm, ec2_client=ec2)

    with pytest.raises(ProviderError) as excinfo:
        provider.start(request_with_instance(dry_run=False), "key-1")

    assert excinfo.value.code == "DOCUMENT_TYPE_NOT_SUPPORTED"
    ssm_stub.assert_no_pending_responses()


def test_dry_run_accepts_an_allowed_automation_document(aws_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    stub_describe_instance(ec2_stub)
    stub_instance_information(ssm_stub)
    stub_describe_document(ssm_stub)
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.start(request_with_instance(dry_run=True), "key-1")

    assert execution.status is ExecutionStatus.DRY_RUN
    assert "Automation" in execution.steps[0].output
    ssm_stub.assert_no_pending_responses()


def test_undeclared_parameter_is_rejected():
    contract = contract_for(OPERATION_PATCH)
    with pytest.raises(RunbookContractError) as excinfo:
        validate_parameters(contract, {"InstanceId": [INSTANCE], "Unknown": ["x"]})
    assert excinfo.value.code == "PARAMETER_NOT_DECLARED"


def test_generic_operation_parameter_is_forbidden():
    contract = contract_for(OPERATION_PATCH)
    with pytest.raises(RunbookContractError) as excinfo:
        validate_parameters(contract, {"InstanceId": [INSTANCE], "Operation": ["Install"]})
    assert excinfo.value.code == "PARAMETER_FORBIDDEN"


def test_missing_required_parameter_is_rejected():
    contract = contract_for(OPERATION_PATCH)
    with pytest.raises(RunbookContractError) as excinfo:
        validate_parameters(contract, {"AutomationAssumeRole": [ASSUME_ROLE]})
    assert excinfo.value.code == "PARAMETER_REQUIRED_MISSING"


def test_provider_does_not_hide_critical_parameters_with_stub_any():
    """El propio suite no puede ocultar parámetros críticos con el comodín de botocore."""
    wildcard = "".join(("A", "N", "Y"))
    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert not [line for line in imports if wildcard in line]
    assert f'"Parameters": {wildcard}' not in source


@pytest.mark.parametrize("track", ["B", "C", "", None])
def test_only_track_a_is_accepted_by_the_aws_provider(aws_settings, clients, track):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    with pytest.raises(ProviderError) as excinfo:
        provider.start(request_with_instance(dry_run=False, track=track), "key-1")

    assert excinfo.value.code == "UNSUPPORTED_REMEDIATION_TRACK"
    ssm_stub.assert_no_pending_responses()


# --- STS AssumeRole ---------------------------------------------------------
def test_assume_role_uses_sts_and_sanitizes_the_session_name(aws_settings, clients):
    ssm, ec2, _ssm_stub, _ec2_stub = clients
    aws_settings.aws_role_arn = "arn:aws:iam::123456789012:role/MSR-Caller"
    sts = boto3.client("sts", region_name="eu-west-1", aws_access_key_id="test",
                       aws_secret_access_key="test")
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    with Stubber(sts) as sts_stub:
        sts_stub.add_response(
            "assume_role",
            {"Credentials": {"AccessKeyId": "ASIATEMPKEY123456789", "SecretAccessKey": "secret",
                             "SessionToken": "token", "Expiration": expiry},
             "AssumedRoleUser": {"AssumedRoleId": "AROA:msr", "Arn": aws_settings.aws_role_arn}},
            {"RoleArn": aws_settings.aws_role_arn,
             "RoleSessionName": "msr-corr-abc-123",
             "DurationSeconds": 3600})
        provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2,
                                                 sts_client=sts)
        provider._correlation_id = "corr/abc 123"

        credentials = provider._assume_role_credentials()

        assert credentials["aws_access_key_id"] == "ASIATEMPKEY123456789"
        # La sesión se reutiliza mientras no caduque (una sola llamada a STS).
        assert provider._assume_role_credentials() is credentials
        sts_stub.assert_no_pending_responses()


def test_session_name_is_sanitized_and_truncated():
    assert sanitize_session_name("corr/abc 123") == "corr-abc-123"
    assert len(sanitize_session_name("x" * 200)) == 64
    assert sanitize_session_name("") == "msr-platform"


def test_step_execution_failure_becomes_a_sanitized_warning(aws_settings, clients):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    ssm_stub.add_response(
        "get_automation_execution",
        {"AutomationExecution": {"AutomationExecutionId": EXECUTION_ID,
                                 "AutomationExecutionStatus": "InProgress",
                                 "CurrentStepName": "installPatches"}},
        {"AutomationExecutionId": EXECUTION_ID})
    ssm_stub.add_client_error(
        "describe_automation_step_executions", service_error_code="AccessDeniedException",
        service_message="not authorized for AKIAIOSFODNN7EXAMPLE")
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.poll(EXECUTION_ID, request_with_instance(dry_run=False))

    # El estado de GetAutomationExecution se conserva y el fallo no se oculta.
    assert execution.status is ExecutionStatus.RUNNING
    assert execution.warning_code == "PERMISSION_DENIED"
    assert "AKIAIOSFODNN7EXAMPLE" not in (execution.warning_message or "")
    ssm_stub.assert_no_pending_responses()


# --- poll -------------------------------------------------------------------
def test_poll_maps_status_and_sanitizes_output(aws_settings, clients):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    ssm_stub.add_response(
        "get_automation_execution",
        {"AutomationExecution": {"AutomationExecutionId": EXECUTION_ID,
                                 "AutomationExecutionStatus": "Failed",
                                 "FailureMessage": "failed with token: sup3rs3cret",
                                 "CurrentStepName": "installPatches"}},
        {"AutomationExecutionId": EXECUTION_ID})
    ssm_stub.add_response(
        "describe_automation_step_executions",
        {"StepExecutions": [{"StepName": "installPatches", "Action": "aws:runCommand",
                             "StepStatus": "Failed",
                             "FailureMessage": "AKIAIOSFODNN7EXAMPLE leaked"}]},
        {"AutomationExecutionId": EXECUTION_ID})
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.poll(EXECUTION_ID, request_with_instance(dry_run=False))

    assert execution.status is ExecutionStatus.FAILED
    assert execution.raw_status == "Failed"
    assert "sup3rs3cret" not in (execution.error_message or "")
    assert "AKIAIOSFODNN7EXAMPLE" not in execution.steps[0].output
    assert execution.steps[0].status == "failed"


def test_unknown_aws_status_is_treated_as_running():
    assert map_status("SomeFutureStatus") is ExecutionStatus.RUNNING
    assert map_status(None) is ExecutionStatus.RUNNING
    assert STATUS_MAP["Success"] is ExecutionStatus.SUCCEEDED


def test_poll_on_dry_run_reference_does_not_call_aws(aws_settings, clients):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.poll("dryrun:job-1", request_with_instance())

    assert execution.status is ExecutionStatus.DRY_RUN
    ssm_stub.assert_no_pending_responses()


def test_cancel_does_not_assume_cancelled_state(aws_settings, clients):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    ssm_stub.add_response("stop_automation_execution", {},
                          {"AutomationExecutionId": EXECUTION_ID, "Type": "Cancel"})
    ssm_stub.add_response(
        "get_automation_execution",
        {"AutomationExecution": {"AutomationExecutionId": EXECUTION_ID,
                                 "AutomationExecutionStatus": "Cancelling"}},
        {"AutomationExecutionId": EXECUTION_ID})
    ssm_stub.add_response("describe_automation_step_executions", {"StepExecutions": []},
                          {"AutomationExecutionId": EXECUTION_ID})
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.cancel(EXECUTION_ID, request_with_instance(dry_run=False))

    assert execution.status is ExecutionStatus.CANCELLING
    ssm_stub.assert_no_pending_responses()
