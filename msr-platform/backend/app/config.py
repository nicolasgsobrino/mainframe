"""Configuración de la plataforma (12-factor) con valores predeterminados seguros.

El provider por defecto es `mock` y `dry_run` está activado, de modo que la
aplicación arranca y funciona sin ninguna configuración de AWS.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROVIDER_MOCK = "mock"
PROVIDER_AWS_AUTOMATION = "aws-automation"
ALLOWED_PROVIDERS = (PROVIDER_MOCK, PROVIDER_AWS_AUTOMATION)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLATFORM_DIR = os.path.dirname(_BACKEND_DIR)


class ConfigurationError(RuntimeError):
    """Configuración incompleta o inválida para el provider seleccionado."""

    code = "PROVIDER_MISCONFIGURED"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MSR_", env_file=".env",
                                      env_file_encoding="utf-8", extra="ignore")

    # --- Selección de providers -------------------------------------------
    patch_provider: str = PROVIDER_MOCK
    restore_provider: str = PROVIDER_MOCK
    dry_run: bool = True

    # --- Persistencia de jobs ---------------------------------------------
    jobs_db_path: str = "./data/msr_jobs.db"

    # --- AWS ---------------------------------------------------------------
    aws_region: str = ""
    aws_role_arn: str = ""
    aws_profile: str = ""
    aws_endpoint_url: str = ""

    # --- Systems Manager Automation ---------------------------------------
    patch_runbook_name: str = ""
    reset_runbook_name: str = ""
    automation_assume_role_arn: str = ""

    # --- Objetivo de sandbox (primera integración: 1 EC2 Linux) -----------
    # Permite apuntar a la instancia real sin hardcodear IDs en la CMDB.
    sandbox_instance_id: str = ""
    sandbox_logical_target_id: str = ""

    # --- Política de objetivos --------------------------------------------
    allowed_account_ids: list[str] = Field(default_factory=list)
    allowed_regions: list[str] = Field(default_factory=list)
    allowed_environments: list[str] = Field(default_factory=list)
    allowed_runbooks: list[str] = Field(
        default_factory=lambda: ["AWS-RunPatchBaseline", "AWS-PatchInstanceWithRollback"])
    required_target_tag_key: str = "msr-poc"
    required_target_tag_value: str = "true"

    # --- Jobs --------------------------------------------------------------
    job_poll_interval_seconds: int = 2
    job_timeout_seconds: int = 1800
    mock_job_duration_seconds: int = 6
    mock_restore_duration_seconds: int = 0
    max_output_chars: int = 2000

    # --- API ---------------------------------------------------------------
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    @field_validator("allowed_account_ids", "allowed_regions", "allowed_environments",
                     "allowed_runbooks", "cors_allow_origins", mode="before")
    @classmethod
    def _split_csv(cls, value):
        """Permite listas en formato CSV (`a,b`) además de JSON."""
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                return value
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @field_validator("patch_provider", "restore_provider")
    @classmethod
    def _known_provider(cls, value: str) -> str:
        if value not in ALLOWED_PROVIDERS:
            raise ValueError(f"provider desconocido '{value}'; permitidos: {', '.join(ALLOWED_PROVIDERS)}")
        return value

    # ----------------------------------------------------------------------
    @property
    def jobs_db_absolute_path(self) -> str:
        if self.jobs_db_path == ":memory:" or os.path.isabs(self.jobs_db_path):
            return self.jobs_db_path
        return os.path.normpath(os.path.join(_PLATFORM_DIR, self.jobs_db_path))

    def effective_dry_run(self, provider_name: str) -> bool:
        """`dry_run` protege recursos reales: el provider mock nunca muta nada,
        por lo que la simulación se ejecuta completa aunque el flag esté activo."""
        return bool(self.dry_run) and provider_name != PROVIDER_MOCK

    def uses_aws(self) -> bool:
        return PROVIDER_AWS_AUTOMATION in (self.patch_provider, self.restore_provider)

    def validate_for_providers(self) -> None:
        """Falla con un mensaje claro si un provider AWS carece de configuración."""
        missing: list[str] = []
        if self.patch_provider == PROVIDER_AWS_AUTOMATION:
            if not self.aws_region:
                missing.append("MSR_AWS_REGION")
            if not self.patch_runbook_name:
                missing.append("MSR_PATCH_RUNBOOK_NAME")
        if self.restore_provider == PROVIDER_AWS_AUTOMATION:
            if not self.aws_region:
                missing.append("MSR_AWS_REGION")
            if not self.reset_runbook_name:
                missing.append("MSR_RESET_RUNBOOK_NAME")
        if not self.dry_run and self.uses_aws() and not self.required_target_tag_key:
            missing.append("MSR_REQUIRED_TARGET_TAG_KEY")
        if missing:
            raise ConfigurationError(
                "Configuración AWS incompleta para el provider seleccionado. "
                f"Variables obligatorias sin valor: {', '.join(sorted(set(missing)))}. "
                "Con MSR_PATCH_PROVIDER=mock la aplicación arranca sin configuración de AWS.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
