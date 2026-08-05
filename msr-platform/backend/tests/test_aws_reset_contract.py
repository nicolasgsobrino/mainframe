"""Contrato del runbook de reset del laboratorio (sin llamadas reales a AWS)."""
from __future__ import annotations

import uuid

import boto3
import pytest
from botocore.stub import Stubber

from app.providers.aws_ssm_automation import AwsSsmAutomationRestoreProvider
from app.providers.base import (
    RESTORE_KIND_RESET_LAB,
    ExecutionStatus,
    ProviderError,
    RestoreRequest,
    Target,
)
from app.runbooks import (
    DEFAULT_RESET_RUNBOOK,
    OPERATION_RESET_LAB,
    RunbookContractError,
    contract_for,
    validate_parameters,
)

INSTANCE = "i-0123456789abcdef0"
NEW_INSTANCE = "i-0fedcba9876543210"
EXECUTION_ID = "11111111-2222-3333-4444-555555555555"
ASSUME_ROLE = "arn:aws:iam::123456789012:role/MSR-AutomationRole"
LAUNCH_TEMPLATE = "lt-0123456789abcdef0"
CLIENT_TOKEN = str(uuid.uuid5(uuid.NAMESPACE_URL, "msr-platform/key-reset"))


@pytest.fixture
def clients():
    ssm = boto3.client("ssm", region_name="eu-west-1", aws_access_key_id="test",
                       aws_secret_access_key="test")
    ec2 = boto3.client("ec2", region_name="eu-west-1", aws_access_key_id="test",
                       aws_secret_access_key="test")
    with Stubber(ssm) as ssm_stub, Stubber(ec2) as ec2_stub:
        yield ssm, ec2, ssm_stub, ec2_stub


@pytest.fixture
def reset_settings(aws_real_settings):
    aws_real_settings.lab_launch_template_id = LAUNCH_TEMPLATE
    aws_real_settings.lab_launch_template_version = "3"
    return aws_real_settings


def reset_request(dry_run: bool = False) -> RestoreRequest:
    return RestoreRequest(
        job_id="job-reset", task_id="RTASK900900", ring_number=0,
        targets=(Target(logical_target_id="linux-patching-01", instance_id=INSTANCE,
                        environment="development", operating_system="Linux/UNIX"),),
        reason="reset del laboratorio", target_version="", dry_run=dry_run,
        correlation_id="corr-reset", restore_kind=RESTORE_KIND_RESET_LAB,
        task_snapshot={"track": "A"})


def stub_describe_instance(ec2_stub):
    ec2_stub.add_response(
        "describe_instances",
        {"Reservations": [{"OwnerId": "123456789012", "Instances": [{
            "InstanceId": INSTANCE, "State": {"Name": "running"},
            "Placement": {"AvailabilityZone": "eu-west-1a"},
            "PlatformDetails": "Linux/UNIX",
            "Tags": [{"Key": "msr-poc", "Value": "true"}]}]}]},
        {"InstanceIds": [INSTANCE]})


def stub_common(ssm_stub, ec2_stub):
    stub_describe_instance(ec2_stub)
    ssm_stub.add_response(
        "describe_instance_information",
        {"InstanceInformationList": [{"InstanceId": INSTANCE, "PingStatus": "Online"}]},
        {"Filters": [{"Key": "InstanceIds", "Values": [INSTANCE]}]})
    ssm_stub.add_response(
        "describe_document",
        {"Document": {"Name": DEFAULT_RESET_RUNBOOK, "DocumentType": "Automation",
                      "Status": "Active"}},
        {"Name": DEFAULT_RESET_RUNBOOK})


