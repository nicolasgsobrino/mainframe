"""Reinicio completo del backend contra el mismo fichero SQLite.

Simula el proceso real: se crea y completa un job con el provider mock, se cierran
Store y Repository, y un proceso nuevo rehidrata el pipeline desde el mismo
fichero. No interviene AWS en ningún momento.
"""
from __future__ import annotations

from conftest import deployment_task
from test_rehydration import FrozenClock, complete_ring, mock_store

from app import engine
from app.jobs import JobState
from app.repository import JobRepository
from app.store import Store


def test_full_restart_rebuilds_state_and_allows_the_next_ring(settings, tmp_path):
    settings.jobs_db_path = str(tmp_path / "restart.db")
    repo = JobRepository(settings.jobs_db_absolute_path)
    store, clock = mock_store(settings, repo)
    tid = deployment_task(store)
    job, ring_no = complete_ring(store, clock, tid, "key-restart")

    assert job.state is JobState.SUCCEEDED
    rings_done = store.pipelines[tid]["rings_done"]
    task_status = store.tasks[tid].get("status")
    vi_id = store.tasks[tid]["vulnerable_item_id"]
    vi_status = store.vulnerable_items[vi_id]["status"]
    events = [e.message for e in repo.list_events(job.id)]
    assert events

    # Apagado completo del "proceso": no queda ningún objeto en memoria.
    repo.close()
    del store

    repo_2 = JobRepository(settings.jobs_db_absolute_path)
    store_2, clock_2 = mock_store(settings, repo_2)
    try:
        replayed = store_2.rehydrate_pipeline_state()
        assert replayed >= 1

        recovered = repo_2.get_job(job.id, with_events=True)
        assert recovered is not None
        assert recovered.state is JobState.SUCCEEDED
        assert [e.message for e in recovered.events] == events
        assert store_2.pipelines[tid]["rings_done"] == rings_done
        assert store_2.pipelines[tid]["ring_evidence"][ring_no]["job_id"] == job.id
        assert store_2.tasks[tid].get("status") == task_status
        assert store_2.vulnerable_items[vi_id]["status"] == vi_status

        # Sin locks huérfanos: el job terminal liberó su objetivo.
        assert repo_2.list_active_jobs() == []
        for target in recovered.targets:
            assert repo_2.active_job_for_target(target.logical_target_id) is None

        # Y el anillo siguiente puede arrancar en el proceso nuevo.
        next_job, next_ring = complete_ring(store_2, clock_2, tid, "key-restart-2")
        assert next_ring == engine.RING_DEFS[rings_done][0]
        assert next_job.state is JobState.SUCCEEDED
        assert store_2.pipelines[tid]["rings_done"] == next_ring
    finally:
        repo_2.close()


def test_restart_does_not_depend_on_the_random_baseline(settings, tmp_path):
    """`rings_done` inicial aleatorio no puede sobrescribir el histórico persistido."""
    settings.jobs_db_path = str(tmp_path / "baseline.db")
    repo = JobRepository(settings.jobs_db_absolute_path)
    store, clock = mock_store(settings, repo)
    tid = deployment_task(store)
    _job, ring_no = complete_ring(store, clock, tid, "key-baseline")
    repo.close()

    repo_2 = JobRepository(settings.jobs_db_absolute_path)
    store_2 = Store(settings=settings, repository=repo_2)
    try:
        assert store_2.pipelines[tid]["baseline"]["rings_done"] < ring_no
        assert store_2.pipelines[tid]["rings_done"] == ring_no
    finally:
        repo_2.close()


def test_active_job_survives_and_is_reconciled_after_restart(settings, tmp_path):
    """Un job aún en curso conserva su lock al reiniciar y avanza al reconciliar."""
    settings.jobs_db_path = str(tmp_path / "active.db")
    repo = JobRepository(settings.jobs_db_absolute_path)
    store, _clock = mock_store(settings, repo)
    tid = deployment_task(store)
    ring_no = engine.RING_DEFS[store.pipelines[tid]["rings_done"]][0]
    store.preapprove_ring(tid, ring_no)
    job = store.start_ring_patch_job(tid, "key-active")
    assert not job.terminal
    repo.close()

    repo_2 = JobRepository(settings.jobs_db_absolute_path)
    clock_2 = FrozenClock()
    clock_2.advance(11)
    store_2 = Store(settings=settings, repository=repo_2,
                    patch_provider=mock_store(settings, repo_2)[0].patch_provider)
    try:
        active = repo_2.list_active_jobs()
        assert [j.id for j in active] == [job.id]
        for target in active[0].targets:
            assert repo_2.active_job_for_target(target.logical_target_id).id == job.id

        # El reconciliador (o cualquier proceso nuevo) puede cerrarlo.
        store_2.reconcile_active_jobs()
        assert repo_2.get_job(job.id).state in {JobState.RUNNING, JobState.SUCCEEDED}
    finally:
        repo_2.close()
