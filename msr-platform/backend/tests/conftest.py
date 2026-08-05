"""Fixtures comunes: settings aisladas, repositorio en memoria y store con mocks."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings  # noqa: E402
from app.repository import JobRepository  # noqa: E402
from app.runbooks import (  # noqa: E402
    DEFAULT_PATCH_RUNBOOK,
    DEFAULT_RESET_RUNBOOK,
    DEFAULT_ROLLBACK_RUNBOOK,
)
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
    """Runbooks propios de tipo Automation: nunca documentos de tipo Command."""
    return Settings(
        _env_file=None,
        patch_provider="aws-automation",
        restore_provider="aws-automation",
        dry_run=True,
        jobs_db_path=str(tmp_path / "jobs-aws.db"),
        aws_region="eu-west-1",
        patch_runbook_name=DEFAULT_PATCH_RUNBOOK,
        rollback_runbook_name=DEFAULT_ROLLBACK_RUNBOOK,
        reset_runbook_name=DEFAULT_RESET_RUNBOOK,
        allowed_runbooks=[DEFAULT_PATCH_RUNBOOK, DEFAULT_ROLLBACK_RUNBOOK,
                          DEFAULT_RESET_RUNBOOK],
        automation_assume_role_arn="arn:aws:iam::123456789012:role/MSR-AutomationRole",
    )


@pytest.fixture
def aws_real_settings(aws_settings) -> Settings:
    """Configuración completa exigida por la política fail-closed (MSR_DRY_RUN=false).

    Sigue sin tocar AWS: los tests inyectan clientes con `botocore.stub.Stubber`.
    """
    aws_settings.dry_run = False
    aws_settings.allowed_account_ids = ["123456789012"]
    aws_settings.allowed_regions = ["eu-west-1"]
    aws_settings.allowed_environments = ["development"]
    aws_settings.sandbox_instance_id = "i-0123456789abcdef0"
    return aws_settings


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
