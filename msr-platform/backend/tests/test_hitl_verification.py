"""Verificaciones humanas de los puntos de control que el motor no bloquea."""
import pytest

from app import journey
from app.errors import ValidationError
from tests.conftest import deployment_task


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


def test_a_gate_that_blocks_execution_is_not_closed_as_a_mere_record(store):
    with pytest.raises(ValidationError):
        store.verify_gate("RTASK900001", "change_approval")


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


def test_per_ring_gates_are_verified_ring_by_ring(store):
    detail = store.verify_gate(deployment_task(store), "ring_result", ring=1)
    assert _gate(detail, "ring_result", ring=1)["verified"] is True
    assert _gate(detail, "ring_result", ring=5)["verified"] is False
