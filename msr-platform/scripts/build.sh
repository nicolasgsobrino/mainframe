#!/usr/bin/env bash
# Compila el frontend y lo copia a backend/static para servirlo desde FastAPI.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
npm install
npm run build
rm -rf "$ROOT/backend/static"
cp -r dist "$ROOT/backend/static"
echo "Frontend compilado en backend/static. Arranca: cd backend && uvicorn app.main:app --port 8080"
