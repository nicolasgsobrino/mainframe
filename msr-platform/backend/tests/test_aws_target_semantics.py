"""Fase 1.1: un job AWS representa exactamente una instancia y sólo track A."""
from __future__ import annotations

import pytest
from conftest import deployment_task
from fakes import FakeAwsProvider

from app import engine
from app.errors import ValidationError
from app.labs import LabInstance
from app.repository import JobRepository
from app.store import Store

INSTANCE = "i-0123456789abcdef0"


class FakeLabResolver:
    """Resolutor de laboratorio que devuelve una instancia ya descubierta."""

    def __init__(self, instance: LabInstance):
        self._instance = instance

    def resolve(self, _logical_lab_id: str) -> LabInstance:
        return self._instance


@pytest.fixture
def aws_store(aws_settings) -> Store:
    """Store con el provider AWS falso: el plano de control se comporta como AWS."""
    repo = JobRepository(aws_settings.jobs_db_absolute_path)
    provider = FakeAwsProvider()
    store = Store(settings=aws_settings, repository=repo,
                  patch_provider=provider, restore_provider=provider)
    yield store
    repo.close()


def next_ring(store: Store, tid: str) -> int:
    return engine.RING_DEFS[store.pipelines[tid]["rings_done"]][0]


def use_track_a(store: Store, tid: str) -> None:
    """El seed reparte tracks A/B/C; AWS sólo admite infraestructura (A)."""
    store.tasks[tid]["track"] = "A"


def ring_logical_ids(store: Store, tid: str, ring_no: int) -> list[str]:
    return [a.get("logical_target_id") or a["id"]
            for a in store._ring_assets(tid, ring_no)]


def pin_instances(store: Store, tid: str, ring_no: int, count: int = 1) -> list[str]:
    """Asigna Instance IDs reales a los primeros activos del anillo.

    Los IDs viven en el activo, nunca en la configuración: no existe ninguna
    variable de entorno capaz de fijar la instancia de un objetivo.
    """
    assets = store._ring_assets(tid, ring_no)
    for index, asset in enumerate(assets[:count]):
        asset["instance_id"] = f"i-0123456789abcdef{index}"
    return [a.get("logical_target_id") or a["id"] for a in assets[:count]]


def test_ring_without_real_instances_is_rejected(aws_store):
    """La CMDB sintética no tiene Instance IDs: cero objetivos reales."""
    tid = deployment_task(aws_store)
    ring_no = next_ring(aws_store, tid)
    use_track_a(aws_store, tid)
    aws_store.preapprove_ring(tid, ring_no)

    with pytest.raises(ValidationError) as excinfo:
        aws_store.start_ring_patch_job(tid, "key-zero")

    assert excinfo.value.code == "RING_TARGET_COUNT_UNSUPPORTED"
    assert excinfo.value.http_status == 422


def test_ring_with_several_real_instances_is_rejected(aws_store):
    tid = deployment_task(aws_store)
    ring_no = next_ring(aws_store, tid)
    logical_ids = ring_logical_ids(aws_store, tid, ring_no)
    if len(logical_ids) < 2:
        pytest.skip("el anillo de esta tarea sólo contiene un activo")
    pin_instances(aws_store, tid, ring_no, count=2)

    with pytest.raises(ValidationError) as excinfo:
        aws_store._aws_single_target(tid, ring_no, "A")

    assert excinfo.value.code == "RING_TARGET_COUNT_UNSUPPORTED"


def test_exactly_one_real_instance_is_accepted(aws_store):
    tid = deployment_task(aws_store)
    ring_no = next_ring(aws_store, tid)
    logical_ids = pin_instances(aws_store, tid, ring_no)

    target = aws_store._aws_single_target(tid, ring_no, "A")

    assert target.instance_id == INSTANCE
    assert target.logical_target_id == logical_ids[0]


@pytest.mark.parametrize("track", ["B", "C", "", None])
def test_only_track_a_reaches_the_aws_provider(aws_store, track):
    tid = deployment_task(aws_store)
    ring_no = next_ring(aws_store, tid)
    aws_store.preapprove_ring(tid, ring_no)
    pin_instances(aws_store, tid, ring_no)
    aws_store.tasks[tid]["track"] = track

    with pytest.raises(ValidationError) as excinfo:
        aws_store.start_ring_patch_job(tid, f"key-{track}")

    assert excinfo.value.code == "UNSUPPORTED_REMEDIATION_TRACK"
    # El provider no ha sido invocado: ninguna ejecución iniciada.
    assert aws_store.patch_provider.starts == 0


def test_aws_job_reports_only_the_executed_instance(aws_store):
    tid = deployment_task(aws_store)
    ring_no = next_ring(aws_store, tid)
    aws_store.settings.dry_run = False
    use_track_a(aws_store, tid)
    aws_store.preapprove_ring(tid, ring_no)
    pin_instances(aws_store, tid, ring_no)

    job = aws_store.start_ring_patch_job(tid, "key-one")

    assert job.request_payload["assets_count"] == 1
    assert len(job.targets) == 1
    # La versión corregida la determina el runbook, no el store.
    assert job.request_payload["spec"]["to_version"] == ""


def test_lab_target_environment_comes_from_the_instance_tag(aws_store):
    """El anillo se llama «Laboratorio», pero el entorno lo fija msr-environment.

    La allowlist `MSR_ALLOWED_ENVIRONMENTS` se compara contra el entorno real del
    activo; usar la etiqueta de la etapa del anillo denegaba siempre el objetivo.
    """
    lab_id = aws_store.settings.lab_logical_id
    aws_store.lab_resolver = FakeLabResolver(LabInstance(
        instance_id=INSTANCE, state="running", logical_lab_id=lab_id,
        tags={"msr-poc": "true", "msr-lab-id": lab_id, "msr-environment": "sandbox"},
        ssm_managed=True))

    target = aws_store._asset_target(
        {"id": lab_id, "logical_target_id": lab_id, "environment": "Laboratorio"})

    assert target.environment == "sandbox"
