"""Fase 1.1: con MSR_DRY_RUN=false la política es fail-closed."""
from __future__ import annotations

import pytest

from app.config import ConfigurationError, Settings
from app.runbooks import (
    DEFAULT_PATCH_RUNBOOK,
    DEFAULT_ROLLBACK_RUNBOOK,
)

REQUIRED = (
    "MSR_ALLOWED_ACCOUNT_IDS",
    "MSR_ALLOWED_REGIONS",
    "MSR_ALLOWED_ENVIRONMENTS",
    "MSR_REQUIRED_TARGET_TAG_KEY",
    "MSR_REQUIRED_TARGET_TAG_VALUE",
    "MSR_ALLOWED_RUNBOOKS",
    "MSR_SANDBOX_INSTANCE_ID",
)


def real_settings(**overrides) -> Settings:
    data = {
        "_env_file": None,
        "patch_provider": "aws-automation",
        "restore_provider": "aws-automation",
        "dry_run": False,
        "aws_region": "eu-west-1",
        "patch_runbook_name": DEFAULT_PATCH_RUNBOOK,
        "rollback_runbook_name": DEFAULT_ROLLBACK_RUNBOOK,
        "allowed_account_ids": ["123456789012"],
        "allowed_regions": ["eu-west-1"],
        "allowed_environments": ["development"],
        "sandbox_instance_id": "i-0123456789abcdef0",
    }
    data.update(overrides)
    return Settings(**data)


def test_defaults_are_mock_and_dry_run():
    settings = Settings(_env_file=None)
    assert settings.patch_provider == "mock"
    assert settings.restore_provider == "mock"
    assert settings.dry_run is True
    assert settings.execution_mode() == "mock"
    assert settings.real_aws_execution() is False
    settings.validate_for_providers()  # el modo mock arranca sin configuración AWS


def test_a_fully_configured_real_policy_is_accepted():
    settings = real_settings()
    settings.validate_for_providers()
    assert settings.execution_mode() == "aws-real"
    assert settings.real_aws_execution() is True


def test_empty_allowlists_do_not_mean_allow_all_in_real_mode():
    settings = real_settings(allowed_account_ids=[], allowed_regions=[],
                             allowed_environments=[])
    with pytest.raises(ConfigurationError) as excinfo:
        settings.validate_for_providers()
    message = str(excinfo.value)
    assert "MSR_ALLOWED_ACCOUNT_IDS" in message
    assert "MSR_ALLOWED_REGIONS" in message
    assert "MSR_ALLOWED_ENVIRONMENTS" in message


@pytest.mark.parametrize("field,empty", [
    ("allowed_account_ids", []),
    ("allowed_regions", []),
    ("allowed_environments", []),
    ("required_target_tag_key", ""),
    ("required_target_tag_value", ""),
    ("allowed_runbooks", []),
])
def test_each_missing_requirement_blocks_real_execution(field, empty):
    settings = real_settings(**{field: empty})
    with pytest.raises(ConfigurationError):
        settings.validate_for_providers()


def test_real_execution_does_not_require_an_automation_service_role():
    """La cuenta no permite crear un service role: Automation usa al iniciador."""
    settings = real_settings(automation_assume_role_arn="")
    settings.validate_for_providers()
    assert settings.real_aws_execution() is True


def test_real_execution_does_not_require_an_application_role_to_assume():
    """Sin MSR_AWS_ROLE_ARN el backend usa la cadena estándar de boto3."""
    settings = real_settings(aws_role_arn="")
    settings.validate_for_providers()
    assert settings.aws_role_arn == ""


def test_real_execution_requires_some_resolvable_target_identity():
    settings = real_settings(sandbox_instance_id="", sandbox_logical_target_id="",
                             lab_logical_id="")
    with pytest.raises(ConfigurationError) as excinfo:
        settings.validate_for_providers()
    assert "MSR_SANDBOX_INSTANCE_ID" in str(excinfo.value)


def test_a_resolvable_logical_lab_id_replaces_a_fixed_instance_id():
    """El laboratorio cambia de Instance ID en cada reset: basta el ID lógico."""
    settings = real_settings(sandbox_instance_id="", lab_logical_id="linux-patching-01")
    settings.validate_for_providers()
    assert settings.real_aws_execution() is True


def test_dry_run_is_less_restrictive_but_clearly_identified():
    settings = real_settings(dry_run=True, allowed_account_ids=[], allowed_regions=[],
                             allowed_environments=[], sandbox_instance_id="")
    settings.validate_for_providers()  # el dry-run no exige la allowlist completa
    assert settings.execution_mode() == "aws-dry-run"
    assert settings.real_aws_execution() is False
