"""Validación de sólo lectura de la PoC contra AWS (`python -m app.preflight`).

Ningún test toca AWS: la identidad, la tabla de locks y el laboratorio se
inyectan. Lo que se fija aquí es el contrato: el preflight nunca autoriza un
reset, exige credenciales temporales y falla cerrado ante cualquier duda.
"""
from __future__ import annotations

import pytest

from app import preflight
from app.config import Settings
from app.errors import DomainError

READY_LAB = {
    "ready": True,
    "action": "none",
    "account_id": "133789123239",
    "region": "eu-north-1",
    "autoscaling_group_name": "msr-poc-linux-patching-01-asg",
    "instance_id": "i-0123456789abcdef0",
    "dry_run": True,
    "evidence": {"ssm_state": "Online", "vulnerable_state": "vulnerable",
                 "health_state": "healthy", "current_kernel": "6.1.147-180.264.amzn2023"},
}

FEDERATED_IDENTITY = {
    "region": "eu-north-1",
    "credentials_source": "default-chain",
    "allowed_accounts": ["133789123239"],
    "account": "133789123239",
    "arn": "arn:aws:sts::133789123239:assumed-role/MSRExternalBackendRole/devin",
    "role": "MSRExternalBackendRole",
    "temporary": True,
    "static_credentials_present": False,
    "account_allowed": True,
    "usable": True,
}


class _FakeLifecycle:
    def __init__(self, result: dict | DomainError):
        self._result = result
        self.calls: list[dict] = []

    def ensure_lab_ready(self, logical_lab_id=None, **kwargs):
        self.calls.append({"logical_lab_id": logical_lab_id, **kwargs})
        if isinstance(self._result, DomainError):
            raise self._result
        return self._result


class _FakeLocks:
    backend_name = "sqlite"


class _FakeStore:
    def __init__(self, lifecycle: _FakeLifecycle):
        self.lab_lifecycle = lifecycle
        self.lab_locks = _FakeLocks()

    def dynamodb_client(self):
        return object()


class _FakeLockBackend:
    """Doble de `DynamoDbLabLockBackend`: sólo `get`, nunca escribe."""

    def __init__(self, result):
        self._result = result
        self.requested: list[str] = []

    def __call__(self, table_name, client_factory, **kwargs):
        self.table_name = table_name
        return self

    def get(self, lab_id: str):
        self.requested.append(lab_id)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.fixture
def aws_dry_run_settings(monkeypatch):
    settings = Settings(_env_file=None, patch_provider="aws-automation",
                        restore_provider="aws-automation", dry_run=True,
                        aws_region="eu-north-1", allowed_account_ids=["133789123239"])
    monkeypatch.setattr(preflight, "get_settings", lambda: settings)
    return settings


@pytest.fixture
def lab(monkeypatch):
    def _install(result):
        lifecycle = _FakeLifecycle(result)
        monkeypatch.setattr(preflight, "STORE", _FakeStore(lifecycle))
        return lifecycle
    return _install


@pytest.fixture
def lock_table(monkeypatch):
    def _install(result):
        backend = _FakeLockBackend(result)
        monkeypatch.setattr(preflight, "DynamoDbLabLockBackend", backend)
        return backend
    return _install


@pytest.fixture
def identity(monkeypatch):
    def _install(result: dict):
        monkeypatch.setattr(preflight, "describe_identity", lambda: result)
    return _install


# --- identidad ---------------------------------------------------------------

def test_a_federated_temporary_identity_passes(identity):
    identity(FEDERATED_IDENTITY)

    assert preflight.check_identity()["ok"] is True


@pytest.mark.parametrize("override, reason", [
    ({"usable": False}, "cuenta fuera de la allowlist o sin identidad"),
    ({"temporary": False, "role": ""}, "credenciales no temporales (usuario IAM)"),
    ({"static_credentials_present": True}, "hay claves estáticas visibles para el SDK"),
])
def test_an_identity_that_is_not_temporary_and_federated_fails(identity, override, reason):
    identity({**FEDERATED_IDENTITY, **override})

    assert preflight.check_identity()["ok"] is False, reason


# --- valores por defecto seguros --------------------------------------------

