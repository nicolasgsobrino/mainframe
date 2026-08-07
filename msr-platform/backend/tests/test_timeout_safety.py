"""Fase 1.1: un timeout local nunca libera el objetivo ni cancela por su cuenta."""
from __future__ import annotations

import pytest
from conftest import deployment_task
from fakes import FakeAwsProvider

from app import engine
from app.errors import ConflictError, ValidationError
from app.jobs import JobState
from app.providers.base import ExecutionStatus
from app.repository import JobRepository
from app.store import Store

INSTANCE = "i-0123456789abcdef0"


def build_store(settings, provider) -> Store:
    repo = JobRepository(settings.jobs_db_absolute_path)
    settings.dry_run = False
    settings.job_timeout_seconds = 0  # cualquier job supera el timeout local
    return Store(settings=settings, repository=repo,
                 patch_provider=provider, restore_provider=provider)


def running_job(store: Store):
    tid = deployment_task(store)
    ring_no = engine.RING_DEFS[store.pipelines[tid]["rings_done"]][0]
    store.tasks[tid]["track"] = "A"
    store.preapprove_ring(tid, ring_no)
    assets = store._ring_assets(tid, ring_no)
    logical = assets[0].get("logical_target_id") or assets[0]["id"]
    # El Instance ID viaja en el activo: ninguna variable de entorno lo fija.
    assets[0]["instance_id"] = INSTANCE
    return store.start_ring_patch_job(tid, "key-timeout"), tid, logical


def test_local_timeout_requests_stop_without_cancelling_the_job(aws_settings):
    provider = FakeAwsProvider(poll_status=ExecutionStatus.RUNNING)
    store = build_store(aws_settings, provider)
    job, _tid, logical = running_job(store)

    job = store.reconcile_job(job)

    assert job.state is JobState.STOP_REQUESTED
    assert job.state is not JobState.CANCELLED
    assert not job.terminal
    # Se ha vuelto a consultar el estado remoto y se ha pedido la parada.
    assert provider.polls >= 1
    assert provider.cancels == 1
    # El lock del objetivo sigue tomado: el job continúa siendo el activo.
    busy = store.repo.active_job_for_target(logical)
    assert busy is not None and busy.id == job.id


def test_unknown_remote_status_keeps_the_target_busy(aws_settings):
    provider = FakeAwsProvider(poll_error="THROTTLED")
    store = build_store(aws_settings, provider)
    job, tid, logical = running_job(store)

    job = store.reconcile_job(job)

    assert job.state is JobState.REMOTE_STATUS_UNKNOWN
    assert job.unconfirmed and not job.terminal
    assert store.repo.active_job_for_target(logical).id == job.id
    with pytest.raises(ConflictError):
        store.start_ring_patch_job(tid, "key-otro")


def test_confirmed_remote_terminal_state_closes_the_job(aws_settings):
    provider = FakeAwsProvider(poll_status=ExecutionStatus.SUCCEEDED)
    store = build_store(aws_settings, provider)
    job, _tid, logical = running_job(store)

    job = store.reconcile_job(job)

    assert job.state is JobState.SUCCEEDED
    assert job.terminal
    assert store.repo.active_job_for_target(logical) is None


def test_admin_reconciliation_closes_an_unconfirmed_job_with_audit_event(aws_settings):
    provider = FakeAwsProvider(poll_error="PERMISSION_DENIED")
    store = build_store(aws_settings, provider)
    job, _tid, logical = running_job(store)
    job = store.reconcile_job(job)
    assert job.unconfirmed

    resolved = store.admin_resolve_job(job.id, "failed", "verificado en la consola de AWS",
                                       actor="sre@bank.example")

    assert resolved.state is JobState.FAILED
    assert resolved.terminal
    assert store.repo.active_job_for_target(logical) is None
    messages = [e.message for e in store.repo.get_job(job.id, with_events=True).events]
    assert any("Reconciliación manual" in m for m in messages)


def test_admin_reconciliation_rejects_a_confirmed_job(aws_settings):
    provider = FakeAwsProvider(poll_status=ExecutionStatus.SUCCEEDED)
    store = build_store(aws_settings, provider)
    job, _tid, _logical = running_job(store)
    job = store.reconcile_job(job)

    with pytest.raises(ValidationError) as excinfo:
        store.admin_resolve_job(job.id, "failed", "no procede")
    assert excinfo.value.code == "JOB_NOT_UNCONFIRMED"


def test_mock_job_still_times_out_locally(store):
    """Sin ejecución remota viva el timeout local sí es terminal."""
    tid = deployment_task(store)
    ring_no = engine.RING_DEFS[store.pipelines[tid]["rings_done"]][0]
    store.preapprove_ring(tid, ring_no)
    store.settings.job_timeout_seconds = 0
    store.settings.mock_job_duration_seconds = 600
    job = store.start_ring_patch_job(tid, "key-mock-timeout")

    job = store.reconcile_job(job)

    assert job.state is JobState.TIMED_OUT
    assert job.terminal
