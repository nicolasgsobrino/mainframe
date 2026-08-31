"""Fase 2.6: `ensure_lab_ready` reconcilia el laboratorio o falla cerrado.

Ninguna prueba llama a AWS: EC2, Systems Manager y Auto Scaling se sustituyen por
los dobles de `lab_fakes`, y el reloj se inyecta para que las esperas sean
deterministas.
"""
from __future__ import annotations

import pytest
from lab_fakes import ASG_NAME, FakeLabAwsProvider, FakeLabWorld

from app.lab import (
    LAB_STATE_PATCHED,
    LAB_STATE_VULNERABLE,
    RECONCILE_FAILED,
    RECONCILE_READY,
    RECONCILE_SKIPPED,
)
from app.lab_lifecycle import (
    ACTION_NONE,
    ACTION_RESET,
    ERROR_CONFIRMATION,
    ERROR_LOCKED,
    ERROR_NOT_VULNERABLE,
    ERROR_REPLACEMENT,
    ERROR_RESET_FAILED,
    ERROR_UNCHANGED,
    LabLifecycleManager,
)
from app.providers.base import ExecutionStatus
from app.repository import JobRepository
from app.store import Store

LAB_ID = "linux-patching-01"


class Clock:
    """Reloj monótono que sólo avanza cuando el reconciliador duerme."""

    def __init__(self):
        self.value = 0.0
        self.sleeps = 0

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        self.value += seconds

    def monotonic(self) -> float:
        return self.value


@pytest.fixture
def lab_settings(aws_settings):
    aws_settings.lab_logical_id = LAB_ID
    aws_settings.lab_environment = "development"
    aws_settings.lab_autoscaling_group_name = ASG_NAME
    aws_settings.allowed_account_ids = ["123456789012"]
    aws_settings.allowed_regions = ["eu-west-1"]
    aws_settings.allowed_environments = ["development"]
    aws_settings.lab_reconcile_timeout_seconds = 120
    aws_settings.lab_replacement_timeout_seconds = 60
    aws_settings.lab_reconcile_poll_interval_seconds = 5
    return aws_settings


def build(lab_settings, world: FakeLabWorld, **provider_kwargs):
    """Store con el provider AWS falso y un reconciliador con reloj inyectado."""
    repo = JobRepository(lab_settings.jobs_db_absolute_path)
    provider = FakeLabAwsProvider(world, **provider_kwargs)
    store = Store(settings=lab_settings, repository=repo,
                  patch_provider=provider, restore_provider=provider)
    clock = Clock()
    store.lab_lifecycle = LabLifecycleManager(store, sleep_fn=clock.sleep,
                                              monotonic_fn=clock.monotonic)
    return store, provider, clock


@pytest.fixture
def world() -> FakeLabWorld:
    return FakeLabWorld(LAB_ID)


# --- instancia ya lista ---------------------------------------------------
def test_a_vulnerable_and_healthy_instance_is_never_recreated(lab_settings, world):
    store, provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is True
    assert result["state"] == RECONCILE_READY
    assert result["action"] == ACTION_NONE
    assert result["instance_id"] == world.instances[0].instance_id
    assert provider.reset_requests == []
    lab = store.repo.get_lab_target(LAB_ID)
    assert lab.lab_state == LAB_STATE_VULNERABLE
    assert lab.current_instance_id == world.instances[0].instance_id
    assert lab.reconciliation_state == RECONCILE_READY
    assert lab.advisory_applicable is True
    assert lab.health_state == "healthy"
    assert lab.ssm_state == "Online"
    assert lab.last_correlation_id == result["correlation_id"]


# --- reset de una instancia ya parcheada ---------------------------------
def test_a_patched_instance_is_reset_and_replaced_by_a_different_one(lab_settings, world):
    world.instances[0].patch()
    previous = world.instances[0].instance_id
    lab_settings.dry_run = False
    store, provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["ready"] is True
    assert result["action"] == ACTION_RESET
    assert result["previous_instance_id"] == previous
    assert result["instance_id"] != previous
    assert len(provider.reset_requests) == 1
    # El reset recibe el Instance ID resuelto dinámicamente y el ASG de la IaC.
    request = provider.reset_requests[0]
    assert request.primary_target().instance_id == previous
    lab = store.repo.get_lab_target(LAB_ID)
    assert lab.previous_instance_id == previous
    assert lab.current_instance_id == result["instance_id"]
    assert lab.lab_state == LAB_STATE_VULNERABLE
    assert lab.autoscaling_group_name == ASG_NAME


