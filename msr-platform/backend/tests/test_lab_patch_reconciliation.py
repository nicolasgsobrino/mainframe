"""Anillos de despliegue sobre una instancia real que ya está parcheada.

La promoción por anillos y su aprobación Human-Driven se mantienen intactas: lo
que cambia es la ejecución. Todos los anillos resuelven la misma EC2 y, una vez
que la Automation confirma el parcheo, los anillos siguientes se cierran con esa
evidencia en lugar de relanzar el runbook (que abortaría con
`KERNEL_ALREADY_FIXED`).
"""
from __future__ import annotations

import pytest
from lab_fakes import ASG_NAME, FIXED_KERNEL, FakeLabWorld
from test_lab_lifecycle import LAB_ID, build

from app import engine
from app.jobs import JobState, JobType, PatchJob
from app.providers.base import ExecutionStatus, utcnow

FIXED = f"{FIXED_KERNEL[0]}-{FIXED_KERNEL[1]}.x86_64"


@pytest.fixture
def lab_settings(aws_settings):
    aws_settings.lab_logical_id = LAB_ID
    aws_settings.lab_environment = "development"
    aws_settings.lab_autoscaling_group_name = ASG_NAME
    aws_settings.allowed_account_ids = ["123456789012"]
    aws_settings.allowed_regions = ["eu-west-1"]
    aws_settings.allowed_environments = ["development"]
    return aws_settings


@pytest.fixture
def world() -> FakeLabWorld:
    return FakeLabWorld(LAB_ID)


def _approve_next_ring(store, tid, key: str) -> PatchJob:
    ring_no = engine.RING_DEFS[store.pipelines[tid]["rings_done"]][0]
    store.preapprove_ring(tid, ring_no)
    return store.start_ring_patch_job(tid, key)


def patched_lab_store(lab_settings, world: FakeLabWorld):
    """Store AWS con el parcheo del laboratorio ya ejecutado y confirmado."""
    store, provider, _clock = build(lab_settings, world,
                                    poll_status=ExecutionStatus.SUCCEEDED)
    store.ensure_lab_ready(LAB_ID)
    tid = store._lab_task_id(LAB_ID)
    store.tasks[tid]["track"] = "A"
    job = _approve_next_ring(store, tid, "key-patch")
    world.instances[0].patched = True
    world.instances[0].kernel_version, world.instances[0].kernel_release = FIXED_KERNEL
    job = store.reconcile_job(job)
    assert job.state is JobState.SUCCEEDED
    return store, provider, tid, job


def test_the_ring_plan_keeps_its_five_environments(lab_settings, world):
    """La promoción por anillos y sus puertas de aprobación no cambian."""
    store, _provider, tid, _job = patched_lab_store(lab_settings, world)

    deploy = store.pipelines[tid]["artifacts"]["deployment"]

    assert [r["ring"] for r in deploy["rings"]] == [rn for rn, _ in engine.RING_DEFS]
    assert store.task_detail(tid)["journey"]["resources"]["rings_total"] == 5


def test_a_confirmed_patch_exposes_its_evidence(lab_settings, world):
    store, _provider, tid, _job = patched_lab_store(lab_settings, world)

    detail = store.task_detail(tid)

    assert detail["lab_patch"]["kernel"] == FIXED
    assert detail["lab_patch"]["execution_id"]
    assert detail["lab_patch"]["instance_id"] == world.instances[0].instance_id


def test_the_next_ring_closes_without_calling_aws_again(lab_settings, world):
    """El objetivo ya está en la versión corregida: no se relanza la Automation."""
    store, provider, tid, first = patched_lab_store(lab_settings, world)
    starts = provider.starts
    rings_done = store.pipelines[tid]["rings_done"]

    job = _approve_next_ring(store, tid, "key-next-ring")

    assert provider.starts == starts
    assert job.state is JobState.SUCCEEDED
    assert job.result_payload["already_compliant"]["execution_id"] == first.provider_reference
    assert store.pipelines[tid]["rings_done"] == rings_done + 1


def test_the_last_ring_closes_the_deployment(lab_settings, world):
    store, _provider, tid, _job = patched_lab_store(lab_settings, world)

    while store.pipelines[tid]["rings_done"] < len(engine.RING_DEFS):
        _approve_next_ring(store, tid, f"key-ring-{store.pipelines[tid]['rings_done']}")

    detail = store.task_detail(tid)
    assert detail["task"]["status"] == "remediated"
    assert detail["phases"][-1]["status"] == "approved"
    assert detail["journey"]["resources"]["failed"] == 0
    assert detail["journey"]["blockers"] == []


def test_a_later_failed_attempt_does_not_reopen_the_deployment(lab_settings, world):
    """`KERNEL_ALREADY_FIXED` queda como historial, no como recurso fallido."""
    store, _provider, tid, job = patched_lab_store(lab_settings, world)
    failed = PatchJob(
        id="job-already-fixed", job_type=JobType.PATCH, task_id=tid,
        ring_number=job.ring_number,
        provider=store.patch_provider.name, state=JobState.FAILED, dry_run=False,
        provider_reference="exec-already-fixed", completed_at=utcnow(),
        error_code="AUTOMATION_FAILED", error_message=f"KERNEL_ALREADY_FIXED:{FIXED}")
    store.repo.create_job(failed, scope="approve")

    detail = store.task_detail(tid)

    assert detail["journey"]["resources"]["failed"] == 0
    assert "job_failed" not in detail["journey"]["blockers"]
    # El intento sigue siendo auditable.
    assert "job-already-fixed" in [j["id"] for j in detail["jobs"]]


def test_a_vulnerable_lab_still_offers_the_patch(lab_settings, world):
    """Sin evidencia de parcheo el despliegue sigue abierto (fail-closed)."""
    store, _provider, _clock = build(lab_settings, world)
    store.ensure_lab_ready(LAB_ID)
    tid = store._lab_task_id(LAB_ID)

    assert store._lab_patch_evidence(tid) is None
    detail = store.task_detail(tid)
    assert detail["lab_patch"] is None
    assert detail["journey"]["resources"]["rings_total"] == 5
