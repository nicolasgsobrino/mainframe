"""Política mínima de seguridad para operaciones mutativas sobre objetivos.

Se evalúa SIEMPRE antes de arrancar una ejecución (incluso en dry-run) y sólo
usa datos ya resueltos por el provider mediante llamadas de sólo lectura.
"""
from __future__ import annotations

import re

from .config import Settings
from .providers.base import Target, TargetPolicyResult

# Instance ID real de EC2: i- + 8 o 17 hex. Los IDs sintéticos de la CMDB de
# demo (SRV-1001, APP-1002, ...) no cumplen este patrón y se rechazan.
INSTANCE_ID_RE = re.compile(r"^i-[0-9a-f]{8}([0-9a-f]{9})?$")

TERMINAL_INSTANCE_STATES = frozenset({"terminated", "shutting-down", "stopping", "stopped"})

_REDACTIONS = (
    (re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{8,20}\b"), "***AWS_ACCESS_KEY_REDACTED***"),
    (re.compile(r"\barn:aws:iam::\d{12}:[\w/+=.@-]+"), "arn:aws:iam::***:***"),
    (re.compile(r"(?i)\b(password|passwd|secret|token|api[-_]?key)\s*[:=]\s*\S+"), r"\1=***REDACTED***"),
    (re.compile(r"\b\d{12}\b"), "***ACCOUNT_ID***"),
    (re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
     "***PRIVATE_KEY_REDACTED***"),
)


def redact(text: str | None) -> str:
    """Elimina credenciales y datos sensibles reconocibles de un texto."""
    if not text:
        return ""
    out = str(text)
    for pattern, replacement in _REDACTIONS:
        out = pattern.sub(replacement, out)
    return out


def sanitize_text(text: str | None, limit: int = 2000) -> str:
    """Redacta y trunca cualquier salida antes de persistirla o mostrarla."""
    out = redact(text)
    if len(out) > limit:
        out = out[:limit] + f"… [truncado, {len(out)} caracteres]"
    return out


def assert_runbook_allowed(runbook: str, settings: Settings) -> str:
    """El runbook proviene de la configuración y debe estar en la allowlist."""
    if not runbook:
        raise PolicyViolation("RUNBOOK_NOT_CONFIGURED",
                             "No hay runbook de Automation configurado para esta operación.")
    if runbook not in settings.allowed_runbooks:
        raise PolicyViolation("RUNBOOK_NOT_ALLOWED",
                              f"El runbook '{runbook}' no está en la allowlist interna.")
    return runbook


def assert_parameters_allowed(parameters: dict, allowed_keys: set[str]) -> dict:
    """Sólo se admiten parámetros construidos por el backend (nunca del cliente)."""
    unexpected = sorted(set(parameters or {}) - set(allowed_keys))
    if unexpected:
        raise PolicyViolation("PARAMETERS_NOT_ALLOWED",
                              f"Parámetros no admitidos para el runbook: {', '.join(unexpected)}.")
    for key, value in (parameters or {}).items():
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str):
                raise PolicyViolation("PARAMETERS_NOT_ALLOWED",
                                      f"El parámetro '{key}' debe ser texto.")
            if any(ch in item for ch in (";", "|", "&&", "`", "$(")):
                raise PolicyViolation("PARAMETERS_NOT_ALLOWED",
                                      f"El parámetro '{key}' contiene metacaracteres de shell.")
    return dict(parameters or {})