def test_the_reset_shares_the_reconciliation_trace_and_only_the_allowlisted_runbook(
        lab_settings, world):
    """Una sola traza: el correlation ID de la reconciliación viaja al job y al runbook."""
    world.instances[0].patch()
    lab_settings.dry_run = False
    store, provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["ready"] is True
    job = store.get_job(store.repo.get_lab_target(LAB_ID).last_reset_job_id)
    assert job.correlation_id == result["correlation_id"]
    assert job.request_payload["trigger"] == "lab_reconcile:api"
    assert store.repo.get_lab_target(LAB_ID).last_correlation_id == result["correlation_id"]
    # Sólo se invoca el runbook de reset permitido: nunca un documento libre.
    assert provider.started_runbooks == ["reset_lab"]


def test_a_reset_that_returns_the_same_instance_fails_closed(lab_settings, world):
    world.instances[0].patch()
    lab_settings.dry_run = False
    store, _provider, _clock = build(lab_settings, world, replaces=False)

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["ready"] is False
    assert result["error_code"] == ERROR_UNCHANGED
    assert store.repo.get_lab_target(LAB_ID).reconciliation_state == RECONCILE_FAILED


def test_a_failed_reset_automation_fails_closed(lab_settings, world):
    world.instances[0].patch()
    lab_settings.dry_run = False
    store, _provider, _clock = build(lab_settings, world,
                                     reset_status=ExecutionStatus.FAILED, replaces=False)

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["ready"] is False
    assert result["error_code"] == ERROR_RESET_FAILED


def test_a_replacement_that_never_becomes_ready_fails_closed(lab_settings, world):
    world.instances[0].patch()
    lab_settings.dry_run = False
    store, _provider, clock = build(lab_settings, world, replacement_ping="ConnectionLost")

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["ready"] is False
    assert result["error_code"] == ERROR_REPLACEMENT
    # Se ha esperado hasta agotar el plazo, sin quedarse colgado.
    assert clock.sleeps >= 1


def test_a_replacement_that_is_not_vulnerable_fails_closed(lab_settings, world):
    world.instances[0].patch()
    lab_settings.dry_run = False
    store, _provider, _clock = build(lab_settings, world, replacement_patched=True)

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["ready"] is False
    assert result["error_code"] == ERROR_NOT_VULNERABLE
    assert result["evidence"]["vulnerable_state"] == LAB_STATE_PATCHED


# --- descubrimiento fail-closed ------------------------------------------
def test_zero_instances_fail_closed_without_creating_anything(lab_settings, world):
    world.instances = []
    store, provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is False
    assert result["error_code"] == "LAB_TARGET_NOT_FOUND"
    assert provider.reset_requests == []
    assert provider.starts == 0


def test_several_running_instances_fail_closed(lab_settings, world):
    world.add()
    store, provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is False
    assert result["error_code"] == "LAB_TARGET_AMBIGUOUS"
    assert provider.reset_requests == []


def test_a_missing_required_tag_fails_closed(lab_settings, world):
    world.instances[0].tags.pop("msr-lab-id")
    store, _provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is False
    # Sin el tag obligatorio la instancia ni siquiera se descubre.
    assert result["error_code"] == "LAB_TARGET_NOT_FOUND"


def test_an_instance_outside_the_expected_asg_fails_closed(lab_settings, world):
    world.instances[0].asg_name = "otro-asg"
    store, _provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is False
    assert result["error_code"] == "LAB_TARGET_NOT_IN_AUTOSCALING_GROUP"


def test_a_wrong_account_fails_closed(lab_settings, world):
    lab_settings.allowed_account_ids = ["999999999999"]
    store, _provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is False
    assert result["error_code"] == "LAB_TARGET_ACCOUNT_MISMATCH"


def test_a_wrong_region_fails_closed(lab_settings, world):
    lab_settings.allowed_regions = ["eu-central-1"]
    store, _provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is False
    assert result["error_code"] == "LAB_TARGET_REGION_MISMATCH"


def test_an_offline_ssm_node_fails_closed(lab_settings, world):
    world.instances[0].ping = "ConnectionLost"
    store, _provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is False
    assert result["error_code"] == ERROR_REPLACEMENT


