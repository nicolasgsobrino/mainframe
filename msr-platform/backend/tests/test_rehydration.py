"""Fase 1.1: el pipeline funcional se reconstruye desde SQLite tras reiniciar."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from conftest import clear_human_gates, deployment_task

from app import engine
from app.jobs import JobState
from app.providers.base import utcnow
from app.providers.mock_patch import MockPatchProvider
from app.reconciler import JobReconciler
from app.repository import JobRepository
from app.store import Store


class FrozenClock:
    def __init__(self):
        self.now = utcnow()

    def __call__(self):
        return self.now

    def advance(self, seconds: int):
        self.now += timedelta(seconds=seconds)


def mock_store(settings, repo) -> tuple[Store, FrozenClock]:
    clock = FrozenClock()
    settings.mock_job_duration_seconds = 10
    return Store(settings=settings, repository=repo,
                 patch_provider=MockPatchProvider(settings, now_fn=clock)), clock


def complete_ring(store: Store, clock: FrozenClock, tid: str, key: str):
    clear_human_gates(store, tid)
    ring_no = engine.RING_DEFS[store.pipelines[tid]["rings_done"]][0]
    store.preapprove_ring(tid, ring_no)
    job = store.start_ring_patch_job(tid, key)
    clock.advance(11)
    return store.reconcile_job(job), ring_no


def test_pipeline_state_survives_a_store_restart(settings, repo):
    store, clock = mock_store(settings, repo)
    tid = deployment_task(store)
    job, ring_no = complete_ring(store, clock, tid, "key-rehydrate")
    assert job.state is JobState.SUCCEEDED
    rings_done = store.pipelines[tid]["rings_done"]
    assert rings_done == ring_no

    # Nuevo proceso: Store y repositorio nuevos sobre la misma base SQLite.
    repo_2 = JobRepository(settings.jobs_db_absolute_path)
    store_2 = Store(settings=settings, repository=repo_2)
    try:
        assert store_2.pipelines[tid]["rings_done"] == rings_done
        evidence = store_2.pipelines[tid]["ring_evidence"][ring_no]
        assert evidence["job_id"] == job.id
        assert store_2.repo.get_job(job.id).state is JobState.SUCCEEDED
    finally:
        repo_2.close()


def test_rehydration_reopens_the_rollout_when_the_target_was_replaced(settings, repo):
    """Instancia sustituida: la evidencia describe una máquina que ya no existe."""
    settings.lab_logical_id = "linux-patching-01"
    store, clock = mock_store(settings, repo)
    tid = store._lab_task_id("linux-patching-01")
    job, ring_no = complete_ring(store, clock, tid, "key-replaced")
    assert store.pipelines[tid]["rings_done"] == ring_no
    lab = store.repo.get_lab_target("linux-patching-01")
    lab.previous_instance_id = next(t.instance_id for t in job.targets if t.instance_id)
    lab.current_instance_id = "i-0ffff11112222aaaa"
    store.repo.upsert_lab_target(lab)

    store.rehydrate_pipeline_state()

    assert store.pipelines[tid]["rings_done"] == 0
    assert store.pipelines[tid]["ring_evidence"] == {}


def test_rehydration_is_idempotent(settings, repo):
    store, clock = mock_store(settings, repo)
    tid = deployment_task(store)
    complete_ring(store, clock, tid, "key-idem")
    rings_done = store.pipelines[tid]["rings_done"]
    evidence = dict(store.pipelines[tid]["ring_evidence"])

    store.rehydrate_pipeline_state()
    store.rehydrate_pipeline_state()

    assert store.pipelines[tid]["rings_done"] == rings_done
    assert store.pipelines[tid]["ring_evidence"] == evidence


def test_rehydration_replays_jobs_marked_as_already_projected(settings, repo):
    """`outcome_applied` no puede impedir la reconstrucción tras un reinicio."""
    store, clock = mock_store(settings, repo)
    tid = deployment_task(store)
    job, ring_no = complete_ring(store, clock, tid, "key-applied")
    assert store.repo.get_job(job.id).result_payload["outcome_applied"] is True

    replayed = store.rehydrate_pipeline_state()

    assert replayed >= 1
    assert store.pipelines[tid]["rings_done"] == ring_no


def test_reconciler_updates_persisted_jobs_and_stops_cleanly(settings, repo):
    store, clock = mock_store(settings, repo)
    tid = deployment_task(store)
    ring_no = engine.RING_DEFS[store.pipelines[tid]["rings_done"]][0]
    store.preapprove_ring(tid, ring_no)
    job = store.start_ring_patch_job(tid, "key-reconciler")
    clock.advance(11)
    reconciler = JobReconciler(store, interval_seconds=1)

    async def run() -> int:
        reconciler.start()
        ticks = await reconciler.tick()
        await reconciler.stop()
        return ticks

    reconciled = asyncio.run(run())

    # El job avanza sin intervención del frontend, sólo desde SQLite.
    assert reconciled == 1
    assert reconciler.ticks == 1
    assert reconciler.last_error is None
    assert not reconciler.running
    assert store.repo.get_job(job.id).state is JobState.SUCCEEDED


def test_disabled_reconciler_does_not_run(settings, repo):
    store, _clock = mock_store(settings, repo)
    reconciler = JobReconciler(store, interval_seconds=1, enabled=False)

    async def run() -> None:
        reconciler.start()
        await reconciler.stop()

    asyncio.run(run())

    assert not reconciler.running
    assert reconciler.ticks == 0
