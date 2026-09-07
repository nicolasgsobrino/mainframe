"""Proyección de las 8 fases del Patching Journey sobre el pipeline de 6 fases."""
import copy

from conftest import deployment_task

from app import engine, journey


def _first(store):
    """Primera tarea y su pipeline."""
    task = next(iter(store.tasks.values()))
    return task, store.pipelines[task["id"]]


def test_catalog_matches_the_model():
    catalog = journey.phase_catalog()
    assert [p["id"] for p in catalog] == [
        "cyber_trigger", "asset_identification", "applicability_assessment",
        "blast_radius", "change_planning", "ring_execution", "gate_validation",
        "evidence_closure"]
    assert [p["band"] for p in catalog] == (
        ["demand_risk"] * 4 + ["change_planning"] + ["execution_closure"] * 3)


def test_pipeline_phases_project_onto_journey_phases(store):
    task, pipeline = _first(store)
    pipeline = copy.deepcopy(pipeline)

    expected = {
        "detection": "cyber_trigger",
        "prioritization": "applicability_assessment",
        "pre_implementation": "blast_radius",
        "lab_testing": "ring_execution",
        "prototype": "gate_validation",
    }
    for pipeline_phase, journey_phase in expected.items():
        pipeline["phase_index"] = engine.PHASE_IDS.index(pipeline_phase)
        assert journey.position(task, pipeline)["phase"] == journey_phase

    # El laboratorio es el anillo 1 en ambos casos.
    pipeline["phase_index"] = engine.PHASE_IDS.index("lab_testing")
    assert journey.position(task, pipeline)["ring"] == 1


def test_deployment_cycles_through_planning_execution_and_closure(store):
    task, pipeline = _first(store)
    pipeline = copy.deepcopy(pipeline)
    pipeline["phase_index"] = engine.PHASE_IDS.index("deployment")
    rings = pipeline["artifacts"]["deployment"]["rings"]
    active = next(r for r in rings if r["status"] == "in_progress")
    # Los anillos ya desplegados tienen su resultado aceptado: si no, el
    # recorrido se quedaría retenido en su validación humana.
    pipeline["hitl_verifications"] = {
        journey.verification_key("ring_result", r["ring"]): {"actor": "qa"}
        for r in rings
    }

    active["job"] = None
    active["plan"]["approval"]["preapproved"] = False
    pos = journey.position(task, pipeline)
    assert pos["phase"] == "change_planning"
    assert pos["blockers"] == ["awaiting_approval"]

    active["plan"]["approval"]["preapproved"] = True
    assert journey.position(task, pipeline)["phase"] == "ring_execution"

    active["job"] = {"state": "running", "terminal": False}
    assert journey.position(task, pipeline)["phase"] == "ring_execution"

    active["job"] = {"state": "failed", "terminal": True, "targets": ["i-1"]}
    pos = journey.position(task, pipeline)
    assert pos["phase"] == "gate_validation"
    assert pos["blockers"] == ["job_failed"]

    for ring in rings:
        ring["status"] = "completed"
    assert journey.position(task, pipeline)["phase"] == "evidence_closure"


def test_rollback_sends_the_ring_back_to_the_step_before_deployment(store):
    task, pipeline = _first(store)
    pipeline = copy.deepcopy(pipeline)
    pipeline["phase_index"] = engine.PHASE_IDS.index("deployment")
    pipeline["rollback"] = {"triggered": True, "status": "executed"}
    pipeline["artifacts"]["deployment"]["rings"][0]["status"] = "completed"
    pipeline["hitl_verifications"] = {
        journey.verification_key("ring_result", 1): {"actor": "qa"},
    }
    ring = pipeline["artifacts"]["deployment"]["rings"][1]
    ring["status"] = "rolled_back"
    ring["plan"]["approval"]["preapproved"] = False

    pos = journey.position(task, pipeline)
    assert pos["phase"] == "change_planning"
    assert pos["blockers"] == ["rollback", "awaiting_approval"]
    assert pos["ring"] == 2

    gates = journey.gate_states(task, pipeline)
    preapproval = next(g for g in gates
                       if g["id"] == "ring_preapproval" and g["ring"] == 2)
    result = next(g for g in gates
                  if g["id"] == "ring_result" and g["ring"] == 2)
    assert preapproval["status"] == journey.GATE_PENDING
    assert result["status"] == journey.GATE_UPCOMING


def test_a_remediated_task_is_closed_whatever_the_pipeline_says(store):
    original, pipeline = _first(store)
    task = dict(original, status="remediated")

    assert journey.position(task, pipeline)["phase"] == "evidence_closure"
    assert {p["status"] for p in journey.phase_states(task, pipeline)} == {"completed"}


def test_phase_states_split_completed_current_and_pending(store):
    task, pipeline = _first(store)
    states = journey.phase_states(task, pipeline)
    current = next(s for s in states if s["status"] == "current")

    assert [s["status"] for s in states[:current["index"]]] == ["completed"] * current["index"]
    assert all(s["status"] == "pending" for s in states[current["index"] + 1:])


