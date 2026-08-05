"""Modelo persistente del laboratorio y distinción rollback / reset_lab."""
from __future__ import annotations

import sqlite3

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


def test_the_autoscaling_group_comes_from_configuration_not_from_the_payload(store, settings):
    settings.lab_autoscaling_group_name = "msr-poc-linux-patching-01-asg"

    registered = store.register_lab_target(
        payload(autoscaling_group_name="asg-de-otro-equipo"))

    assert registered["autoscaling_group_name"] == "msr-poc-linux-patching-01-asg"


def test_a_database_without_the_autoscaling_column_is_migrated(settings, tmp_path):
    """Bases creadas antes de las fases 2.1/2.2 se migran sin perder datos."""
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as legacy:
        legacy.execute(
            """CREATE TABLE lab_targets (
                   logical_lab_id              TEXT PRIMARY KEY,
                   current_instance_id         TEXT,
                   account_id                  TEXT,
                   region                      TEXT,
                   vulnerable_ami_id           TEXT,
                   launch_template_id          TEXT,
                   launch_template_version     TEXT,
                   expected_vulnerable_package TEXT,
                   expected_vulnerable_version TEXT,
                   required_tags               TEXT NOT NULL DEFAULT '{}',
                   last_reset_job_id           TEXT,
                   updated_at                  TEXT NOT NULL)""")
        legacy.execute(
            "INSERT INTO lab_targets (logical_lab_id, current_instance_id, updated_at) "
            "VALUES (?, ?, ?)", (LAB_ID, INSTANCE, "2026-01-01T00:00:00+00:00"))

    migrated = JobRepository(str(path))
    try:
        lab = migrated.get_lab_target(LAB_ID)
        assert lab is not None
        assert lab.current_instance_id == INSTANCE
        assert lab.autoscaling_group_name is None
        assert lab.candidate_releasever is None
        assert lab.expected_fixed_kernel is None
    finally:
        migrated.close()


def test_the_releasever_and_fixed_kernel_come_from_configuration(store):
    """El payload no puede fijar el releasever ni el kernel esperado."""
    registered = store.register_lab_target(payload(
        candidate_releasever="2023.01.19700101",
        expected_fixed_kernel="0.0.0-0.amzn2023.x86_64"))

    assert registered["candidate_releasever"] == store.settings.patch_releasever
    assert registered["expected_fixed_kernel"] == store.settings.patch_expected_fixed_kernel


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
