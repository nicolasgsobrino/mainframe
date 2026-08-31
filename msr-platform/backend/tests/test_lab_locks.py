"""Fase 2.8: lock distribuido de operación del laboratorio.

Ninguna prueba llama a AWS: DynamoDB se sustituye por `FakeDynamoDb`, que evalúa
las mismas condiciones que la API real (ítem inexistente, caducado o del mismo
dueño para tomarlo; dueño coincidente para liberarlo) y que a propósito **no**
simula el borrado asíncrono del TTL, para demostrar que la adquisición no
depende de él.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from lab_fakes import ASG_NAME, FakeDynamoDb, FakeLabAwsProvider, FakeLabWorld

from app.config import ConfigurationError
from app.errors import ConflictError, DomainError
from app.lab_lifecycle import ERROR_LOCKED
from app.lab_locks import (
    BACKEND_DYNAMODB,
    BACKEND_SQLITE,
    ERROR_LAB_BUSY,
    OPERATION_PATCH,
    OPERATION_RECONCILE,
    OPERATION_RESET,
    DynamoDbLabLockBackend,
    LabLockedError,
    LabLockError,
    LabLockManager,
    SqliteLabLockBackend,
    get_lab_lock_backend,
)
from app.repository import JobRepository
from app.store import Store

LAB_ID = "linux-patching-01"
TABLE = "msr-poc-lab-locks"


class Clock:
    """Reloj de pared inyectado: el test decide cuándo caduca un lock."""

    def __init__(self, start: datetime | None = None):
        self.value = start or datetime(2026, 8, 5, 6, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def table() -> FakeDynamoDb:
    return FakeDynamoDb()


@pytest.fixture
def clock() -> Clock:
    return Clock()


def manager(settings, table: FakeDynamoDb, clock: Clock, holder: str) -> LabLockManager:
    """Manager con backend DynamoDB, como en `aws-real`."""
    backend = DynamoDbLabLockBackend(TABLE, lambda: table, now_fn=clock)
    return LabLockManager(settings, backend, holder)


# --- adquisición y exclusión ----------------------------------------------
def test_the_first_process_acquires_the_lock(aws_real_settings, table, clock):
    first = manager(aws_real_settings, table, clock, "task-a:1")

    assert first.acquire(LAB_ID, "corr-a", OPERATION_RESET) is True

    held = first.state(LAB_ID)
    assert held["owner"] == "corr-a"
    assert held["holder"] == "task-a:1"
    assert held["operation"] == OPERATION_RESET
    assert table.tables == [TABLE]


def test_a_second_process_cannot_acquire_an_active_lock(aws_real_settings, table, clock):
    first = manager(aws_real_settings, table, clock, "task-a:1")
    second = manager(aws_real_settings, table, clock, "task-b:1")
    assert first.acquire(LAB_ID, "corr-a", OPERATION_RESET)

    assert second.acquire(LAB_ID, "corr-b", OPERATION_PATCH) is False
    assert first.state(LAB_ID)["owner"] == "corr-a"


def test_an_expired_lock_is_reclaimed_without_waiting_for_the_ttl_deletion(
        aws_real_settings, table, clock):
    first = manager(aws_real_settings, table, clock, "task-a:1")
    second = manager(aws_real_settings, table, clock, "task-b:1")
    assert first.acquire(LAB_ID, "corr-a", OPERATION_RESET,
                         ttl_seconds=aws_real_settings.lab_lock_ttl_seconds)

    clock.advance(aws_real_settings.lab_lock_ttl_seconds + 1)

    # El ítem caducado sigue en la tabla: DynamoDB borra por TTL de forma
    # asíncrona y el lock no puede depender de ese borrado.
    assert LAB_ID in table.items
    assert second.acquire(LAB_ID, "corr-b", OPERATION_PATCH) is True
    assert second.state(LAB_ID)["owner"] == "corr-b"


def test_only_the_owner_releases_the_lock(aws_real_settings, table, clock):
    first = manager(aws_real_settings, table, clock, "task-a:1")
    second = manager(aws_real_settings, table, clock, "task-b:1")
    assert first.acquire(LAB_ID, "corr-a", OPERATION_RESET)

    assert second.release(LAB_ID, "corr-b") is False
    assert first.state(LAB_ID)["owner"] == "corr-a"

    assert first.release(LAB_ID, "corr-a") is True
    assert first.state(LAB_ID) is None


def test_the_same_owner_reenters_its_own_lock(aws_real_settings, table, clock):
    """La reconciliación propaga su correlation ID al reset que lanza."""
    reconcile = manager(aws_real_settings, table, clock, "task-a:1")
    assert reconcile.acquire(LAB_ID, "corr-a", OPERATION_RECONCILE)

    assert reconcile.acquire(LAB_ID, "corr-a", OPERATION_RESET) is True
    assert reconcile.state(LAB_ID)["operation"] == OPERATION_RESET


def test_a_conflict_names_the_operation_and_the_owner_that_hold_the_lock(
        aws_real_settings, table, clock):
    first = manager(aws_real_settings, table, clock, "task-a:1")
    second = manager(aws_real_settings, table, clock, "task-b:1")
    first.acquire(LAB_ID, "corr-a", OPERATION_RESET)

    with pytest.raises(LabLockedError) as raised:
        second.acquire_or_conflict(LAB_ID, "corr-b", OPERATION_PATCH)

    assert raised.value.code == ERROR_LAB_BUSY
    assert raised.value.http_status == 409
    assert OPERATION_RESET in str(raised.value)
    assert "corr-a" in str(raised.value)
    assert isinstance(raised.value, ConflictError)


def test_an_unexpected_dynamodb_error_never_looks_like_a_free_lock(
        aws_real_settings, table, clock):
    table.failure = RuntimeError("AccessDeniedException: not authorized")
    lock = manager(aws_real_settings, table, clock, "task-a:1")

    with pytest.raises(LabLockError) as raised:
        lock.acquire(LAB_ID, "corr-a", OPERATION_RESET)

    assert raised.value.code == "PERMISSION_DENIED"


# --- selección de backend -------------------------------------------------
def test_dry_run_and_mock_do_not_require_dynamodb(settings, aws_settings, tmp_path):
    repo = JobRepository(str(tmp_path / "backend.db"))
    try:
        def missing_client():
            raise AssertionError("no debe construirse ningún cliente AWS")

        assert get_lab_lock_backend(settings, repo, missing_client).name == BACKEND_SQLITE
        assert get_lab_lock_backend(aws_settings, repo, missing_client).name == BACKEND_SQLITE
    finally:
        repo.close()


def test_real_aws_execution_uses_the_dynamodb_table(aws_real_settings, table, tmp_path):
    repo = JobRepository(str(tmp_path / "backend-real.db"))
    try:
        backend = get_lab_lock_backend(aws_real_settings, repo, lambda: table)
        assert backend.name == BACKEND_DYNAMODB

        backend.acquire(LAB_ID, "corr-a", "task-a:1", OPERATION_RESET, 60)
        assert table.tables == [aws_real_settings.lab_lock_table_name]
    finally:
        repo.close()


def test_the_table_name_is_mandatory_for_a_real_execution(aws_real_settings):
    aws_real_settings.lab_lock_table_name = ""

    with pytest.raises(ConfigurationError) as raised:
        aws_real_settings.validate_real_execution()

    assert "MSR_LAB_LOCK_TABLE_NAME" in str(raised.value)


# --- contención entre operaciones reales ----------------------------------
@pytest.fixture
def lab_settings(aws_settings):
    aws_settings.lab_logical_id = LAB_ID
    aws_settings.lab_environment = "development"
    aws_settings.lab_autoscaling_group_name = ASG_NAME
    aws_settings.allowed_account_ids = ["123456789012"]
    aws_settings.allowed_regions = ["eu-west-1"]
    aws_settings.allowed_environments = ["development"]
    return aws_settings


def build_store(lab_settings, world: FakeLabWorld) -> Store:
    repo = JobRepository(lab_settings.jobs_db_absolute_path)
    provider = FakeLabAwsProvider(world)
    return Store(settings=lab_settings, repository=repo,
                 patch_provider=provider, restore_provider=provider)


@pytest.fixture
def world() -> FakeLabWorld:
    return FakeLabWorld(LAB_ID)


def prepare_patch(store: Store, tid: str) -> None:
    """Deja la tarea del laboratorio lista para desplegar su primer anillo."""
    from app import engine

    pipeline = store.pipelines[tid]
    pipeline["phase_index"] = engine.PHASE_IDS.index("deployment")
    ring_no = engine.RING_DEFS[pipeline["rings_done"]][0]
    store.preapprove_ring(tid, ring_no, approver="tester", note="test")


def test_a_patch_cannot_start_while_a_reset_owns_the_lock(lab_settings, world):
    store = build_store(lab_settings, world)
    tid = store._lab_task_id(LAB_ID)
    prepare_patch(store, tid)
    store.lab_locks.with_holder("hook:1").acquire(LAB_ID, "corr-reset", OPERATION_RESET)

    with pytest.raises(LabLockedError):
        store.start_ring_patch_job(tid)


def test_a_reset_cannot_start_while_a_patch_owns_the_lock(lab_settings, world):
    store = build_store(lab_settings, world)
    store.lab_locks.with_holder("task-b:1").acquire(LAB_ID, "corr-patch", OPERATION_PATCH)

    with pytest.raises(LabLockedError):
        store.start_lab_reset_job(LAB_ID)


def test_a_release_hook_reconciliation_cannot_reset_while_the_ui_operates(lab_settings, world):
    """El hook de release y la task del servicio son procesos distintos."""
    world.instances[0].patch()
    store = build_store(lab_settings, world)
    store.lab_locks.with_holder("task-servicio:1").acquire(LAB_ID, "corr-ui", OPERATION_PATCH)

    result = store.ensure_lab_ready(LAB_ID, confirmed=True)

    assert result["error_code"] == ERROR_LOCKED
    assert result["ready"] is False
    assert store.lab_locks.state(LAB_ID)["owner"] == "corr-ui"


def test_a_real_reset_takes_the_lock_and_releases_it_after_success(lab_settings, world):
    lab_settings.dry_run = False
    world.instances[0].patch()
    store = build_store(lab_settings, world)
    assert store.lab_locks.backend_name == BACKEND_DYNAMODB

    job = store.start_lab_reset_job(LAB_ID)

    lock = job.request_payload["lab_lock"]
    assert lock["lab_id"] == LAB_ID
    assert lock["owner"] == job.correlation_id
    assert lock["operation"] == OPERATION_RESET
    # El lock se libera con el estado terminal del job, no antes.
    assert job.terminal
    assert lock["released"] is True
    assert store.lab_locks.state(LAB_ID) is None


def test_the_lock_is_released_when_the_operation_fails(lab_settings, world):
    """Un objetivo rechazado por política libera el laboratorio."""
    store = build_store(lab_settings, world)
    world.instances[0].tags.pop("msr-resettable", None)
    world.instances[0].tags["msr-poc"] = "false"

    with pytest.raises(DomainError):
        store.start_lab_reset_job(LAB_ID)

    assert store.lab_locks.state(LAB_ID) is None


def test_an_abandoned_sqlite_lock_becomes_reclaimable(settings, tmp_path):
    """El backend local respeta las mismas reglas de caducidad y propiedad."""
    repo = JobRepository(str(tmp_path / "abandoned.db"))
    try:
        settings.lab_lock_ttl_seconds = 1
        backend = SqliteLabLockBackend(repo)
        lock = LabLockManager(settings, backend, "task-caida:1")
        assert lock.acquire(LAB_ID, "corr-abandonada", OPERATION_RESET, ttl_seconds=1)

        # El proceso muere sin liberar: nadie más puede tomarlo hasta que caduca.
        other = lock.with_holder("task-nueva:1")
        assert other.acquire(LAB_ID, "corr-nueva", OPERATION_RESET) is False

        # El lock caduca sin que su proceso vuelva: pasa a ser reclamable.
        with repo.transaction() as conn:
            conn.execute("UPDATE lab_locks SET expires_at = ?",
                         ("2020-01-01T00:00:00+00:00",))
        assert other.acquire(LAB_ID, "corr-nueva", OPERATION_RESET) is True
        assert other.state(LAB_ID)["owner"] == "corr-nueva"
    finally:
        repo.close()