def test_dry_run_and_no_startup_reconciliation_are_required(aws_dry_run_settings):
    assert preflight.check_safe_defaults()["ok"] is True

    aws_dry_run_settings.dry_run = False
    assert preflight.check_safe_defaults()["ok"] is False

    aws_dry_run_settings.dry_run = True
    aws_dry_run_settings.lab_reconcile_on_startup = True
    assert preflight.check_safe_defaults()["ok"] is False


# --- tabla de locks ----------------------------------------------------------

def test_an_empty_lock_table_is_reachable(aws_dry_run_settings, lab, lock_table):
    lab(READY_LAB)
    backend = lock_table(None)

    result = preflight.check_lock_table()

    assert result["ok"] is True
    assert result["reachable"] is True
    assert result["current_lock"] is None
    # Se consulta exactamente el laboratorio configurado, con la clave de partición.
    assert backend.requested == [aws_dry_run_settings.lab_logical_id]
    assert backend.table_name == "msr-poc-lab-locks"


def test_a_held_lock_is_reported_without_touching_it(aws_dry_run_settings, lab, lock_table):
    lab(READY_LAB)
    held = {"lab_id": "linux-patching-01", "operation": "reset", "holder": "otra-sesion"}
    lock_table(held)

    result = preflight.check_lock_table()

    assert result["ok"] is True
    assert result["current_lock"] == held


def test_an_unreachable_lock_table_fails(aws_dry_run_settings, lab, lock_table):
    lab(READY_LAB)
    lock_table(RuntimeError("AccessDeniedException"))

    result = preflight.check_lock_table()

    assert result["ok"] is False
    assert "AccessDeniedException" in result["error"]


def test_the_lock_table_is_not_checked_in_mock_mode(monkeypatch, lab):
    monkeypatch.setattr(preflight, "get_settings", lambda: Settings(_env_file=None))
    lab(READY_LAB)

    result = preflight.check_lock_table()

    assert result["ok"] is False
    assert "provider is not AWS" in result["error"]


# --- laboratorio -------------------------------------------------------------

def test_the_lab_check_never_authorizes_a_reset(aws_dry_run_settings, lab):
    lifecycle = lab(READY_LAB)

    result = preflight.check_lab()

    assert result["ok"] is True
    assert result["instance_id"] == "i-0123456789abcdef0"
    assert result["ssm_state"] == "Online"
    assert result["vulnerable_state"] == "vulnerable"
    assert result["health_state"] == "healthy"
    assert lifecycle.calls == [{"logical_lab_id": None, "allow_reset": False,
                               "confirmed": False, "reason": "preflight"}]


def test_a_patched_lab_fails_the_check_instead_of_resetting_it(aws_dry_run_settings, lab):
    lifecycle = lab({**READY_LAB, "ready": False, "action": "reset",
                     "error_code": "LAB_RESET_NOT_AUTHORIZED",
                     "evidence": {"vulnerable_state": "patched", "ssm_state": "Online",
                                  "health_state": "healthy"}})

    result = preflight.check_lab()

    assert result["ok"] is False
    assert result["error_code"] == "LAB_RESET_NOT_AUTHORIZED"
    assert lifecycle.calls[0]["allow_reset"] is False


def test_a_domain_error_is_reported_fail_closed(aws_dry_run_settings, lab):
    lab(DomainError("La instancia no está en la cuenta.", "LAB_TARGET_ACCOUNT_MISMATCH"))

    result = preflight.check_lab()

    assert result["ok"] is False
    assert result["error_code"] == "LAB_TARGET_ACCOUNT_MISMATCH"


# --- agregado ----------------------------------------------------------------

def test_the_preflight_passes_only_when_every_check_passes(aws_dry_run_settings, identity,
                                                           lab, lock_table):
    identity(FEDERATED_IDENTITY)
    lab(READY_LAB)
    lock_table(None)

    report = preflight.run_preflight()

    assert report["ok"] is True
    assert [check["check"] for check in report["checks"]] == [
        "identity", "safe_defaults", "lock_table", "lab"]
    assert preflight.main() == 0


def test_the_preflight_fails_when_the_identity_is_missing(aws_dry_run_settings, identity,
                                                         lab, lock_table):
    identity({**FEDERATED_IDENTITY, "usable": False})
    lab(READY_LAB)
    lock_table(None)

    assert preflight.run_preflight()["ok"] is False
    assert preflight.main() == 1
