"""Arranque en la VM de una sesión de Devin: sin .env, sin perfil y sin claves.

Comprobaciones estáticas sobre `scripts/start_poc.sh` y el informe de la fase
2.11, más la verificación de identidad de `app.identity_check` con un STS falso.
Ningún test ejecuta el script, arranca uvicorn ni contacta con AWS.
"""
from __future__ import annotations

import pathlib
import re
from types import SimpleNamespace

import boto3
import pytest

from app.config import Settings
from app.identity_check import describe_identity

PLATFORM = pathlib.Path(__file__).resolve().parents[2]
START = PLATFORM / "scripts" / "start_poc.sh"
REPORT = PLATFORM / "ARCHITECTURE_REPORT_PHASE2_11.md"
BOOTSTRAP = PLATFORM / "AWS_BOOTSTRAP_REQUEST.md"

CREDENTIAL_MARKERS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                      "aws_access_key_id", "aws_secret_access_key", "aws configure",
                      "aws login", "aws sso login")


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def json_blocks(text: str) -> list[str]:
    """Bloques ```json de un documento: las políticas, sin la prosa que las explica."""
    return re.findall(r"```json\n(.*?)```", text, re.DOTALL)


def code(path: pathlib.Path) -> str:
    """Fichero sin comentarios: las aserciones miran el código, no la prosa."""
    return "\n".join(line for line in read(path).splitlines()
                     if not line.lstrip().startswith("#"))


# --- el script de arranque ---------------------------------------------------

def test_the_startup_script_is_executable():
    assert START.exists()
    assert START.stat().st_mode & 0o111, "scripts/start_poc.sh debe ser ejecutable"


def test_a_fresh_session_needs_no_env_file():
    """Nada de copiar, generar o leer un .env: la configuración se exporta."""
    script = code(START)

    for forbidden in ("cp .env", "cp ../.env", ".env.example", "source .env", "set -a"):
        assert forbidden not in script, forbidden


def test_the_startup_script_carries_no_static_credentials():
    script = read(START)

    for marker in CREDENTIAL_MARKERS:
        assert marker not in script, marker
    # La identidad la resuelve la cadena estándar del SDK: sin perfil ni assume-role.
    assert 'export MSR_AWS_PROFILE=""' in script
    assert 'export MSR_AWS_ROLE_ARN=""' in script


def test_the_startup_script_never_pins_an_instance_id():
    """El objetivo se resuelve por tags: cada reset cambia el Instance ID."""
    assert not re.search(r"\bi-[0-9a-f]{8,}", read(START))
    assert "MSR_SANDBOX_INSTANCE_ID" not in read(START)


def test_the_startup_script_keeps_the_safe_defaults():
    script = code(START)

    assert 'export MSR_DRY_RUN="${MSR_DRY_RUN:-true}"' in script
    assert "export MSR_LAB_RECONCILE_ON_STARTUP=false" in script


def test_the_startup_script_never_authorizes_a_destructive_reconciliation():
    """Comprobación no destructiva: `app.preflight` contra AWS, `app.lab_hook` en
    mock, y nunca `--confirm`."""
    # Sólo las líneas que ejecutan algo, no el mensaje final que documenta el reset.
    checks = [line for line in code(START).splitlines()
              if ("app.lab_hook" in line or "app.preflight" in line)
              and ("CHECK=" in line or "-m " in line)]

    assert [line for line in checks if "app.preflight" in line]
    assert [line for line in checks if "app.lab_hook" in line]
    for line in checks:
        assert "--confirm" not in line, line


def test_the_startup_script_verifies_the_aws_identity_before_using_aws():
    script = code(START)

    # Sólo sts:GetCallerIdentity (app.identity_check) y sólo entonces providers AWS.
    assert "app.identity_check" in script
    assert script.index("app.identity_check") < script.index("MSR_PATCH_PROVIDER=aws-automation")
    assert "MSR_POC_MODE=aws pero no hay identidad" in script


def test_the_startup_script_is_idempotent():
    """Repetible tras dormir la sesión: dependencias, build y proceso se reutilizan."""
    script = code(START)

    assert "[ -d \"$ROOT/backend/.venv\" ] || python3 -m venv" in script
    assert "[ -d \"$ROOT/frontend/node_modules\" ] || " in script
    assert "backend/static/index.html" in script          # no recompila si está al día
    assert "pkill -f \"uvicorn app.main:app" in script    # no deja dos backends en :8080


# --- verificación de identidad ----------------------------------------------

class _FakeSts:
    arn: str | None = None

    def __init__(self, account: str):
        self._account = account

    def get_caller_identity(self) -> dict:
        arn = self.arn or f"arn:aws:sts::{self._account}:assumed-role/MSRExternalBackendRole/msr"
        return {"Account": self._account, "Arn": arn}


class _FakeCredentials:
    """Credenciales resueltas por el SDK: `method` y presencia de session token."""

    def __init__(self, method: str, token: str | None):
        self.method = method
        self._token = token

    def get_frozen_credentials(self):
        return SimpleNamespace(access_key="AKIAFAKE", secret_key="fake", token=self._token)


class _FakeSession:
    def __init__(self, account: str | Exception, credentials: _FakeCredentials | None = None):
        self._account = account
        self._credentials = credentials or _FakeCredentials("custom-process", "fake-token")

    def __call__(self, **kwargs):
        return self

    def client(self, service: str):
        assert service == "sts"
        if isinstance(self._account, Exception):
            raise self._account
        return _FakeSts(self._account)

    def get_credentials(self):
        return self._credentials


