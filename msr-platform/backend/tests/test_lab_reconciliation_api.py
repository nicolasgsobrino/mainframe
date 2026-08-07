"""Fase 2.6: endpoints de reconciliación del laboratorio y estado persistido."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from lab_fakes import ASG_NAME, FakeLabAwsProvider, FakeLabWorld
from test_rehydration import FrozenClock

from app import engine, main
from app.jobs import JobState
from app.lab import LAB_STATE_PATCHED, RECONCILE_READY
from app.providers.mock_patch import MockPatchProvider
from app.repository import JobRepository
from app.store import Store

LAB_ID = "linux-patching-01"


@pytest.fixture
def lab_store(settings, repo, monkeypatch) -> Store:
    settings.lab_logical_id = LAB_ID
    store = Store(settings=settings, repository=repo)
    monkeypatch.setattr(main, "STORE", store)
    monkeypatch.setattr(main, "settings", settings)
    return store


@pytest.fixture
def client(lab_store) -> TestClient:
    return TestClient(main.app)


def test_reconciliation_status_reports_the_mode_without_calling_aws(client):
    body = client.get(f"/api/labs/{LAB_ID}/reconciliation").json()

    assert body["logical_lab_id"] == LAB_ID
    assert body["execution_mode"] == "mock"
    assert body["reconcile_on_startup"] is False
    assert body["lock"] is None
    assert body["last_result"] is None


def test_reconciliation_status_of_an_unknown_lab_is_a_404(client):
    assert client.get("/api/labs/lab-inexistente/reconciliation").status_code == 404


def test_reconcile_leaves_the_lab_ready_and_is_reflected_in_the_status(client):
    result = client.post(f"/api/labs/{LAB_ID}/reconcile").json()

    assert result["ready"] is True
    assert result["state"] == RECONCILE_READY
    status = client.get(f"/api/labs/{LAB_ID}/reconciliation").json()
    assert status["reconciliation_state"] == RECONCILE_READY
    assert status["current_instance_id"] == result["instance_id"]
    assert status["lock"] is None  # el lock se libera siempre
    snapshot = client.get(f"/api/labs/{LAB_ID}").json()
    assert snapshot["reconciliation"]["reconciliation_state"] == RECONCILE_READY


def test_reconcile_of_an_unknown_lab_is_a_404(client):
    assert client.post("/api/labs/lab-inexistente/reconcile").status_code == 404


def test_a_real_reset_requires_explicit_confirmation(settings, repo, monkeypatch):
    settings.lab_logical_id = LAB_ID
    settings.lab_autoscaling_group_name = ASG_NAME
    settings.patch_provider = "aws-automation"
    settings.restore_provider = "aws-automation"
    settings.dry_run = False
    settings.allowed_account_ids = ["123456789012"]
    settings.allowed_regions = ["eu-west-1"]
    settings.allowed_environments = ["development"]
    settings.lab_environment = "development"
    provider = FakeLabAwsProvider(FakeLabWorld(LAB_ID))
    store = Store(settings=settings, repository=JobRepository(settings.jobs_db_absolute_path),
                  patch_provider=provider, restore_provider=provider)
    monkeypatch.setattr(main, "STORE", store)
    monkeypatch.setattr(main, "settings", settings)
    client = TestClient(main.app)

    refused = client.post(f"/api/labs/{LAB_ID}/reset", json={"confirmed": False})

    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "LAB_RESET_CONFIRMATION_REQUIRED"
    assert provider.starts == 0
    assert provider.reset_requests == []

    accepted = client.post(f"/api/labs/{LAB_ID}/reset", json={"confirmed": True})

    assert accepted.status_code == 202
    assert len(provider.reset_requests) == 1


def test_a_mock_reset_needs_no_confirmation(client):
    assert client.post(f"/api/labs/{LAB_ID}/reset").status_code == 202


# --- estado persistido tras un parcheo -----------------------------------
def test_a_confirmed_patch_persists_the_patched_state_and_its_report(settings, repo):
    """Tras un parcheo confirmado el laboratorio no puede seguir mostrándose vulnerable."""
    settings.lab_logical_id = LAB_ID
    settings.mock_job_duration_seconds = 10
    clock = FrozenClock()
    lab_store = Store(settings=settings, repository=repo,
                      patch_provider=MockPatchProvider(settings, now_fn=clock))
    lab_store.ensure_lab_ready(LAB_ID)
    tid = lab_store._lab_task_id(LAB_ID)
    ring_no = engine.RING_DEFS[lab_store.pipelines[tid]["rings_done"]][0]
    lab_store.tasks[tid]["track"] = "A"
    lab_store.preapprove_ring(tid, ring_no)
    job = lab_store.start_ring_patch_job(tid, "key-patch")
    clock.advance(11)
    job = lab_store.reconcile_job(job)

    assert job.state is JobState.SUCCEEDED
    assert job.result_payload["report"]  # el report del runbook viaja con el job
    lab = lab_store.repo.get_lab_target(LAB_ID)
    assert lab.lab_state == LAB_STATE_PATCHED
    assert lab.last_patch_job_id == job.id
    assert lab.advisory_applicable is False
    assert lab.current_kernel
    snapshot = lab_store.lab_snapshot(LAB_ID)
    assert snapshot["vulnerable_state"] == LAB_STATE_PATCHED
    assert snapshot["last_patch_job_id"] == job.id
    assert lab_store.repo.list_jobs_for_task(tid)
