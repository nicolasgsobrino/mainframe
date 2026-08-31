"""Persistencia SQLite: durabilidad, idempotencia y lock por objetivo."""
from __future__ import annotations

import pytest

from app.jobs import JobState, JobType, PatchJob, new_job_id
from app.providers.base import Target
from app.repository import JobRepository, TargetBusyError


def make_job(target_id: str = "SRV-1001", key: str | None = None, **kwargs) -> PatchJob:
    job_id = kwargs.pop("id", new_job_id())
    return PatchJob(
        id=job_id, job_type=kwargs.pop("job_type", JobType.PATCH), task_id="RTASK1",
        ring_number=kwargs.pop("ring_number", 1), provider="mock",
        idempotency_key=key or f"key-{job_id}",
        targets=(Target(logical_target_id=target_id, instance_id=kwargs.pop("instance_id", None)),),
        request_payload={"job_id": job_id}, **kwargs)


def test_job_survives_a_backend_restart(tmp_path):
    path = str(tmp_path / "jobs.db")
    repo = JobRepository(path)
    job, created = repo.create_job(make_job(key="k1"))
    assert created
    repo.close()

    reopened = JobRepository(path)
    recovered = reopened.get_job(job.id, with_events=True)
    assert recovered is not None
    assert recovered.state is JobState.QUEUED
    assert recovered.targets[0].logical_target_id == "SRV-1001"
    assert reopened.active_job_for_task("RTASK1").id == job.id
    reopened.close()


def test_same_idempotency_key_returns_the_original_job(repo):
    first, created_first = repo.create_job(make_job(key="same"))
    second, created_second = repo.create_job(make_job(key="same"))
    assert created_first is True
    assert created_second is False
    assert second.id == first.id


def test_lock_prevents_two_active_jobs_on_the_same_target(repo):
    repo.create_job(make_job(key="k1"))
    with pytest.raises(TargetBusyError):
        repo.create_job(make_job(key="k2"))


def test_lock_is_released_only_on_terminal_state(repo):
    job, _ = repo.create_job(make_job(key="k1"))
    job.transition_to(JobState.VALIDATING)
    repo.save_job(job)
    with pytest.raises(TargetBusyError):
        repo.create_job(make_job(key="k2"))

    job.transition_to(JobState.FAILED, error_code="X", error_message="boom")
    repo.save_job(job)
    other, created = repo.create_job(make_job(key="k3"))
    assert created and other.active


def test_different_targets_can_run_in_parallel(repo):
    repo.create_job(make_job(target_id="SRV-1001", key="k1"))
    _, created = repo.create_job(make_job(target_id="SRV-1002", key="k2"))
    assert created


def test_events_are_persisted_and_deduplicated(repo):
    job, _ = repo.create_job(make_job(key="k1"))
    repo.append_event(job.id, JobState.QUEUED, "creado")
    assert repo.has_event(job.id, "creado")
    assert not repo.has_event(job.id, "otro")
    assert [e.message for e in repo.list_events(job.id)] == ["creado"]


def test_clear_removes_history(repo):
    job, _ = repo.create_job(make_job(key="k1"))
    repo.clear()
    assert repo.get_job(job.id) is None
    assert repo.active_job_for_target("SRV-1001") is None
