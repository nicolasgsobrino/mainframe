"""Verificación de sólo lectura de la identidad de AWS del runtime.

    python -m app.identity_check

Llama únicamente a `sts:GetCallerIdentity` y comprueba que la cuenta resuelta
está en `MSR_ALLOWED_ACCOUNT_IDS`. No inicia ninguna Automation, no muta nada y
no imprime credenciales: sólo cuenta, ARN y origen de las credenciales.

Código de salida 0 si hay una identidad utilizable, 1 en cualquier otro caso —
que es lo que usa `scripts/start_poc.sh` para decidir entre AWS y mock.
"""
from __future__ import annotations

import json
import sys

from .config import get_settings


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
        return {**result, "usable": False, "error": "boto3 no está instalado."}

    session_kwargs = {}
    if settings.aws_region:
        session_kwargs["region_name"] = settings.aws_region
    if settings.aws_profile:
        session_kwargs["profile_name"] = settings.aws_profile
    try:
        identity = boto3.Session(**session_kwargs).client("sts").get_caller_identity()
    except Exception as exc:  # noqa: BLE001 - cualquier fallo significa "sin identidad"
        return {**result, "usable": False, "error": f"{type(exc).__name__}: {exc}"}

    account = identity.get("Account", "")
    allowed = not settings.allowed_account_ids or account in settings.allowed_account_ids
    return {
        **result,
        "account": account,
        "arn": identity.get("Arn", ""),
        "account_allowed": allowed,
        "usable": allowed,
        **({} if allowed else
           {"error": f"La cuenta {account} no está en MSR_ALLOWED_ACCOUNT_IDS."}),
    }


def main() -> int:
    result = describe_identity()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("usable") else 1


if __name__ == "__main__":
    sys.exit(main())