def test_missing_asg_health_evidence_is_not_treated_as_healthy(lab_settings, world):
    """El ASG es obligatorio: sin evidencia InService/Healthy no hay readiness."""
    world.instances[0].lifecycle = "Pending"
    store, provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["ready"] is False
    assert result["evidence"]["health_state"] == "unhealthy"
    assert provider.reset_requests == []


def test_asg_health_is_read_regardless_of_its_casing(lab_settings, world):
    """DescribeAutoScalingInstances devuelve «HEALTHY»; los grupos, «Healthy»."""
    for casing in ("HEALTHY", "Healthy", "healthy"):
        world.instances[0].asg_health = casing
        store, _provider, _clock = build(lab_settings, world)

        result = store.ensure_lab_ready(LAB_ID)

        assert result["evidence"]["health_state"] == "healthy", casing


def test_an_unhealthy_vulnerable_instance_is_not_recreated(lab_settings, world):
    world.instances[0].ec2_ok = False
    lab_settings.dry_run = False
    store, provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["ready"] is False
    assert provider.reset_requests == []
    assert result["evidence"]["health_state"] == "unhealthy"


# --- concurrencia ---------------------------------------------------------
def test_a_second_replica_skips_a_reconciliation_already_in_progress(lab_settings, world):
    store, _provider, _clock = build(lab_settings, world)
    other = store.lab_locks.with_holder("otra-replica:1")
    assert other.acquire(LAB_ID, "corr-otra", "reconcile",
                         ttl_seconds=lab_settings.lab_reconcile_lock_ttl_seconds)

    result = store.ensure_lab_ready(LAB_ID)

    assert result["state"] == RECONCILE_SKIPPED
    assert result["error_code"] == ERROR_LOCKED
    assert "otra-replica:1" in result["error"]


def test_the_lock_is_released_after_a_reconciliation(lab_settings, world):
    store, _provider, _clock = build(lab_settings, world)

    store.ensure_lab_ready(LAB_ID)

    assert store.lab_locks.state(LAB_ID) is None


# --- modos ---------------------------------------------------------------
def test_dry_run_never_starts_an_automation(lab_settings, world):
    world.instances[0].patch()
    store, provider, _clock = build(lab_settings, world)  # dry_run sigue en True

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert store.settings.execution_mode() == "aws-dry-run"
    assert result["state"] == RECONCILE_SKIPPED
    assert result["action"] == ACTION_RESET
    assert provider.starts == 0
    assert provider.reset_requests == []
    assert "MSR-ResetLabInstance" in result["detail"]


def test_real_mode_requires_explicit_human_confirmation(lab_settings, world):
    world.instances[0].patch()
    lab_settings.dry_run = False
    store, provider, _clock = build(lab_settings, world)

    result = store.ensure_lab_ready(LAB_ID)

    assert store.settings.execution_mode() == "aws-real"
    assert result["error_code"] == ERROR_CONFIRMATION
    assert provider.starts == 0


def test_mock_mode_never_touches_aws(store):
    """Con el provider mock el laboratorio se reconcilia sin clientes AWS."""
    result = store.ensure_lab_ready()

    assert result["execution_mode"] == "mock"
    assert result["ready"] is True
    assert result["evidence"]["source"] == "mock"


def test_the_provider_output_never_substitutes_the_aws_rediscovery(lab_settings, world):
    """El `NewInstanceId` del runbook no puede fijar por sí solo el estado local."""
    world.instances[0].patch()
    previous = world.instances[0].instance_id
    lab_settings.dry_run = False
    # El reset «tiene éxito» pero el ASG no sustituye la instancia: AWS sigue
    # devolviendo la anterior y el report miente con un ID nuevo.
    store, _provider, _clock = build(lab_settings, world, replaces=False)

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["ready"] is False
    assert store.repo.get_lab_target(LAB_ID).current_instance_id == previous


# --- credenciales --------------------------------------------------------
def test_deployed_backend_needs_no_aws_profile(lab_settings):
    """Sin `MSR_AWS_PROFILE` ni rol, boto3 usa la cadena estándar del entorno."""
    lab_settings.aws_profile = ""
    lab_settings.aws_role_arn = ""
    assert lab_settings.credentials_source() == "default-chain"


def test_local_development_still_supports_an_aws_profile(lab_settings):
    lab_settings.aws_profile = "msr-poc"
    lab_settings.aws_role_arn = ""
    assert lab_settings.credentials_source() == "profile"
