"""Verificaciones humanas: cada puerta detiene el recorrido hasta el visto bueno."""
import pytest

from app import engine, journey
from app.errors import ValidationError
from app.providers.mock_patch import MockPatchProvider
from app.repository import JobRepository
from app.store import Store
from tests.conftest import clear_human_gates, deployment_task
from tests.test_store_deployment import FrozenClock


def _gate(detail, gate_id, ring=None):
    return next(g for g in detail["journey"]["gates"]
                if g["id"] == gate_id and g["ring"] == ring)


def test_a_registered_gate_is_closed_by_an_explicit_human_verification(store):
    tid = "RTASK900001"
    assert _gate(store.task_detail(tid), "scope_confirmation")["status"] == journey.GATE_PENDING

    detail = store.verify_gate(tid, "scope_confirmation", actor="ana.ruiz",
                               role="service_manager")
    gate = _gate(detail, "scope_confirmation")
    assert gate["status"] == journey.GATE_DONE
    assert gate["verified"] is True
    assert gate["actor"] == "ana.ruiz"
    assert gate["role"] == "service_manager"
    assert "activos afectados confirmados" in gate["output"]


def test_confirming_the_scope_moves_the_journey_to_the_asset_phase(store):
    tid = "RTASK900001"
    assert store.task_detail(tid)["journey"]["phase"] == "cyber_trigger"
    detail = store.verify_gate(tid, "scope_confirmation")
    assert detail["journey"]["phase"] == "asset_identification"


def test_the_verification_leaves_an_audit_line(store):
    detail = store.verify_gate("RTASK900001", "scope_confirmation", actor="ana.ruiz")
    assert any("Verificación humana de 'Confirmación de alcance'" in log["msg"]
               for log in detail["logs"])


def test_a_gate_with_its_own_approval_is_not_closed_as_a_mere_record(store):
    with pytest.raises(ValidationError):
        store.verify_gate("RTASK900001", "change_approval")


def test_the_phase_does_not_advance_while_its_gate_is_pending(store):
    tid = "RTASK900001"
    before = store.pipelines[tid]["phase_index"]

    with pytest.raises(ValidationError) as excinfo:
        store.approve_phase(tid)

    assert excinfo.value.code == "HITL_VERIFICATION_REQUIRED"
    assert store.pipelines[tid]["phase_index"] == before

    store.verify_gate(tid, "scope_confirmation")
    assert store.approve_phase(tid)["phase_index"] == before + 1


def test_the_ai_proposal_gate_stops_the_run_before_the_lab(store):
    tid = "RTASK900001"
    while store.pipelines[tid]["phase_index"] < engine.PHASE_IDS.index("pre_implementation"):
        clear_human_gates(store, tid)
        store.approve_phase(tid)

    assert store.pending_verification(tid)["id"] == "ai_proposal"
    with pytest.raises(ValidationError):
        store.approve_phase(tid)


def test_the_next_ring_waits_for_the_previous_result_to_be_validated(settings, repo):
    clock = FrozenClock()
    settings.mock_job_duration_seconds = 10
    store = Store(settings=settings, repository=repo,
                  patch_provider=MockPatchProvider(settings, now_fn=clock))
    tid = deployment_task(store)
    clear_human_gates(store, tid)
    done = store.pipelines[tid]["rings_done"]
    store.preapprove_ring(tid, done + 1)
    store.start_ring_patch_job(tid, "key-ring")
    clock.advance(11)
    store.task_detail(tid)  # reconcilia el job y cierra el anillo
    assert store.pipelines[tid]["rings_done"] == done + 1

    gate = store.pending_verification(tid)
    assert (gate["id"], gate["ring"]) == ("ring_result", done + 1)
    with pytest.raises(ValidationError):
        store.preapprove_ring(tid, done + 2)

    store.verify_gate(tid, "ring_result", ring=gate["ring"])
    assert store.preapprove_ring(tid, done + 2) is not None


def test_verifications_survive_a_restart(settings, tmp_path):
    settings.jobs_db_path = str(tmp_path / "gates.db")
    repo = JobRepository(settings.jobs_db_absolute_path)
    store = Store(settings=settings, repository=repo)
    store.verify_gate("RTASK900001", "scope_confirmation", actor="ana.ruiz")
    repo.close()

    repo_2 = JobRepository(settings.jobs_db_absolute_path)
    store_2 = Store(settings=settings, repository=repo_2)
    try:
        gate = _gate(store_2.task_detail("RTASK900001"), "scope_confirmation")
        assert gate["status"] == journey.GATE_DONE
        assert gate["actor"] == "ana.ruiz"
    finally:
        repo_2.close()


def test_an_unknown_gate_is_rejected(store):
    assert store.verify_gate("RTASK900001", "not_a_gate") is None


def test_every_registered_gate_produces_a_readable_output(store):
    """Cada puerta registrable deja un resultado con datos reales del pipeline."""
    for tid in store.tasks:
        for gate_id in ("scope_confirmation", "ai_proposal", "closure"):
            detail = store.verify_gate(tid, gate_id)
            assert _gate(detail, gate_id)["output"]
        detail = store.verify_gate(tid, "ring_result", ring=1)
        assert _gate(detail, "ring_result", ring=1)["output"]


def test_the_reset_reopens_the_deployment_verifications(store):
    tid = deployment_task(store)
    store.verify_gate(tid, "ring_result", ring=1)
    assert _gate(store.task_detail(tid), "ring_result", 1)["verified"] is True

    store._reopen_pipeline(tid)

    assert _gate(store.task_detail(tid), "ring_result", 1)["verified"] is False
    assert store.repo.verifications_for_task(tid) == {}


def test_per_ring_gates_are_verified_ring_by_ring(store):
    detail = store.verify_gate(deployment_task(store), "ring_result", ring=1)
    assert _gate(detail, "ring_result", ring=1)["verified"] is True
    assert _gate(detail, "ring_result", ring=5)["verified"] is False
