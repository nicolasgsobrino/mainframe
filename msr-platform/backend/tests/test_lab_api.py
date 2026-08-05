"""Endpoints `/api/labs/*`: estado, validación read-only, reset e historial."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.jobs import JobState, JobType
from app.store import Store

LAB_ID = "linux-patching-01"


@pytest.fixture
def lab_store(settings, repo, monkeypatch) -> Store:
    settings.lab_logical_id = LAB_ID
    store = Store(settings=settings, repository=repo)
    monkeypatch.setattr(main, "STORE", store)
    return store


@pytest.fixture
def lab_client(lab_store) -> TestClient:
    return TestClient(main.app)


def complete(store: Store, job_id: str):
    """Reconcilia el job (el reset simulado dura 0 s en los tests)."""
    return store.get_job(job_id)


def test_lab_status_exposes_the_resolved_instance_and_mode(lab_client):
    body = lab_client.get(f"/api/labs/{LAB_ID}").json()

    assert body["instance"]["instance_id"].startswith("i-")
    assert body["resolution_error"] is None
    assert body["advisory_id"] == "ALAS2023-2026-1651"
    assert body["execution_mode"] == "mock"
    assert body["vulnerable_state"] == "vulnerable_expected"
    assert body["required_tags"]["msr-lab-id"] == LAB_ID


def test_unknown_lab_is_a_404(lab_client):
    assert lab_client.get("/api/labs/lab-inexistente").status_code == 404


def test_validate_is_read_only_and_starts_no_job(lab_client, lab_store):
    before = len(lab_store.repo.list_jobs_for_task(lab_store._lab_task_id(LAB_ID)))

    body = lab_client.post(f"/api/labs/{LAB_ID}/validate").json()

    assert body["read_only"] is True
    assert any(c["check"] == "Instancia resuelta por tags" and c["ok"] for c in body["checks"])
    assert body["advisory_confirmed"] is False  # sólo el precheck del runbook lo confirma
    assert len(lab_store.repo.list_jobs_for_task(lab_store._lab_task_id(LAB_ID))) == before


def test_reset_creates_a_reset_lab_job_and_returns_202(lab_client, lab_store):
    response = lab_client.post(f"/api/labs/{LAB_ID}/reset")

    assert response.status_code == 202
    job = response.json()["job"]
    assert job["job_type"] == JobType.RESET_LAB.value
    assert job["request"]["restore_kind"] == "reset_lab"
    assert job["request"]["previous_instance_id"].startswith("i-")


def test_reset_updates_the_instance_id_and_keeps_the_logical_id(lab_client, lab_store):
    previous = lab_client.get(f"/api/labs/{LAB_ID}").json()["instance"]["instance_id"]

    job_id = lab_client.post(f"/api/labs/{LAB_ID}/reset").json()["job"]["id"]
    job = complete(lab_store, job_id)

    assert job.state is JobState.RESTORED
    lab = lab_store.get_lab_target(LAB_ID)
    assert lab["logical_lab_id"] == LAB_ID
    assert lab["current_instance_id"] != previous
    assert lab["last_reset_job_id"] == job_id
    assert lab_store.lab_snapshot(LAB_ID)["vulnerable_state"] == "vulnerable_expected"


def test_reset_does_not_increment_rings_done_and_keeps_history(lab_client, lab_store):
    tid = lab_store._lab_task_id(LAB_ID)
    rings_before = lab_store.pipelines[tid]["rings_done"]

    job_id = lab_client.post(f"/api/labs/{LAB_ID}/reset").json()["job"]["id"]
    complete(lab_store, job_id)

    assert lab_store.pipelines[tid]["rings_done"] <= rings_before
    history = lab_client.get(f"/api/labs/{LAB_ID}/jobs").json()
    assert job_id in [job["id"] for job in history]


def test_reset_does_not_require_a_deployed_ring(lab_client, lab_store):
    tid = lab_store._lab_task_id(LAB_ID)
    lab_store.pipelines[tid]["rings_done"] = 0

    assert lab_client.post(f"/api/labs/{LAB_ID}/reset").status_code == 202


def test_a_second_reset_is_rejected_while_one_is_active(lab_client, lab_store):
    lab_store.settings.mock_restore_duration_seconds = 600
    lab_client.post(f"/api/labs/{LAB_ID}/reset")

    second = lab_client.post(f"/api/labs/{LAB_ID}/reset")

    assert second.status_code == 409


def test_lab_endpoints_never_accept_instance_ids_or_commands(lab_client):
    """Ningún endpoint del laboratorio admite Instance IDs ni comandos libres."""
    payload = {"instance_id": "i-0deadbeefdeadbeef", "commands": ["rm -rf /"],
               "document_name": "AWS-RunShellScript",
               "autoscaling_group_name": "asg-de-otro-equipo",
               "launch_template_id": "lt-0deadbeefdeadbeef",
               "launch_template_version": "$Latest"}

    reset = lab_client.post(f"/api/labs/{LAB_ID}/reset", json=payload)

    assert reset.status_code == 202
    job = reset.json()["job"]
    assert job["targets"][0]["instance_id"] != payload["instance_id"]
    for forbidden in ("commands", "document_name", "autoscaling_group_name",
                      "launch_template_id", "launch_template_version"):
        assert forbidden not in job["request"]


def test_lab_status_exposes_the_autoscaling_group_as_read_only(lab_client, lab_store):
    """El ASG lo fija la IaC: la UI lo muestra, nunca lo elige."""
    lab_store.settings.lab_autoscaling_group_name = "msr-poc-linux-patching-01-asg"
    lab_store.register_lab_target({"logical_lab_id": LAB_ID,
                                   "autoscaling_group_name": "asg-de-otro-equipo"})

    body = lab_client.get(f"/api/labs/{LAB_ID}").json()

    assert body["lab"]["autoscaling_group_name"] == "msr-poc-linux-patching-01-asg"
