"""Integración del despliegue con jobs: el anillo sólo avanza si el provider gana."""
from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import deployment_task

from app.errors import ConflictError, TargetNotAllowedError, ValidationError
from app.jobs import JobState, JobType
from app.providers.base import (
    ExecutionStatus,
    PatchExecution,
    RestoreExecution,
    TargetPolicyResult,
    utcnow,
)
from app.providers.mock_patch import MockPatchProvider
from app.repository import JobRepository
from app.store import Store


class FrozenClock:
    def __init__(self):
        self.now = utcnow()

    def __call__(self):
        return self.now

    def advance(self, seconds: int):
        self.now += timedelta(seconds=seconds)


class FailingPatchProvider:
    name = "mock"

    def validate_target(self, request):
        return TargetPolicyResult(allowed=True, target=request.primary_target())

    def start(self, request, idempotency_key):
        return PatchExecution(provider=self.name, provider_reference="failing-1",
                              status=ExecutionStatus.RUNNING, dry_run=False)

    def poll(self, provider_reference, request=None):
        return PatchExecution(provider=self.name, provider_reference=provider_reference,
                              status=ExecutionStatus.FAILED, dry_run=False,
                              error_code="AUTOMATION_FAILED", error_message="post-check failed")

    def cancel(self, provider_reference, request=None):
        return PatchExecution(provider=self.name, provider_reference=provider_reference,
                              status=ExecutionStatus.CANCELLED, dry_run=False)


class RejectingPatchProvider(FailingPatchProvider):
    def validate_target(self, request):
        return TargetPolicyResult(allowed=False, error_code="TARGET_NOT_ALLOWED",
                                  message="La instancia no está en la allowlist.")


class DryRunPatchProvider(FailingPatchProvider):
    def start(self, request, idempotency_key):
        return PatchExecution(provider=self.name, provider_reference=f"dryrun:{request.job_id}",
                              status=ExecutionStatus.DRY_RUN, dry_run=True)


def preapprove_next_ring(store: Store, tid: str) -> int:
    ring = store.pipelines[tid]["rings_done"] + 1
    store.preapprove_ring(tid, ring, approver="tester", note="test")
    return ring


def test_approve_creates_job_without_advancing_the_ring(store):
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)
    before = store.pipelines[tid]["rings_done"]

    job = store.start_ring_patch_job(tid, "key-1")

    assert job.job_type is JobType.PATCH
    assert job.state is JobState.RUNNING
    assert store.pipelines[tid]["rings_done"] == before
    assert store.task_detail(tid, reconcile=False)["active_job"]["id"] == job.id


def test_ring_advances_exactly_once_when_the_provider_succeeds(settings, repo):
    clock = FrozenClock()
    settings.mock_job_duration_seconds = 10
    store = Store(settings=settings, repository=repo,
                  patch_provider=MockPatchProvider(settings, now_fn=clock))
    tid = deployment_task(store)
    ring = preapprove_next_ring(store, tid)
    before = store.pipelines[tid]["rings_done"]

    store.start_ring_patch_job(tid, "key-1")
    assert store.pipelines[tid]["rings_done"] == before  # aún en curso

    clock.advance(11)
    detail = store.task_detail(tid)
    assert store.pipelines[tid]["rings_done"] == before + 1
    assert detail["active_job"] is None

    logs_after_first = len(store.pipelines[tid]["logs"])
    store.task_detail(tid)  # reconciliaciones repetidas
    store.task_detail(tid)
    assert store.pipelines[tid]["rings_done"] == before + 1
    assert len(store.pipelines[tid]["logs"]) == logs_after_first

    actions = store.pipelines[tid]["artifacts"]["deployment"]["rings"][ring - 1]["actions"]
    assert actions["steps"], "la evidencia real del job debe quedar en el artefacto"


def test_failed_job_does_not_advance_the_ring(settings, repo):
    store = Store(settings=settings, repository=repo, patch_provider=FailingPatchProvider())
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)
    before = store.pipelines[tid]["rings_done"]

    job = store.start_ring_patch_job(tid, "key-1")
    job = store.reconcile_job(job)

    assert job.state is JobState.FAILED
    assert job.error_code == "AUTOMATION_FAILED"
    assert store.pipelines[tid]["rings_done"] == before


def test_dry_run_job_does_not_advance_the_ring(settings, repo):
    store = Store(settings=settings, repository=repo, patch_provider=DryRunPatchProvider())
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)
    before = store.pipelines[tid]["rings_done"]

    job = store.start_ring_patch_job(tid, "key-1")

    assert job.state is JobState.DRY_RUN
    assert job.terminal
    assert store.pipelines[tid]["rings_done"] == before
    assert any("dry-run" in entry["msg"].lower() for entry in store.pipelines[tid]["logs"])


