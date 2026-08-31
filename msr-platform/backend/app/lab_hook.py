"""Hook de despliegue de ejecución única: deja el laboratorio listo.

Uso previsto (job de release/init, no el arranque de cada réplica):

    python -m app.lab_hook              # informa de lo que haría
    python -m app.lab_hook --confirm    # autoriza el reset destructivo en aws-real

Con `MSR_PATCH_PROVIDER=mock` no toca AWS. En `aws-dry-run` sólo consulta AWS con
APIs de sólo lectura y nunca inicia una Automation. El lock durable de SQLite
garantiza que dos ejecuciones simultáneas no reconcilien el mismo laboratorio.

Código de salida 0 si el laboratorio queda listo, 1 en cualquier otro caso.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .errors import DomainError
from .store import STORE

log = logging.getLogger("msr.lab.hook")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcilia el laboratorio de la PoC.")
    parser.add_argument("--lab-id", default=None,
                        help="Identificador lógico del laboratorio (por defecto, el configurado).")
    parser.add_argument("--confirm", action="store_true",
                        help="Autoriza explícitamente un reset destructivo en aws-real.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        result = STORE.ensure_lab_ready(args.lab_id, confirmed=args.confirm,
                                        reason="deployment-hook")
    except DomainError as exc:
        print(json.dumps(exc.to_payload(), ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main())
