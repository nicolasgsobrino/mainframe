"""Factoría de providers: único punto donde se decide quién ejecuta.

Ni `store.py` ni `main.py` ni `engine.py` deben seleccionar provider.
"""
from __future__ import annotations

from ..config import (
    ALLOWED_PROVIDERS,
    PROVIDER_AWS_AUTOMATION,
    PROVIDER_MOCK,
    ConfigurationError,
    Settings,
)
from .base import PatchProvider, RestoreProvider
from .mock_patch import MockPatchProvider
from .mock_restore import MockRestoreProvider

__all__ = [
    "PROVIDER_MOCK",
    "PROVIDER_AWS_AUTOMATION",
    "get_patch_provider",
    "get_restore_provider",
]


def _reject(kind: str, value: str) -> None:
    raise ConfigurationError(
        f"Provider de {kind} desconocido: '{value}'. Valores permitidos: "
        f"{', '.join(ALLOWED_PROVIDERS)}.")


def get_patch_provider(settings: Settings) -> PatchProvider:
    if settings.patch_provider == PROVIDER_MOCK:
        return MockPatchProvider(settings)
    if settings.patch_provider == PROVIDER_AWS_AUTOMATION:
        settings.validate_for_providers()
        from .aws_ssm_automation import AwsSsmAutomationPatchProvider
        return AwsSsmAutomationPatchProvider(settings)
    _reject("parcheo", settings.patch_provider)
    raise AssertionError("unreachable")


def get_restore_provider(settings: Settings) -> RestoreProvider:
    if settings.restore_provider == PROVIDER_MOCK:
        return MockRestoreProvider(settings)
    if settings.restore_provider == PROVIDER_AWS_AUTOMATION:
        settings.validate_for_providers()
        from .aws_ssm_automation import AwsSsmAutomationRestoreProvider
        return AwsSsmAutomationRestoreProvider(settings)
    _reject("restauración", settings.restore_provider)
    raise AssertionError("unreachable")
