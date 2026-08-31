"""Máquina de estados de los jobs: transiciones válidas e inválidas."""
from __future__ import annotations

import pytest

from app.jobs import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    InvalidTransition,
    JobState,
    JobType,
    PatchJob,
    can_transition,
    state_for_execution,
)
from app.providers.base import ExecutionStatus


def _job(**kwargs) -> PatchJob:
    base = dict(id="job-1", job_type=JobType.PATCH, task_id="RTASK1", ring_number=1,
                provider="mock")
    base.update(kwargs)
    return PatchJob(**base)


def test_terminal_and_active_states_are_disjoint():
    assert not TERMINAL_STATES & ACTIVE_STATES
    assert TERMINAL_STATES | ACTIVE_STATES == set(JobState)


def test_happy_path_transitions():
    job = _job()
    job.transition_to(JobState.VALIDATING)
    job.transition_to(JobState.RUNNING)
    assert job.started_at is not None
    job.transition_to(JobState.SUCCEEDED)
    assert job.terminal and job.completed_at is not None


def test_invalid_transition_is_rejected():
    job = _job()
    with pytest.raises(InvalidTransition):
        job.transition_to(JobState.SUCCEEDED)


def test_terminal_states_have_no_outgoing_transitions():
    for state in TERMINAL_STATES:
        job = _job(state=state)
        assert job.terminal
        for target in JobState:
            assert not can_transition(state, target)


def test_dry_run_is_terminal_and_never_becomes_succeeded():
    job = _job(state=JobState.VALIDATING)
    job.transition_to(JobState.DRY_RUN)
    assert job.terminal
    with pytest.raises(InvalidTransition):
        job.transition_to(JobState.SUCCEEDED)


@pytest.mark.parametrize("status,expected_patch,expected_restore", [
    (ExecutionStatus.PENDING, JobState.RUNNING, JobState.RESTORING),
    (ExecutionStatus.RUNNING, JobState.RUNNING, JobState.RESTORING),
    (ExecutionStatus.SUCCEEDED, JobState.SUCCEEDED, JobState.RESTORED),
    (ExecutionStatus.FAILED, JobState.FAILED, JobState.RESTORE_FAILED),
    (ExecutionStatus.CANCELLED, JobState.CANCELLED, JobState.CANCELLED),
    (ExecutionStatus.TIMED_OUT, JobState.TIMED_OUT, JobState.TIMED_OUT),
    (ExecutionStatus.DRY_RUN, JobState.DRY_RUN, JobState.DRY_RUN),
])
def test_state_for_execution_mapping(status, expected_patch, expected_restore):
    assert state_for_execution(status, JobType.PATCH) is expected_patch
    assert state_for_execution(status, JobType.ROLLBACK) is expected_restore


def test_error_message_is_truncated():
    job = _job(state=JobState.VALIDATING)
    job.transition_to(JobState.FAILED, error_code="X", error_message="a" * 5000)
    assert len(job.error_message) == 2000