def test_reset_sends_exactly_the_declared_parameters(reset_settings, clients):
    ssm, ec2, ssm_stub, ec2_stub = clients
    stub_common(ssm_stub, ec2_stub)
    ssm_stub.add_response(
        "start_automation_execution", {"AutomationExecutionId": EXECUTION_ID},
        {"DocumentName": DEFAULT_RESET_RUNBOOK,
         "Parameters": {"CurrentInstanceId": [INSTANCE],
                        "LaunchTemplateId": [LAUNCH_TEMPLATE],
                        "LaunchTemplateVersion": ["3"],
                        "CorrelationId": ["corr-reset"],
                        "AutomationAssumeRole": [ASSUME_ROLE]},
         "Mode": "Auto", "ClientToken": CLIENT_TOKEN,
         "Tags": [{"Key": "msr:correlation-id", "Value": "corr-reset"},
                  {"Key": "msr:task-id", "Value": "RTASK900900"},
                  {"Key": "msr:managed-by", "Value": "msr-platform"}]})
    provider = AwsSsmAutomationRestoreProvider(reset_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.start(reset_request(), "key-reset")

    assert execution.provider_reference == EXECUTION_ID
    assert execution.status is ExecutionStatus.RUNNING
    ssm_stub.assert_no_pending_responses()


def test_reset_requires_a_fixed_launch_template_version(reset_settings, clients):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    reset_settings.lab_launch_template_version = ""
    provider = AwsSsmAutomationRestoreProvider(reset_settings, ssm_client=ssm, ec2_client=ec2)

    with pytest.raises(ProviderError) as excinfo:
        provider.start(reset_request(), "key-reset")

    assert excinfo.value.code == "PROVIDER_MISCONFIGURED"
    ssm_stub.assert_no_pending_responses()


def test_reset_poll_returns_the_new_instance_id_sanitized(reset_settings, clients):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    ssm_stub.add_response(
        "get_automation_execution",
        {"AutomationExecution": {"AutomationExecutionId": EXECUTION_ID,
                                 "AutomationExecutionStatus": "Success",
                                 "Outputs": {"recreate.NewInstanceId": [NEW_INSTANCE]}}},
        {"AutomationExecutionId": EXECUTION_ID})
    ssm_stub.add_response(
        "describe_automation_step_executions", {"StepExecutions": []},
        {"AutomationExecutionId": EXECUTION_ID})
    provider = AwsSsmAutomationRestoreProvider(reset_settings, ssm_client=ssm, ec2_client=ec2)

    execution = provider.poll(EXECUTION_ID, reset_request())

    assert execution.new_instance_id == NEW_INSTANCE
    assert execution.status is ExecutionStatus.SUCCEEDED


def test_reset_poll_ignores_an_output_that_is_not_an_instance_id(reset_settings, clients):
    ssm, ec2, ssm_stub, _ec2_stub = clients
    ssm_stub.add_response(
        "get_automation_execution",
        {"AutomationExecution": {"AutomationExecutionId": EXECUTION_ID,
                                 "AutomationExecutionStatus": "Success",
                                 "Outputs": {"recreate.NewInstanceId": ["rm -rf /"]}}},
        {"AutomationExecutionId": EXECUTION_ID})
    ssm_stub.add_response(
        "describe_automation_step_executions", {"StepExecutions": []},
        {"AutomationExecutionId": EXECUTION_ID})
    provider = AwsSsmAutomationRestoreProvider(reset_settings, ssm_client=ssm, ec2_client=ec2)

    assert provider.poll(EXECUTION_ID, reset_request()).new_instance_id is None


@pytest.mark.parametrize("forbidden", ["Commands", "Command", "Script", "SourceInfo",
                                       "Parameters", "DocumentName", "Operation",
                                       "InstallOverrideList", "LogicalLabId"])
def test_reset_contract_forbids_free_form_parameters(forbidden):
    contract = contract_for(OPERATION_RESET_LAB)
    params = {"CurrentInstanceId": [INSTANCE], "LaunchTemplateId": [LAUNCH_TEMPLATE],
              "LaunchTemplateVersion": ["3"], forbidden: ["x"]}

    with pytest.raises(RunbookContractError) as excinfo:
        validate_parameters(contract, params)

    assert excinfo.value.code in ("PARAMETER_FORBIDDEN", "PARAMETER_NOT_DECLARED")


def test_reset_contract_requires_the_launch_template():
    contract = contract_for(OPERATION_RESET_LAB)

    with pytest.raises(RunbookContractError) as excinfo:
        validate_parameters(contract, {"CurrentInstanceId": [INSTANCE]})

    assert excinfo.value.code == "PARAMETER_REQUIRED_MISSING"
