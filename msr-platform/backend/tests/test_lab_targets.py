"""Modelo persistente del laboratorio y distinción rollback / reset_lab."""
from __future__ import annotations

import pytest

from app.errors import NotFoundError, ValidationError
from app.jobs import JobType
from app.repository import JobRepository

LAB_ID = "lab-payments-linux"
INSTANCE = "i-0123456789abcdef0"


def payload(**overrides) -> dict:
    data = {
        "logical_lab_id": LAB_ID,
        "current_instance_id": INSTANCE,
        "account_id": "123456789012",
        "region": "eu-west-1",
        "vulnerable_ami_id": "ami-0123456789abcdef0",
        "launch_template_id": "lt-0123456789abcdef0",
        "launch_template_version": "3",
        "expected_vulnerable_package": "openssl",
        "expected_vulnerable_version": "1.1.1k-1",
        "required_tags": {"msr-poc": "true"},
    }
    data.update(overrides)
    return data


def test_lab_target_is_persisted_and_survives_a_new_repository(store, settings):
    registered = store.register_lab_target(payload())

    assert registered["logical_lab_id"] == LAB_ID
    assert registered["current_instance_id"] == INSTANCE
    assert registered["updated_at"]

    repo_2 = JobRepository(settings.jobs_db_absolute_path)
    try:
        reloaded = repo_2.get_lab_target(LAB_ID)
        assert reloaded is not None
        assert reloaded.launch_template_version == "3"
        assert reloaded.required_tags == {"msr-poc": "true"}
    finally:
        repo_2.close()


def test_lab_target_rejects_an_invalid_instance_id(store):
    with pytest.raises(ValidationError) as excinfo:
        store.register_lab_target(payload(current_instance_id="APP-1001"))
    assert excinfo.value.code == "LAB_TARGET_INVALID"


def test_lab_target_requires_a_logical_id(store):
    with pytest.raises(ValidationError):
        store.register_lab_target(payload(logical_lab_id=" "))


def test_unknown_lab_target_is_reported_as_missing(store):
    with pytest.raises(NotFoundError):
        store.get_lab_target("lab-inexistente")


def test_reset_lab_is_a_different_operation_than_rollback(store):
    """`reset_lab` recrea el laboratorio; `rollback` recupera un fallo."""
    lab_id = store.settings.lab_logical_id

    reset = store.start_lab_reset_job(lab_id, idempotency_key="key-reset")

    assert reset.job_type is JobType.RESET_LAB
    assert reset.request_payload["restore_kind"] == "reset_lab"
    assert store.get_lab_target(lab_id)["last_reset_job_id"] == reset.id


def test_reset_lab_requires_a_registered_lab(store):
    with pytest.raises(NotFoundError):
        store.start_lab_reset_job("lab-inexistente")


def test_job_history_reset_keeps_the_lab_configuration(store):
    store.register_lab_target(payload())
    store.reset(clear_jobs=True)

    assert store.get_lab_target(LAB_ID)["current_instance_id"] == INSTANCE
