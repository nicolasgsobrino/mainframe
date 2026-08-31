"""Un laboratorio ya parcheado no vuelve a ofrecer el parcheo.

La demo tiene un único activo real: cuando la Automation confirma el parcheo, el
despliegue está completo y un intento posterior (que el runbook abortaría con
`KERNEL_ALREADY_FIXED`) se rechaza antes de tocar AWS, sin borrar el historial.
"""
from __future__ import annotations

import pytest
from lab_fakes import ASG_NAME, FIXED_KERNEL, FakeLabWorld
from test_lab_lifecycle import LAB_ID, build

from app import journey
from app.errors import ValidationError
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


def patched_lab_store(lab_settings, world: FakeLabWorld):
    """Store AWS con el parcheo del laboratorio ya ejecutado y confirmado."""
    store, provider, _clock = build(lab_settings, world,
                                    poll_status=ExecutionStatus.SUCCEEDED)
    store.ensure_lab_ready(LAB_ID)
    tid = store._lab_task_id(LAB_ID)
    store.tasks[tid]["track"] = "A"
    ring_no = store._ring_defs(tid)[store.pipelines[tid]["rings_done"]][0]
    store.preapprove_ring(tid, ring_no)
    job = store.start_ring_patch_job(tid, "key-patch")
    world.instances[0].patched = True
    world.instances[0].kernel_version, world.instances[0].kernel_release = FIXED_KERNEL
    job = store.reconcile_job(job)
    assert job.state is JobState.SUCCEEDED
    return store, provider, tid, job


def test_the_real_lab_deploys_in_a_single_ring(lab_settings, world):
    """Un único activo real no se promociona por cinco entornos simulados."""
    store, _provider, tid, _job = patched_lab_store(lab_settings, world)

    deploy = store.pipelines[tid]["artifacts"]["deployment"]

    assert [r["ring"] for r in deploy["rings"]] == [1]
    assert deploy["total_assets"] == 1
    assert deploy["rings"][0]["status"] == "completed"


def test_a_confirmed_patch_closes_the_deployment(lab_settings, world):
    store, _provider, tid, _job = patched_lab_store(lab_settings, world)

    detail = store.task_detail(tid)

    assert detail["rings_done"] == 1
    assert detail["task"]["status"] == "remediated"
    assert detail["journey"]["resources"]["patched"] == 1
    assert detail["journey"]["resources"]["failed"] == 0
    assert detail["journey"]["resources"]["pending"] == 0
    assert detail["journey"]["blockers"] == []
    assert {p["status"] for p in detail["journey"]["phases"]} == {"completed"}
    assert detail["phases"][-1]["status"] == "approved"
    assert detail["lab_patch"]["kernel"] == FIXED
    assert detail["lab_patch"]["execution_id"]


def test_patching_again_is_refused_without_calling_aws(lab_settings, world):
    store, provider, tid, _job = patched_lab_store(lab_settings, world)
    starts = provider.starts

    with pytest.raises(ValidationError) as excinfo:
        store.start_ring_patch_job(tid, "key-again")

    assert excinfo.value.code == "LAB_ALREADY_PATCHED"
    assert provider.starts == starts


def test_a_later_failed_attempt_does_not_reopen_the_deployment(lab_settings, world):
    """`KERNEL_ALREADY_FIXED` queda como historial, no como recurso fallido."""
    store, _provider, tid, _job = patched_lab_store(lab_settings, world)
    failed = PatchJob(
        id="job-already-fixed", job_type=JobType.PATCH, task_id=tid, ring_number=1,
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
    assert detail["journey"]["resources"]["patched"] == 0
    assert journey.resource_rollup(store.pipelines[tid])["rings_total"] == 1
