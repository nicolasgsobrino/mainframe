#!/usr/bin/env bash
# Arranca la PoC de MSR en la VM de la sesión de Devin. Idempotente: se puede
# repetir tras dormir/reiniciar la sesión, que pierde los procesos pero no el disco.
#
#   scripts/start_poc.sh              # modo automático: AWS si hay identidad, mock si no
#   MSR_POC_MODE=mock scripts/start_poc.sh
#   MSR_POC_MODE=aws  scripts/start_poc.sh   # falla si no hay identidad de workload
#
# Nunca ejecuta un patch ni un reset: `MSR_DRY_RUN=true` y la comprobación del
# laboratorio es la no destructiva (`app.lab_hook` sin `--confirm`).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${MSR_POC_PORT:-8080}"
MODE="${MSR_POC_MODE:-auto}"
LOG="$ROOT/data/uvicorn.log"

log() { printf '\n=== %s\n' "$1"; }

# --- 1. Dependencias (incrementales) -----------------------------------------
log "Dependencias"
[ -d "$ROOT/backend/.venv" ] || python3 -m venv "$ROOT/backend/.venv"
PY="$ROOT/backend/.venv/bin/python"
"$PY" -m pip install -q --disable-pip-version-check -r "$ROOT/backend/requirements.txt"
[ -d "$ROOT/frontend/node_modules" ] || (cd "$ROOT/frontend" && npm install --silent)

# --- 2. Build de producción de la SPA ----------------------------------------
# Sólo recompila si falta o si hay fuentes más recientes que el build.
if [ ! -f "$ROOT/backend/static/index.html" ] ||
   [ -n "$(find "$ROOT/frontend/src" "$ROOT/frontend/index.html" \
            -newer "$ROOT/backend/static/index.html" -print -quit 2>/dev/null)" ]; then
  log "Compilando el frontend"
  "$ROOT/scripts/build.sh" >/dev/null
else
  log "Frontend ya compilado (backend/static)"
fi

# --- 3. Configuración (no hay secretos: ningún valor de abajo es sensible) ----
# Las credenciales de AWS NO se configuran aquí: las resuelve la cadena estándar
# del SDK desde la identidad de workload federada por OIDC de la sesión.
export MSR_AWS_REGION="${MSR_AWS_REGION:-eu-north-1}"
export MSR_AWS_PROFILE=""
export MSR_AWS_ROLE_ARN=""
export MSR_DRY_RUN="${MSR_DRY_RUN:-true}"
export MSR_LAB_RECONCILE_ON_STARTUP=false
export MSR_LAB_LOGICAL_ID="${MSR_LAB_LOGICAL_ID:-linux-patching-01}"
export MSR_LAB_AUTOSCALING_GROUP_NAME="${MSR_LAB_AUTOSCALING_GROUP_NAME:-msr-poc-${MSR_LAB_LOGICAL_ID}-asg}"
export MSR_PATCH_RUNBOOK_NAME="${MSR_PATCH_RUNBOOK_NAME:-MSR-PatchLinuxInstance}"
export MSR_ROLLBACK_RUNBOOK_NAME="${MSR_ROLLBACK_RUNBOOK_NAME:-MSR-RollbackLinuxInstance}"
export MSR_RESET_RUNBOOK_NAME="${MSR_RESET_RUNBOOK_NAME:-MSR-ResetLabInstance}"
export MSR_JOBS_DB_PATH="${MSR_JOBS_DB_PATH:-$ROOT/data/msr_jobs.db}"
mkdir -p "$(dirname "$MSR_JOBS_DB_PATH")"

# --- 4. Identidad de AWS (sólo lectura: sts:GetCallerIdentity) ---------------
log "Identidad de AWS"
IDENTITY="$(cd "$ROOT/backend" && "$PY" -m app.identity_check 2>&1)" && AWS_OK=1 || AWS_OK=0
echo "$IDENTITY"

case "$MODE" in
  aws)
    [ "$AWS_OK" = "1" ] || { echo "MSR_POC_MODE=aws pero no hay identidad de AWS utilizable." >&2; exit 1; }
    ;;
  mock) AWS_OK=0 ;;
  auto) : ;;
  *) echo "MSR_POC_MODE debe ser auto, aws o mock." >&2; exit 1 ;;
esac

if [ "$AWS_OK" = "1" ]; then
  export MSR_PATCH_PROVIDER=aws-automation
  export MSR_RESTORE_PROVIDER=aws-automation
  # Allowlist fail-closed: contra AWS una lista vacía nunca significa «todo».
  # En mock no se aplica, porque el laboratorio simulado no vive en esa cuenta.
  export MSR_ALLOWED_ACCOUNT_IDS="${MSR_ALLOWED_ACCOUNT_IDS:-133789123239}"
  export MSR_ALLOWED_REGIONS="${MSR_ALLOWED_REGIONS:-eu-north-1}"
  export MSR_ALLOWED_ENVIRONMENTS="${MSR_ALLOWED_ENVIRONMENTS:-sandbox}"
  log "Providers: aws-automation (MSR_DRY_RUN=$MSR_DRY_RUN)"
else
  export MSR_PATCH_PROVIDER=mock
  export MSR_RESTORE_PROVIDER=mock
  log "Providers: mock (sin identidad de AWS; la demo funciona simulada)"
fi

# --- 5. Backend en :8080 (reinicio idempotente) ------------------------------
log "Backend"
if curl -fsS -m 3 "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
  echo "Ya había un backend en :$PORT; se reinicia para aplicar esta configuración."
fi
pkill -f "uvicorn app.main:app .*--port $PORT" 2>/dev/null || true
sleep 1
(cd "$ROOT/backend" && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
   >"$LOG" 2>&1 &)

for _ in $(seq 1 40); do
  if curl -fsS -m 3 "http://localhost:$PORT/api/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS -m 5 "http://localhost:$PORT/api/health" ||
  { echo "El backend no responde; log en $LOG" >&2; tail -20 "$LOG" >&2; exit 1; }
echo
curl -fsS -m 5 "http://localhost:$PORT/api/execution" || true
echo

# --- 6. Laboratorio: comprobación NO destructiva ------------------------------
# Sin `--confirm`: descubre la instancia por tags e informa. Nunca resetea.
log "Laboratorio (comprobación no destructiva)"
(cd "$ROOT/backend" && "$PY" -m app.lab_hook) ||
  echo "El laboratorio no está listo (ver salida): la aplicación sigue arriba."

cat <<EOF

=== Listo
Abre http://localhost:$PORT en el navegador de la VM y opéralo desde la pestaña
Desktop de la sesión. Log del backend: $LOG
Un patch o un reset reales siguen exigiendo autorización explícita
(MSR_DRY_RUN=false y, para recrear el laboratorio, \`app.lab_hook --confirm\`).
EOF
