"""Invariantes temporales del seed: el SLA de la demo debe ser interpretable."""
from datetime import datetime

from app import seed
from app.store import sla_state


def _dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _tasks():
    return seed.build_all()["remediation_tasks"]


def test_a_task_is_never_created_after_its_own_deadline():
    for task in _tasks():
        assert _dt(task["created_at"]) <= _dt(task["sla_due"]), task["cve"]


def test_nothing_is_detected_in_the_future():
    for vitem in seed.build_all()["vulnerable_items"]:
        assert _dt(vitem["detected_at"]) <= seed.NOW, vitem["cve"]


def test_the_deadline_is_the_detection_plus_the_severity_window():
    for vitem in seed.build_all()["vulnerable_items"]:
        expected = _dt(vitem["detected_at"]).replace(microsecond=0)
        assert (_dt(vitem["sla_due"]) - expected).days == vitem["sla_days"], vitem["cve"]


def test_no_task_starts_the_demo_out_of_sla():
    """Un plazo vencido distrae de la narrativa: el escenario arranca en plazo."""
    overdue = [t["cve"] for t in _tasks() if sla_state(t["sla_due"])["overdue"]]
    assert overdue == []


def test_only_the_walkthrough_vulnerability_is_urgent():
    urgent = [t["cve"] for t in _tasks() if sla_state(t["sla_due"])["due_soon"]]
    assert urgent == ["CVE-2021-44228"]


def test_the_rest_keep_a_comfortable_margin():
    states = [sla_state(t["sla_due"]) for t in _tasks()]
    assert all(s["days_left"] >= 3 for s in states if not s["due_soon"])
