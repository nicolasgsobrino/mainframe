"""Provider AWS con botocore Stubber: nunca se llama a AWS real ni en dry-run."""
from __future__ import annotations

from dataclasses import replace

import boto3
import pytest
from botocore.stub import ANY, Stubber
from pydantic import ValidationError as PydanticValidationError
from test_providers_mock import patch_request

from app.config import ConfigurationError, Settings
from app.providers import get_patch_provider, get_restore_provider
from app.providers.aws_ssm_automation import (
    STATUS_MAP,
    AwsSsmAutomationPatchProvider,
    map_status,
)
from app.providers.base import ExecutionStatus, ProviderError, Target

INSTANCE = "i-0123456789abcdef0"
# AutomationExecutionId real: identificador con formato UUID (36 caracteres).
EXECUTION_ID = "11111111-2222-3333-4444-555555555555"


def aws_target() -> Target:
    return Target(logical_target_id="SRV-1001", instance_id=INSTANCE, environment="development")


def request_with_instance(dry_run: bool = True, target: Target | None = None):
    return replace(patch_request(dry_run=dry_run), targets=(target or aws_target(),))


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
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.start(request_with_instance(dry_run=True), "key-1")

    assert execution.status is ExecutionStatus.DRY_RUN
    assert execution.provider_reference.startswith("dryrun:")
    # Si se hubiese llamado a StartAutomationExecution, el Stubber habría fallado.
    ssm_stub.assert_no_pending_responses()


def test_real_start_uses_configured_runbook_and_client_token(aws_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    stub_describe_instance(ec2_stub)
    stub_instance_information(ssm_stub)
    ssm_stub.add_response(
        "start_automation_execution", {"AutomationExecutionId": EXECUTION_ID},
        {"DocumentName": "AWS-RunPatchBaseline", "Parameters": ANY, "Mode": "Auto",
         "ClientToken": ANY, "Tags": ANY})
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.start(request_with_instance(dry_run=False), "key-1")

    assert execution.provider_reference == EXECUTION_ID
    assert execution.status is ExecutionStatus.RUNNING
    ssm_stub.assert_no_pending_responses()


def test_start_fails_when_runbook_not_allowlisted(aws_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    aws_settings.patch_runbook_name = "AWS-RunShellScript"
    stub_describe_instance(ec2_stub)
    stub_instance_information(ssm_stub)
    provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)

    with pytest.raises(ProviderError) as excinfo:
        provider.start(request_with_instance(dry_run=False), "key-1")
    assert excinfo.value.code == "RUNBOOK_NOT_ALLOWED"


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
