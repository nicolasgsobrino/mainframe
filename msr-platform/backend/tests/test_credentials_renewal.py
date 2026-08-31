"""Ciclo de vida de los clientes creados con credenciales temporales de STS.

Ningún test llama a AWS: `assume_role` se sirve con `botocore.stub.Stubber` y los
clientes SSM/EC2 se construyen mediante una subclase que registra con qué
credenciales se han creado.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from botocore.stub import Stubber
from test_providers_mock import patch_request

from app.providers.aws_ssm_automation import AwsSsmAutomationPatchProvider
from app.providers.base import ProviderError, Target

ROLE_ARN = "arn:aws:iam::123456789012:role/MSR-Caller"
FIRST_KEY = "ASIAFIRSTKEY12345678"
SECOND_KEY = "ASIASECONDKEY1234567"
FIRST_SECRET = "first-secret-value"
SECOND_SECRET = "second-secret-value"


class FrozenClock:
    def __init__(self):
        self.now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass
class RecordedClient:
    """Doble de cliente boto3 que recuerda las credenciales de su sesión."""

    service: str
    access_key: str


class RecordingProvider(AwsSsmAutomationPatchProvider):
    """Sustituye la construcción de clientes boto3, sin tocar la lógica de caché."""

    def _client(self, service: str) -> RecordedClient:
        credentials = self._assume_role_credentials()
        client = RecordedClient(service=service, access_key=credentials["aws_access_key_id"])
        self.created.append(client)
        return client

    def __init__(self, *args, **kwargs):
        self.created: list[RecordedClient] = []
        super().__init__(*args, **kwargs)


def sts_client() -> boto3.client:
    return boto3.client("sts", region_name="eu-west-1", aws_access_key_id="test",
                        aws_secret_access_key="test")


def stub_assume_role(stub: Stubber, clock: FrozenClock, access_key: str, secret: str,
                     ttl_seconds: int, session_name: str) -> None:
    stub.add_response(
        "assume_role",
        {"Credentials": {"AccessKeyId": access_key, "SecretAccessKey": secret,
                         "SessionToken": f"token-{access_key}",
                         "Expiration": clock.now + timedelta(seconds=ttl_seconds)},
         "AssumedRoleUser": {"AssumedRoleId": "AROA:msr", "Arn": ROLE_ARN}},
        {"RoleArn": ROLE_ARN, "RoleSessionName": session_name, "DurationSeconds": 3600})


@pytest.fixture
def role_settings(aws_settings):
    aws_settings.aws_role_arn = ROLE_ARN
    return aws_settings


def test_clients_are_rebuilt_when_the_sts_session_is_renewed(role_settings):
    clock = FrozenClock()
    sts = sts_client()
    with Stubber(sts) as sts_stub:
        stub_assume_role(sts_stub, clock, FIRST_KEY, FIRST_SECRET, 300, "msr-corr-1")
        provider = RecordingProvider(role_settings, sts_client=sts, now_fn=clock)
        provider._correlation_id = "corr-1"

        first_ssm, first_ec2 = provider.ssm, provider.ec2
        assert first_ssm.access_key == FIRST_KEY
        # Mientras las credenciales sigan vigentes se reutilizan los clientes.
        assert provider.ssm is first_ssm
        assert provider.ec2 is first_ec2
        assert len(provider.created) == 2

        # Más allá del margen de renovación (expiración - 60 s).
        clock.advance(300)
        stub_assume_role(sts_stub, clock, SECOND_KEY, SECOND_SECRET, 300, "msr-corr-1")

        second_ssm, second_ec2 = provider.ssm, provider.ec2
        assert second_ssm is not first_ssm
        assert second_ec2 is not first_ec2
        assert (second_ssm.access_key, second_ec2.access_key) == (SECOND_KEY, SECOND_KEY)
        assert len(provider.created) == 4
        sts_stub.assert_no_pending_responses()


def test_expired_client_is_never_reused_across_operations(role_settings):
    """El mismo recorrido que hacen `validate_target`, `start`, `poll` y `cancel`."""
    clock = FrozenClock()
    sts = sts_client()
    with Stubber(sts) as sts_stub:
        stub_assume_role(sts_stub, clock, FIRST_KEY, FIRST_SECRET, 120, "msr-corr-2")
        provider = RecordingProvider(role_settings, sts_client=sts, now_fn=clock)
        provider._correlation_id = "corr-2"
        assert provider.ssm.access_key == FIRST_KEY

        clock.advance(120)
        stub_assume_role(sts_stub, clock, SECOND_KEY, SECOND_SECRET, 120, "msr-corr-2")

        keys = {provider.ssm.access_key, provider.ec2.access_key, provider.ssm.access_key}
        assert keys == {SECOND_KEY}, "ninguna operación puede usar la clave caducada"
        assert [c.access_key for c in provider.created].count(FIRST_KEY) == 1
        sts_stub.assert_no_pending_responses()


def test_injected_clients_are_never_replaced_and_skip_assume_role(role_settings):
    ssm = object()
    ec2 = object()
    sts = sts_client()
    with Stubber(sts) as sts_stub:  # sin respuestas: cualquier AssumeRole fallaría
        provider = AwsSsmAutomationPatchProvider(role_settings, ssm_client=ssm, ec2_client=ec2,
                                                 sts_client=sts)
        assert provider.ssm is ssm
        assert provider.ec2 is ec2
        sts_stub.assert_no_pending_responses()


def test_temporary_credentials_do_not_leak_into_logs_or_errors(role_settings, caplog):
    clock = FrozenClock()
    sts = sts_client()
    with Stubber(sts) as sts_stub, caplog.at_level(logging.DEBUG):
        stub_assume_role(sts_stub, clock, FIRST_KEY, FIRST_SECRET, 300, "msr-corr-3")
        provider = RecordingProvider(role_settings, sts_client=sts, now_fn=clock)
        provider._correlation_id = "corr-3"
        credentials = provider._assume_role_credentials()

    assert credentials["aws_secret_access_key"] == FIRST_SECRET
    for secret in (FIRST_SECRET, f"token-{FIRST_KEY}"):
        assert secret not in caplog.text
        assert secret not in repr(provider.created)


def test_assume_role_failure_is_classified_without_exposing_credentials(role_settings):
    sts = sts_client()
    with Stubber(sts) as sts_stub:
        sts_stub.add_client_error("assume_role", service_error_code="AccessDenied",
                                  service_message="not authorized to perform sts:AssumeRole")
        provider = AwsSsmAutomationPatchProvider(role_settings, sts_client=sts)

        with pytest.raises(ProviderError) as excinfo:
            provider._assume_role_credentials()

    assert excinfo.value.code == "PERMISSION_DENIED"
    assert "AssumeRole" not in str(excinfo.value) or FIRST_SECRET not in str(excinfo.value)


def test_validate_target_uses_injected_clients_without_boto3(aws_settings):
    """Los tests siguen pudiendo inyectar clientes: no se construye ninguna sesión."""
    ssm = boto3.client("ssm", region_name="eu-west-1", aws_access_key_id="test",
                       aws_secret_access_key="test")
    ec2 = boto3.client("ec2", region_name="eu-west-1", aws_access_key_id="test",
                       aws_secret_access_key="test")
    with Stubber(ssm), Stubber(ec2) as ec2_stub:
        ec2_stub.add_client_error("describe_instances",
                                  service_error_code="InvalidInstanceID.NotFound")
        provider = AwsSsmAutomationPatchProvider(aws_settings, ssm_client=ssm, ec2_client=ec2)
        request = replace(
            patch_request(dry_run=True),
            targets=(Target(logical_target_id="SRV-1001", instance_id="i-0123456789abcdef0",
                            operating_system="Linux/UNIX"),),
            spec=replace(patch_request().spec, track="A"))

        with pytest.raises(ProviderError) as excinfo:
            provider.validate_target(request)

    assert excinfo.value.code == "TARGET_NOT_FOUND"
