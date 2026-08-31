#!/usr/bin/env bash
# Arranca backend (8080) y frontend (5173) en desarrollo.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT/backend"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --reload --port 8080 &
BACK=$!

cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run dev

kill $BACK 2>/dev/null || true