@pytest.fixture
def identity_settings(monkeypatch):
    def _configure(account: str | Exception, allowed: list[str], *,
                   credentials: _FakeCredentials | None = None, arn: str | None = None):
        settings = Settings(_env_file=None, aws_region="eu-north-1",
                            patch_provider="aws-automation",
                            restore_provider="aws-automation",
                            allowed_account_ids=allowed)
        monkeypatch.setattr("app.identity_check.get_settings", lambda: settings)
        session = _FakeSession(account, credentials)
        if arn is not None:
            monkeypatch.setattr(_FakeSts, "arn", arn, raising=False)
        monkeypatch.setattr(boto3, "Session", session)
        return settings
    return _configure


def test_a_usable_identity_in_the_allowed_account_enables_aws(identity_settings):
    identity_settings("133789123239", ["133789123239"])

    result = describe_identity()

    assert result["usable"] is True
    assert result["account"] == "133789123239"
    assert result["credentials_source"] == "default-chain"
    # El rol federado del bootstrap, con credenciales temporales de STS.
    assert result["role"] == "MSRExternalBackendRole"
    assert result["temporary"] is True
    assert result["static_credentials_present"] is False
    # Nunca se publica una credencial, sólo su origen.
    for key in result:
        assert key not in ("access_key_id", "secret_access_key", "session_token")


def test_a_permanent_iam_key_is_rejected_even_in_the_allowed_account(identity_settings):
    # Clave de usuario IAM: sin session token y resuelta del entorno.
    identity_settings("133789123239", ["133789123239"],
                      credentials=_FakeCredentials("env", None),
                      arn="arn:aws:iam::133789123239:user/algun-humano")

    result = describe_identity()

    assert result["usable"] is False
    assert result["temporary"] is False
    assert result["static_credentials_present"] is True
    assert result["role"] == ""
    assert "is not an assumed role" in result["error"]


def test_temporary_credentials_from_a_static_source_are_rejected(identity_settings):
    # Credenciales de STS pegadas en ~/.aws/credentials: no es la federación OIDC.
    identity_settings("133789123239", ["133789123239"],
                      credentials=_FakeCredentials("shared-credentials-file", "fake-token"))

    result = describe_identity()

    assert result["usable"] is False
    assert result["static_credentials_present"] is True
    assert "shared-credentials-file" in result["error"]


def test_an_identity_outside_the_allowlist_is_rejected(identity_settings):
    identity_settings("999999999999", ["133789123239"])

    result = describe_identity()

    assert result["usable"] is False
    assert "999999999999" in result["error"]


def test_no_identity_falls_back_to_mock(identity_settings):
    identity_settings(RuntimeError("Unable to locate credentials"), ["133789123239"])

    result = describe_identity()

    assert result["usable"] is False
    assert "Unable to locate credentials" in result["error"]


# --- configuración por defecto de una sesión limpia -------------------------

def test_the_defaults_of_a_clean_session_touch_no_aws():
    settings = Settings(_env_file=None)

    assert settings.patch_provider == "mock"
    assert settings.restore_provider == "mock"
    assert settings.dry_run is True
    assert settings.lab_reconcile_on_startup is False
    assert settings.aws_profile == ""
    assert settings.aws_role_arn == ""
    assert settings.credentials_source() == "none"


def test_single_valued_allowlists_can_come_from_the_environment(monkeypatch):
    """`MSR_ALLOWED_REGIONS=eu-north-1` (CSV) es válido, no sólo JSON."""
    monkeypatch.setenv("MSR_ALLOWED_REGIONS", "eu-north-1")
    monkeypatch.setenv("MSR_ALLOWED_ACCOUNT_IDS", "133789123239,999999999999")

    settings = Settings(_env_file=None)

    assert settings.allowed_regions == ["eu-north-1"]
    assert settings.allowed_account_ids == ["133789123239", "999999999999"]


# --- el paquete de bootstrap para el equipo de cloud -------------------------

def test_the_bootstrap_package_is_atomic_and_self_contained():
    package = read(BOOTSTRAP)

    # Los tres elementos del bootstrap, con sus valores verificados.
    assert "https://deloitte-es.devinenterprise.com" in package
    assert "org_id:org-4793cba689a54a11b8fe70ed031524c4" in package
    assert "MSRExternalBackendRole" in package
    assert "PAY_PER_REQUEST" in package
    assert "expires_at" in package
    # No pide nada de la arquitectura descartada.
    for removed in ("ecs ", "ecr ", "aws elbv2", "nat-gateway", "create-vpc-endpoint"):
        assert removed not in package.lower(), removed
    # Las políticas publicadas: DynamoDB acotado a las tres acciones del lock.
    for document in json_blocks(package):
        actions = re.findall(r'"(dynamodb:\w+)"', document)
        assert set(actions) <= {"dynamodb:GetItem", "dynamodb:PutItem",
                                "dynamodb:DeleteItem"}, actions
        assert "iam:PassRole" not in document
    # Y no contiene ninguna credencial.
    for marker in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "aws_secret_access_key"):
        assert marker not in package, marker


def test_the_validation_checklist_covers_the_authorized_dry_run():
    package = read(BOOTSTRAP)

    for check in ("setup-aws-oidc", "app.preflight", "133789123239", "eu-north-1",
                  "Online", "MSR_DRY_RUN=true", "tags"):
        assert check in package, check
    assert "autorización explícita y separada" in package


# --- el informe de la fase 2.11 ---------------------------------------------

def test_the_verified_oidc_subject_is_documented():
    report = read(REPORT)

    assert "org_id:org-4793cba689a54a11b8fe70ed031524c4" in report
    assert "sts:AssumeRoleWithWebIdentity" in report
    assert "MSRExternalBackendRole" in report
    assert "msr-poc-lab-locks" in report
    # El informe describe el modelo sin credenciales, pero no contiene ninguna.
    for marker in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        assert marker not in report, marker