class PolicyViolation(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def evaluate_target(target: Target, settings: Settings, *,
                    instance_state: str | None = None,
                    require_instance: bool = True,
                    strict: bool = False) -> TargetPolicyResult:
    """Evalúa cuenta, región, tags, entorno, estado e inscripción en SSM.

    Con `strict=True` (ejecución real en AWS) la política es *fail-closed*: una
    allowlist vacía no autoriza nada. En mock/dry-run se admite el modo
    laboratorio, menos restrictivo y etiquetado como tal en los checks.
    """
    checks: list[dict] = []
    violations: list[str] = []
    first_code: str | None = None

    def check(name: str, ok: bool, detail: str, code: str,
              ok_detail: str | None = None) -> None:
        """`detail` describe el incumplimiento; con `ok` se publica `ok_detail`."""
        nonlocal first_code
        checks.append({"check": name, "ok": ok,
                       "detail": (ok_detail or "Cumple la política.") if ok else detail})
        if not ok:
            violations.append(detail)
            if first_code is None:
                first_code = code

    if require_instance:
        instance_id = target.instance_id or ""
        check("Instance ID válido", bool(INSTANCE_ID_RE.match(instance_id)),
              f"El objetivo '{target.logical_target_id}' no tiene un Instance ID de EC2 válido "
              f"({instance_id or 'sin valor'}).", "TARGET_NOT_ALLOWED",
              f"Instance ID {instance_id}.")

    if settings.allowed_account_ids:
        check("Cuenta permitida", target.account_id in settings.allowed_account_ids,
              "La cuenta del objetivo no está en MSR_ALLOWED_ACCOUNT_IDS.", "TARGET_NOT_ALLOWED",
              f"La cuenta {target.account_id} está en MSR_ALLOWED_ACCOUNT_IDS.")
    elif strict:
        check("Cuenta permitida", False,
              "MSR_ALLOWED_ACCOUNT_IDS está vacío y en ejecución real no autoriza ninguna cuenta.",
              "POLICY_NOT_CONFIGURED")
    else:
        checks.append({"check": "Cuenta permitida", "ok": True,
                       "detail": "Sin allowlist de cuentas configurada (modo laboratorio)."})

    expected_region = settings.aws_region
    if require_instance and expected_region:
        check("Región permitida", target.region == expected_region,
              f"El objetivo está en '{target.region}' y la región configurada es '{expected_region}'.",
              "TARGET_NOT_ALLOWED", f"El objetivo está en la región configurada '{expected_region}'.")
    if settings.allowed_regions:
        check("Región en allowlist", target.region in settings.allowed_regions,
              "La región del objetivo no está en MSR_ALLOWED_REGIONS.", "TARGET_NOT_ALLOWED",
              f"La región {target.region} está en MSR_ALLOWED_REGIONS.")
    elif strict:
        check("Región en allowlist", False,
              "MSR_ALLOWED_REGIONS está vacío y en ejecución real no autoriza ninguna región.",
              "POLICY_NOT_CONFIGURED")

    if strict and not settings.required_target_tag_key:
        check("Tag obligatorio configurado", False,
              "MSR_REQUIRED_TARGET_TAG_KEY es obligatorio en ejecución real.",
              "POLICY_NOT_CONFIGURED")
    if settings.required_target_tag_key:
        tag_value = (target.tags or {}).get(settings.required_target_tag_key)
        check(f"Tag obligatorio {settings.required_target_tag_key}",
              tag_value == settings.required_target_tag_value,
              f"El objetivo no tiene el tag {settings.required_target_tag_key}="
              f"{settings.required_target_tag_value}.", "TARGET_NOT_ALLOWED",
              f"El objetivo tiene el tag {settings.required_target_tag_key}="
              f"{settings.required_target_tag_value}.")

    if settings.allowed_environments:
        check("Entorno permitido", (target.environment or "") in settings.allowed_environments,
              f"El entorno '{target.environment}' no está permitido para parcheo automático.",
              "TARGET_NOT_ALLOWED",
              f"El entorno '{target.environment}' está en MSR_ALLOWED_ENVIRONMENTS.")
    elif strict:
        check("Entorno permitido", False,
              "MSR_ALLOWED_ENVIRONMENTS está vacío y en ejecución real no autoriza ningún entorno.",
              "POLICY_NOT_CONFIGURED")

    if instance_state is not None:
        check("Instancia operativa", instance_state == "running",
              f"La instancia está en estado '{instance_state}'.", "TARGET_NOT_READY",
              "La instancia está en estado 'running'.")

    if require_instance:
        check("Nodo gestionado por SSM", bool(target.ssm_managed),
              "La instancia no aparece como managed node en Systems Manager.", "TARGET_NOT_READY",
              "La instancia es un managed node de Systems Manager.")

    allowed = not violations
    return TargetPolicyResult(
        allowed=allowed,
        checks=tuple(checks),
        violations=tuple(violations),
        error_code=None if allowed else first_code,
        message="Objetivo conforme con la política." if allowed else sanitize_text(" ".join(violations)),
        target=target,
    )