def test_resource_rollup_only_counts_productive_rings(store):
    task, pipeline = _first(store)
    pipeline = copy.deepcopy(pipeline)
    for ring in pipeline["artifacts"]["deployment"]["rings"]:
        ring["status"] = "pending"
        ring["job"] = None

    rollup = journey.resource_rollup(pipeline)
    assert rollup["patched"] == 0
    assert rollup["pending"] + rollup["excluded"] == rollup["total"]

    # El anillo 1 es una réplica de laboratorio: no parchea activos reales.
    pipeline["artifacts"]["deployment"]["rings"][0]["status"] = "completed"
    assert journey.resource_rollup(pipeline)["patched"] == 0

    productive = next(r for r in pipeline["artifacts"]["deployment"]["rings"]
                      if engine.RING_STAGES[r["ring"]]["prod"])
    productive["status"] = "completed"
    rollup = journey.resource_rollup(pipeline)
    assert rollup["patched"] == productive["assets"]
    assert rollup["patched"] + rollup["pending"] + rollup["excluded"] == rollup["total"]


def test_overview_journey_counts_every_task_exactly_once(store):
    ov = store.overview()
    phases = ov["journey"]["phases"]

    assert len(phases) == 8
    assert sum(p["count"] for p in phases) == ov["journey"]["total"] == len(store.tasks)
    assert all(p["count"] >= 0 for p in phases)


def test_task_detail_exposes_the_journey_with_rings(store):
    detail = store.task_detail(next(iter(store.tasks)))
    journey_block = detail["journey"]

    assert len(journey_block["phases"]) == 8
    assert [r["ring"] for r in journey_block["rings"]] == [1, 2, 3, 4, 5]
    assert journey_block["resources"]["total"] >= 1


def test_gate_catalog_declares_how_each_gate_is_closed():
    catalog = journey.gate_catalog()
    assert [g["id"] for g in catalog] == [
        "scope_confirmation", "ai_proposal", "change_approval",
        "ring_preapproval", "ring_result", "closure"]
    # Todas bloquean; lo que cambia es con qué acción se cierran.
    assert all(g["enforced"] for g in catalog)
    assert {g["id"] for g in catalog if g["verifiable"]} == {
        "scope_confirmation", "ai_proposal", "ring_result", "closure"}
    assert all(g["phase"] in journey.PHASE_INDEX for g in catalog)


def test_gates_repeat_once_per_ring_and_follow_the_deployment(store):
    tid = deployment_task(store)
    task, pipeline = store.tasks[tid], store.pipelines[tid]
    gates = journey.gate_states(task, pipeline)

    per_ring = [g for g in gates if g["per_ring"]]
    assert len(per_ring) == 2 * len(engine.RING_DEFS)
    done = pipeline["rings_done"]
    preapprovals = [g for g in gates if g["id"] == "ring_preapproval"]
    assert [g["status"] for g in preapprovals[:done]] == [journey.GATE_DONE] * done
    assert preapprovals[done]["status"] == journey.GATE_PENDING
    assert [g["status"] for g in gates if g["id"] == "ring_result"][:done] == (
        [journey.GATE_DONE] * done)
    assert all(g["actor"] for g in preapprovals[:done])


def test_gates_do_not_wait_on_a_ring_before_the_deployment_phase(store):
    task, pipeline = _first(store)
    pipeline = copy.deepcopy(pipeline)
    pipeline["phase_index"] = engine.PHASE_IDS.index("detection")

    gates = journey.gate_states(task, pipeline)
    pending = [g for g in gates if g["status"] == journey.GATE_PENDING]
    assert [g["id"] for g in pending] == ["scope_confirmation"]
    assert journey.gate_rollup(gates)["pending_enforced"] == 1


def test_a_remediated_task_has_every_gate_behind_it(store):
    tid = next(t for t, task in store.tasks.items() if task.get("status") == "remediated")
    gates = journey.gate_states(store.tasks[tid], store.pipelines[tid])
    rollup = journey.gate_rollup(gates)

    assert rollup["done"] == rollup["total"] == len(gates)
    assert rollup["pending"] == 0 and rollup["next"] is None


def test_overview_aggregates_the_human_decisions(store):
    ov = store.overview()
    hitl = ov["journey"]["hitl"]

    assert hitl["pending"] >= hitl["pending_enforced"] >= 0
    assert hitl["done"] + hitl["pending"] <= hitl["total"]
    assert hitl["tasks_awaiting"] == sum(
        1 for t in store.tasks
        if journey.gate_rollup(journey.gate_states(
            store.tasks[t], store.pipelines[t]))["pending"])
    assert sum(p["gates_pending"] for p in ov["journey"]["phases"]) == hitl["tasks_awaiting"]


def test_the_scenario_starts_with_three_vulnerabilities_already_closed(store):
    remediated = [t for t in store.tasks.values() if t.get("status") == "remediated"]

    assert len(remediated) == 3
    for task in remediated:
        assert store.vulnerable_items[task["vulnerable_item_id"]]["status"] == "fixed"
        pipeline = store.pipelines[task["id"]]
        assert pipeline["rings_done"] == len(engine.RING_DEFS)
        assert pipeline["statuses"]["deployment"] == "approved"
        assert journey.position(task, pipeline)["phase"] == "evidence_closure"
    # Y con dos abiertas que recorren el flujo durante la demo, además del lab.
    open_tasks = [t for t in store.tasks.values() if t.get("status") != "remediated"]
    assert len(open_tasks) == 3
    assert any(t.get("lab_target") for t in open_tasks)


def test_blast_radius_does_not_propagate_without_downtime(store):
    for task in store.tasks.values():
        impact = store.pipelines[task["id"]]["artifacts"]["impact"]
        if task["track"] == "A":
            assert impact["downtime_required"] is True
            assert impact["blast_scope"] == "propagated"
            assert impact["impacted_count"] == impact["affected_count"]
        else:
            assert impact["downtime_required"] is False
            assert impact["blast_scope"] == "local"
            assert impact["impacted_count"] == 1
        assert impact["affected_count"] >= impact["impacted_count"]
