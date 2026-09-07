"""Verificación de sólo lectura de la identidad de AWS del runtime.

    python -m app.identity_check

Llama únicamente a `sts:GetCallerIdentity` y comprueba que la cuenta resuelta
está en `MSR_ALLOWED_ACCOUNT_IDS`, que la identidad es un rol asumido y que las
credenciales son temporales. No inicia ninguna Automation, no muta nada y no
imprime credenciales: sólo cuenta, ARN, rol y cómo se resolvieron.

Código de salida 0 si hay una identidad utilizable, 1 en cualquier otro caso —
que es lo que usa `scripts/start_poc.sh` para decidir entre AWS y mock.
"""
from __future__ import annotations

import json
import sys

from .config import get_settings

# Orígenes de credenciales de larga duración: una clave escrita en el entorno o
# en `~/.aws/credentials`. La federación OIDC del blueprint resuelve
# `custom-process` (el `credential_process` que canjea el token de la sesión).
STATIC_CREDENTIAL_METHODS = frozenset({
    "env", "explicit", "shared-credentials-file", "credentials-file", "config-file",
})


def role_name(arn: str) -> str:
    """Nombre del rol de un ARN de identidad asumida, o cadena vacía."""
    marker = ":assumed-role/"
    if marker not in arn:
        return ""
    return arn.split(marker, 1)[1].split("/", 1)[0]


def describe_credentials(session) -> dict:
    """Cómo resolvió el SDK las credenciales, sin exponer ninguna.

    `temporary` es tener un session token: es lo que distingue unas credenciales
    de STS de una clave permanente de usuario IAM.
    """
    try:
        credentials = session.get_credentials()
    except Exception:  # noqa: BLE001 - la resolución fallida ya la reporta STS
        credentials = None
    if credentials is None:
        return {"credentials_method": "", "temporary": False,
                "static_credentials_present": False}
    method = getattr(credentials, "method", "") or ""
    temporary = bool(getattr(credentials.get_frozen_credentials(), "token", None))
    return {
        "credentials_method": method,
        "temporary": temporary,
        "static_credentials_present": method in STATIC_CREDENTIAL_METHODS or not temporary,
    }


def describe_identity() -> dict:
    settings = get_settings()
    result: dict = {
        "region": settings.aws_region,
        "credentials_source": settings.credentials_source(),
        "allowed_accounts": list(settings.allowed_account_ids),
    }
    try:
        import boto3
    except ImportError:
        return {**result, "usable": False, "error": "boto3 is not installed."}

    session_kwargs = {}
    if settings.aws_region:
        session_kwargs["region_name"] = settings.aws_region
    if settings.aws_profile:
        session_kwargs["profile_name"] = settings.aws_profile
    session = boto3.Session(**session_kwargs)
    try:
        identity = session.client("sts").get_caller_identity()
    except Exception as exc:  # noqa: BLE001 - cualquier fallo significa "sin identidad"
        return {**result, "usable": False, "error": f"{type(exc).__name__}: {exc}"}

    account = identity.get("Account", "")
    arn = identity.get("Arn", "")
    role = role_name(arn)
    credentials = describe_credentials(session)
    allowed = not settings.allowed_account_ids or account in settings.allowed_account_ids
    # Fail-closed: la cuenta debe estar en la allowlist y la identidad debe ser un
    # rol asumido con credenciales temporales. Una clave permanente nunca vale.
    errors = []
    if not allowed:
        errors.append(f"Account {account} is not in MSR_ALLOWED_ACCOUNT_IDS.")
    if not role:
        errors.append(f"Identity {arn or 'unknown'} is not an assumed role.")
    if credentials["static_credentials_present"]:
        errors.append("The credentials are not temporary "
                      f"(source: {credentials['credentials_method'] or 'unknown'}).")
    return {
        **result,
        **credentials,
        "account": account,
        "arn": arn,
        "role": role,
        "account_allowed": allowed,
        "usable": not errors,
        **({} if not errors else {"error": " ".join(errors)}),
    }


def main() -> int:
    result = describe_identity()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("usable") else 1


if __name__ == "__main__":
    sys.exit(main())
