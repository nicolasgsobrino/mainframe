"""Política de objetivos, allowlist de runbooks y sanitización de salidas."""
from __future__ import annotations

import pytest

from app.policy import (
    PolicyViolation,
    assert_parameters_allowed,
    assert_runbook_allowed,
    evaluate_target,
    redact,
    sanitize_text,
)
from app.providers.base import Target

VALID = "i-0123456789abcdef0"


def aws_target(**kwargs) -> Target:
    base = dict(logical_target_id="SRV-1001", instance_id=VALID, account_id="123456789012",
                region="eu-west-1", tags={"msr-poc": "true"}, environment="development",
                ssm_managed=True)
    base.update(kwargs)
    return Target(**base)


def test_synthetic_cmdb_ids_are_rejected(aws_settings):
    result = evaluate_target(aws_target(instance_id="SRV-1001"), aws_settings,
                             instance_state="running")
    assert not result.allowed
    assert result.error_code == "TARGET_NOT_ALLOWED"


def test_compliant_target_is_allowed(aws_settings):
    result = evaluate_target(aws_target(), aws_settings, instance_state="running")
    assert result.allowed, result.violations


def test_missing_required_tag_is_rejected(aws_settings):
    result = evaluate_target(aws_target(tags={}), aws_settings, instance_state="running")
    assert not result.allowed


def test_wrong_region_is_rejected(aws_settings):
    result = evaluate_target(aws_target(region="us-east-1"), aws_settings, instance_state="running")
    assert not result.allowed


def test_account_allowlist_is_enforced(aws_settings):
    aws_settings.allowed_account_ids = ["999999999999"]
    result = evaluate_target(aws_target(), aws_settings, instance_state="running")
    assert not result.allowed


def test_terminated_instance_is_not_ready(aws_settings):
    result = evaluate_target(aws_target(), aws_settings, instance_state="terminated")
    assert not result.allowed
    assert result.error_code == "TARGET_NOT_READY"


def test_instance_not_managed_by_ssm_is_rejected(aws_settings):
    result = evaluate_target(aws_target(ssm_managed=False), aws_settings, instance_state="running")
    assert not result.allowed


def test_runbook_must_be_allowlisted(aws_settings):
    assert assert_runbook_allowed("AWS-RunPatchBaseline", aws_settings)
    with pytest.raises(PolicyViolation):
        assert_runbook_allowed("AWS-RunShellScript", aws_settings)
    with pytest.raises(PolicyViolation):
        assert_runbook_allowed("", aws_settings)


def test_parameters_reject_unknown_keys_and_shell_metacharacters():
    assert assert_parameters_allowed({"InstanceId": [VALID]}, {"InstanceId"})
    with pytest.raises(PolicyViolation):
        assert_parameters_allowed({"Commands": ["rm -rf /"]}, {"InstanceId"})
    with pytest.raises(PolicyViolation):
        assert_parameters_allowed({"InstanceId": [f"{VALID}; curl evil"]}, {"InstanceId"})


@pytest.mark.parametrize("secret", [
    "AKIAIOSFODNN7EXAMPLE",
    "password: sup3rs3cret",
    "arn:aws:iam::123456789012:role/patching",
    "123456789012",
])
def test_secrets_are_redacted(secret):
    assert secret not in redact(f"output {secret} end")


def test_output_is_truncated():
    assert sanitize_text("a" * 5000, 100).startswith("a" * 100)
    assert "truncado" in sanitize_text("a" * 5000, 100)