def test_rejected_target_fails_the_job_and_raises(settings, repo):
    store = Store(settings=settings, repository=repo, patch_provider=RejectingPatchProvider())
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)

    with pytest.raises(TargetNotAllowedError):
        store.start_ring_patch_job(tid, "key-1")

    jobs = store.repo.list_jobs_for_task(tid)
    assert jobs[0].state is JobState.FAILED
    assert jobs[0].error_code == "TARGET_NOT_ALLOWED"


def test_missing_preapproval_is_rejected(store):
    tid = deployment_task(store)
    with pytest.raises(ValidationError) as excinfo:
        store.start_ring_patch_job(tid, "key-1")
    assert excinfo.value.code == "RING_NOT_PREAPPROVED"


def test_second_concurrent_approval_conflicts(store):
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)
    store.start_ring_patch_job(tid, "key-1")
    with pytest.raises(ConflictError):
        store.start_ring_patch_job(tid, "key-2")


def test_same_idempotency_key_replays_the_same_job(store):
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)
    first = store.start_ring_patch_job(tid, "key-1")
    second = store.start_ring_patch_job(tid, "key-1")
    assert first.id == second.id
    assert len(store.repo.list_jobs_for_task(tid)) == 1


def test_job_times_out_and_ring_does_not_advance(settings, repo):
    clock = FrozenClock()
    settings.job_timeout_seconds = 5
    settings.mock_job_duration_seconds = 1000
    store = Store(settings=settings, repository=repo,
                  patch_provider=MockPatchProvider(settings, now_fn=clock))
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)
    before = store.pipelines[tid]["rings_done"]
    job = store.start_ring_patch_job(tid, "key-1")

    job.created_at = job.created_at - timedelta(seconds=10)
    job = store.reconcile_job(job)

    assert job.state is JobState.TIMED_OUT
    assert store.pipelines[tid]["rings_done"] == before


def test_rollback_only_decrements_after_a_successful_restore(store):
    tid = deployment_task(store)
    before = store.pipelines[tid]["rings_done"]
    assert before > 0

    store.rollback(tid, reason="post-check", trigger="auto", idempotency_key="rb-1")

    job = store.repo.list_jobs_for_task(tid)[0]
    assert job.job_type is JobType.ROLLBACK
    assert job.state is JobState.RESTORED
    assert store.pipelines[tid]["rings_done"] == before - 1
    assert store.pipelines[tid]["rollback"]["status"] == "completed"


def test_rollback_in_dry_run_does_not_decrement(settings, repo):
    class DryRunRestoreProvider:
        name = "mock"

        def validate_target(self, request):
            return TargetPolicyResult(allowed=True, target=request.primary_target())

        def start(self, request, idempotency_key):
            return RestoreExecution(provider=self.name,
                                    provider_reference=f"dryrun:{request.job_id}",
                                    status=ExecutionStatus.DRY_RUN, dry_run=True)

        def poll(self, provider_reference, request=None):
            return RestoreExecution(provider=self.name, provider_reference=provider_reference,
                                    status=ExecutionStatus.DRY_RUN, dry_run=True)

    store = Store(settings=settings, repository=repo, restore_provider=DryRunRestoreProvider())
    tid = deployment_task(store)
    before = store.pipelines[tid]["rings_done"]

    store.rollback(tid, idempotency_key="rb-1")

    assert store.pipelines[tid]["rings_done"] == before
    assert store.repo.list_jobs_for_task(tid)[0].state is JobState.DRY_RUN


def test_phases_one_to_five_remain_synchronous(store):
    tid = next(t for t, p in store.pipelines.items() if p["phase_index"] < 5)
    pipeline = store.pipelines[tid]
    index = pipeline["phase_index"]

    detail = store.approve_phase(tid, "key-1")

    assert detail["phase_index"] == index + 1
    assert detail["active_job"] is None
    assert store.repo.list_jobs_for_task(tid) == []


def test_jobs_are_recovered_after_a_restart(settings, tmp_path):
    repo = JobRepository(settings.jobs_db_absolute_path)
    store = Store(settings=settings, repository=repo)
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)
    settings.mock_job_duration_seconds = 1000
    job = store.start_ring_patch_job(tid, "key-1")
    repo.close()

    fresh_repo = JobRepository(settings.jobs_db_absolute_path)
    recovered = fresh_repo.get_job(job.id, with_events=True)
    assert recovered is not None and recovered.active
    assert recovered.provider_reference == job.provider_reference
    fresh_repo.close()


def test_cancel_marks_the_job_cancelled(store):
    tid = deployment_task(store)
    preapprove_next_ring(store, tid)
    job = store.start_ring_patch_job(tid, "key-1")

    cancelled = store.cancel_job(job.id)

    assert cancelled.state is JobState.CANCELLED
    assert store.repo.active_job_for_target(job.targets[0].logical_target_id) is None
