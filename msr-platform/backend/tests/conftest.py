"""Fixtures comunes: settings aisladas, repositorio en memoria y store con mocks."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings  # noqa: E402
from app.repository import JobRepository  # noqa: E402
from app.store import Store  # noqa: E402


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Configuración por defecto (provider mock) sin leer el .env del proyecto."""
    return Settings(
        _env_file=None,
        patch_provider="mock",
        restore_provider="mock",
        dry_run=True,
        jobs_db_path=str(tmp_path / "jobs.db"),
        mock_job_duration_seconds=1,
        mock_restore_duration_seconds=0,
    )


@pytest.fixture
def aws_settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        patch_provider="aws-automation",
        restore_provider="aws-automation",
        dry_run=True,
        jobs_db_path=str(tmp_path / "jobs-aws.db"),
        aws_region="eu-west-1",
        patch_runbook_name="AWS-RunPatchBaseline",
        reset_runbook_name="AWS-PatchInstanceWithRollback",
        allowed_runbooks=["AWS-RunPatchBaseline", "AWS-PatchInstanceWithRollback"],
    )


@pytest.fixture
def repo(settings) -> JobRepository:
    repository = JobRepository(settings.jobs_db_absolute_path)
    yield repository
    repository.close()


@pytest.fixture
def store(settings, repo) -> Store:
    return Store(settings=settings, repository=repo)


def deployment_task(store: Store) -> str:
    """Primera tarea que ya se encuentra en la fase de despliegue."""
    for tid, pipeline in store.pipelines.items():
        if pipeline["phase_index"] == 5 and pipeline["rings_done"] < 5:
            return tid
    raise AssertionError("el seed no contiene ninguna tarea en despliegue")
