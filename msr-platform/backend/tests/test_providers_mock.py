"""Contrato del provider mock: determinista, no bloqueante y con estado intermedio."""
from __future__ import annotations

from datetime import timedelta

from app.providers.base import ExecutionStatus, PatchRequest, PatchSpec, RestoreRequest, Target, utcnow
from app.providers.mock_patch import MockPatchProvider
from app.providers.mock_restore import MockRestoreProvider

TARGET = Target(logical_target_id="SRV-1001", environment="production", name="srv-payments-01")


def patch_request(dry_run: bool = False, job_id: str = "job-1") -> PatchRequest:
    return PatchRequest(
        job_id=job_id, task_id="RTASK1", ring_number=2, targets=(TARGET,),
        spec=PatchSpec(component="log4j-core", from_version="2.14.1", to_version="2.14.2",
                       cve="CVE-2021-44228", track="B"),
        dry_run=dry_run, ring_label="Anillo 2 · Canary", executor="GitHub Actions",
        assets_count=3, task_snapshot={"id": "RTASK1", "cve": "CVE-2021-44228",
                                       "ci_name": "payments-api", "track": "B",
                                       "vulnerable_version": "2.14.1"})


def restore_request(dry_run: bool = False) -> RestoreRequest:
    return RestoreRequest(
        job_id="job-r1", task_id="RTASK1", ring_number=2, targets=(TARGET,),
        reason="post-check failed", target_version="2.14.1", dry_run=dry_run,
        task_snapshot={"id": "RTASK1", "ci_name": "payments-api", "track": "B",
                       "vulnerable_version": "2.14.1"})


def test_validate_target_allows_logical_targets(settings):
    provider = MockPatchProvider(settings)
    assert provider.validate_target(patch_request()).allowed is True


def test_start_is_not_blocking_and_reports_running(settings):
    provider = MockPatchProvider(settings)
    execution = provider.start(patch_request(), "key-1")
    assert execution.status is ExecutionStatus.RUNNING
    assert execution.steps == ()
    assert execution.dry_run is False


def test_poll_progresses_by_time_without_sleeping(settings):
    """Al menos un poll devuelve un estado NO terminal con pasos parciales."""
    settings.mock_job_duration_seconds = 10
    base = utcnow()
    provider = MockPatchProvider(settings, now_fn=lambda: base)
    execution = provider.start(patch_request(), "key-1")

    mid = MockPatchProvider(settings, now_fn=lambda: base + timedelta(seconds=5))
    partial = mid.poll(execution.provider_reference, patch_request())
    assert partial.status is ExecutionStatus.RUNNING
    assert 0 < len(partial.steps)

    end = MockPatchProvider(settings, now_fn=lambda: base + timedelta(seconds=11))
    final = end.poll(execution.provider_reference, patch_request())
    assert final.status is ExecutionStatus.SUCCEEDED
    assert len(final.steps) > len(partial.steps)
    assert final.to_version and final.from_version


def test_results_are_deterministic(settings):
    a = MockPatchProvider(settings).poll(
        MockPatchProvider(settings).start(patch_request(), "k").provider_reference, patch_request())
    b = MockPatchProvider(settings).poll(
        MockPatchProvider(settings).start(patch_request(), "k").provider_reference, patch_request())
    assert [s.command for s in a.steps] == [s.command for s in b.steps]


def test_dry_run_never_reports_success(settings):
    execution = MockPatchProvider(settings).start(patch_request(dry_run=True), "k")
    assert execution.status is ExecutionStatus.DRY_RUN
    assert execution.provider_reference.startswith("dryrun:")
    assert all(step.status == "planned" for step in execution.steps)


def test_restore_provider_completes_and_reports_version(settings):
    provider = MockRestoreProvider(settings)
    execution = provider.start(restore_request(), "k")
    polled = provider.poll(execution.provider_reference, restore_request())
    assert polled.status in (ExecutionStatus.RUNNING, ExecutionStatus.SUCCEEDED)
    assert polled.restored_version == "2.14.1"


def test_restore_dry_run_does_not_restore(settings):
    execution = MockRestoreProvider(settings).start(restore_request(dry_run=True), "k")
    assert execution.status is ExecutionStatus.DRY_RUN
