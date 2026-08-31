"""Concurrencia de SQLite: una conexión por operación, WAL y locks intactos.

Ninguna prueba comparte una conexión entre threads: el repositorio abre la suya
en cada operación, de modo que requests, polling del frontend y reconciliador
pueden coexistir sin `ProgrammingError` ni transacciones anidadas.
"""
from __future__ import annotations

import sqlite3
import threading

import pytest
from test_repository import make_job

from app.jobs import JobState
from app.repository import JobRepository, TargetBusyError

THREADS = 8
ITERATIONS = 25


def run_concurrently(fn, count: int) -> tuple[list, list[BaseException]]:
    """Ejecuta `fn(i)` en `count` threads y recoge resultados y excepciones."""
    results: list = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(count)
    guard = threading.Lock()

    def worker(index: int) -> None:
        barrier.wait()
        try:
            value = fn(index)
        except BaseException as exc:  # se clasifica en cada test
            with guard:
                errors.append(exc)
            return
        with guard:
            results.append(value)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not any(t.is_alive() for t in threads), "un thread se quedó bloqueado"
    return results, errors


@pytest.fixture
def file_repo(tmp_path) -> JobRepository:
    repository = JobRepository(str(tmp_path / "concurrency.db"))
    yield repository
    repository.close()


def test_file_repository_uses_wal_and_busy_timeout(file_repo):
    with file_repo.connection() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_parallel_reads_do_not_corrupt_state(file_repo):
    job, _ = file_repo.create_job(make_job(key="read"))
    file_repo.append_event(job.id, JobState.QUEUED, "creado")

    def read(_index: int) -> tuple[str, int]:
        for _ in range(ITERATIONS):
            recovered = file_repo.get_job(job.id, with_events=True)
            assert recovered is not None
            assert len(file_repo.list_active_jobs()) == 1
        return recovered.state.value, len(recovered.events)

    results, errors = run_concurrently(read, THREADS)
    assert errors == []
    assert set(results) == {("queued", 1)}


def test_two_threads_racing_for_the_same_target_leave_one_winner(file_repo):
    def create(index: int):
        return file_repo.create_job(make_job(target_id="SRV-RACE", key=f"race-{index}"))

    results, errors = run_concurrently(create, THREADS)
    assert len(results) == 1, "sólo un job puede tomar el lock del objetivo"
    assert all(isinstance(e, TargetBusyError) for e in errors)
    assert len(errors) == THREADS - 1
    assert file_repo.active_job_for_target("SRV-RACE").id == results[0][0].id


def test_different_targets_are_not_blocked_by_each_other(file_repo):
    def create(index: int):
        job, created = file_repo.create_job(
            make_job(target_id=f"SRV-{index}", key=f"target-{index}"))
        return created

    results, errors = run_concurrently(create, THREADS)
    assert errors == []
    assert results == [True] * THREADS
    assert len(file_repo.list_active_jobs()) == THREADS


def test_idempotency_holds_under_concurrency(file_repo):
    def create(_index: int):
        job, created = file_repo.create_job(make_job(target_id="SRV-IDEM", key="shared-key"))
        return job.id, created

    results, errors = run_concurrently(create, THREADS)
    assert errors == []
    assert len({job_id for job_id, _ in results}) == 1, "todos deben ver el mismo job"
    assert [created for _, created in results].count(True) == 1


def test_reconciler_and_api_can_read_and_update_concurrently(file_repo):
    jobs = [file_repo.create_job(make_job(target_id=f"SRV-C{i}", key=f"c{i}"))[0]
            for i in range(THREADS)]

    def churn(index: int) -> int:
        job = jobs[index]
        for _ in range(ITERATIONS):
            # "API": actualiza el job y añade eventos.
            current = file_repo.get_job(job.id)
            assert current is not None
            file_repo.save_job(current)
            file_repo.append_event(job.id, current.state, f"tick-{index}")
            # "Reconciliador": relee los jobs activos persistidos.
            assert len(file_repo.list_active_jobs()) == THREADS
        return index

    results, errors = run_concurrently(churn, THREADS)
    assert errors == []
    assert sorted(results) == list(range(THREADS))
    # Los locks siguen ocupados tras las actualizaciones concurrentes.
    for i in range(THREADS):
        assert file_repo.active_job_for_target(f"SRV-C{i}") is not None
        with pytest.raises(TargetBusyError):
            file_repo.create_job(make_job(target_id=f"SRV-C{i}", key=f"after-{i}"))


def test_concurrent_transactions_do_not_raise_sqlite_misuse(file_repo):
    """Regresión: nada de 'transaction within a transaction' ni uso entre threads."""
    def mixed(index: int) -> None:
        for i in range(ITERATIONS):
            key = f"mixed-{index}-{i}"
            try:
                file_repo.create_job(make_job(target_id=f"SRV-M{index}", key=key))
            except TargetBusyError:
                pass
            job = file_repo.active_job_for_target(f"SRV-M{index}")
            if job is not None:
                file_repo.append_event(job.id, job.state, key)

    _, errors = run_concurrently(mixed, THREADS)
    assert not [e for e in errors if isinstance(e, sqlite3.Error)], errors
    assert errors == []


def test_memory_repository_shares_one_guarded_connection():
    """`:memory:` no puede abrir conexiones nuevas: sería otra base de datos."""
    repo = JobRepository(":memory:")
    job, created = repo.create_job(make_job(key="mem"))
    assert created

    def read(_index: int) -> str:
        for _ in range(ITERATIONS):
            recovered = repo.get_job(job.id, with_events=True)
            assert recovered is not None
        return recovered.id

    results, errors = run_concurrently(read, THREADS)
    assert errors == []
    assert set(results) == {job.id}
    repo.close()
    with pytest.raises(RuntimeError):
        repo.get_job(job.id)


def test_file_repository_keeps_working_after_close(tmp_path):
    """Cerrar el repositorio no invalida las operaciones con conexión propia."""
    path = str(tmp_path / "after-close.db")
    repo = JobRepository(path)
    job, _ = repo.create_job(make_job(key="after-close"))
    repo.close()
    assert repo.get_job(job.id) is not None
