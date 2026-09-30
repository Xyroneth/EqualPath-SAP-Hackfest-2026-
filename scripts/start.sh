#!/usr/bin/env bash
# One-command local start without Docker: installs deps (first run), builds the UI, serves on http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
[ -d backend/.venv ] || $PY -m venv backend/.venv
backend/.venv/bin/pip install -q -r backend/requirements-dev.txt
[ -d frontend/node_modules ] || npm ci --prefix frontend
npm run build --prefix frontend
echo "EQUALPATH running at http://localhost:8000"
cd backend && exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
