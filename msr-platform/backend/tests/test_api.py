"""Contrato HTTP: 202 en despliegue, 409/422/404 y formato uniforme de error."""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MSR_JOBS_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("MSR_PATCH_PROVIDER", "mock")
    monkeypatch.setenv("MSR_RESTORE_PROVIDER", "mock")
    monkeypatch.setenv("MSR_MOCK_JOB_DURATION_SECONDS", "1")
    from app import config

    config.get_settings.cache_clear()
    import app.store as store_module

    importlib.reload(store_module)
    import app.main as main_module

    importlib.reload(main_module)
    yield TestClient(main_module.app)
    config.get_settings.cache_clear()


def deploying_task(client: TestClient) -> str:
    return next(t["id"] for t in client.get("/api/tasks").json() if t["phase_index"] == 5)


def test_execution_endpoint_exposes_provider_without_secrets(client):
    body = client.get("/api/execution").json()
    assert body["patch_provider"] == "mock"
    assert set(body) == {"patch_provider", "restore_provider", "dry_run",
                         "poll_interval_seconds", "region"}


def test_deployment_approval_returns_202_with_the_active_job(client):
    tid = deploying_task(client)
    ring = client.get(f"/api/tasks/{tid}").json()["rings_done"] + 1
    client.post(f"/api/tasks/{tid}/rings/{ring}/preapprove")

    response = client.post(f"/api/tasks/{tid}/approve", headers={"Idempotency-Key": "k1"})

    assert response.status_code == 202
    body = response.json()
    assert body["active_job"]["state"] == "running"
    assert body["active_job"]["provider"] == "mock"
    assert body["rings_done"] == ring - 1


def test_idempotency_key_replays_instead_of_conflicting(client):
    tid = deploying_task(client)
    ring = client.get(f"/api/tasks/{tid}").json()["rings_done"] + 1
    client.post(f"/api/tasks/{tid}/rings/{ring}/preapprove")
    first = client.post(f"/api/tasks/{tid}/approve", headers={"Idempotency-Key": "k1"})
    replay = client.post(f"/api/tasks/{tid}/approve", headers={"Idempotency-Key": "k1"})

    assert replay.status_code == 202
    assert replay.json()["active_job"]["id"] == first.json()["active_job"]["id"]


def test_concurrent_approval_returns_409_with_error_envelope(client):
    tid = deploying_task(client)
    ring = client.get(f"/api/tasks/{tid}").json()["rings_done"] + 1
    client.post(f"/api/tasks/{tid}/rings/{ring}/preapprove")
    client.post(f"/api/tasks/{tid}/approve", headers={"Idempotency-Key": "k1"})

    conflict = client.post(f"/api/tasks/{tid}/approve", headers={"Idempotency-Key": "k2"})

    assert conflict.status_code == 409
    error = conflict.json()["error"]
    assert error["code"] == "JOB_ALREADY_ACTIVE"
    assert error["correlation_id"]


def test_missing_preapproval_returns_422(client):
    tid = deploying_task(client)
    response = client.post(f"/api/tasks/{tid}/approve")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RING_NOT_PREAPPROVED"


def test_unknown_job_returns_404_with_envelope(client):
    response = client.get("/api/patch-jobs/job-does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_job_endpoints_expose_state_and_events(client):
    tid = deploying_task(client)
    ring = client.get(f"/api/tasks/{tid}").json()["rings_done"] + 1
    client.post(f"/api/tasks/{tid}/rings/{ring}/preapprove")
    job_id = client.post(f"/api/tasks/{tid}/approve").json()["active_job"]["id"]

    detail = client.get(f"/api/patch-jobs/{job_id}").json()
    assert detail["id"] == job_id
    assert detail["events"]
    assert "steps" in detail

    listing = client.get(f"/api/tasks/{tid}/patch-jobs").json()
    assert [j["id"] for j in listing] == [job_id]


def test_cancel_endpoint_cancels_an_active_job(client):
    tid = deploying_task(client)
    ring = client.get(f"/api/tasks/{tid}").json()["rings_done"] + 1
    client.post(f"/api/tasks/{tid}/rings/{ring}/preapprove")
    job_id = client.post(f"/api/tasks/{tid}/approve").json()["active_job"]["id"]

    response = client.post(f"/api/patch-jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["state"] == "cancelled"
    assert client.post(f"/api/patch-jobs/{job_id}/cancel").status_code == 409


def test_non_deployment_phase_stays_synchronous_200(client):
    tid = next(t["id"] for t in client.get("/api/tasks").json() if t["phase_index"] < 5)
    response = client.post(f"/api/tasks/{tid}/approve")
    assert response.status_code == 200
    assert response.json()["active_job"] is None


def test_cors_is_not_a_wildcard(client):
    from app.config import get_settings

    assert "*" not in get_settings().cors_allow_origins
