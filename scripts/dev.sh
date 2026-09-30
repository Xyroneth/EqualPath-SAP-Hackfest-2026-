#!/usr/bin/env bash
# Development: FastAPI with reload on :8000 and Vite dev server on :5173 (proxying /api)
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
trap 'kill 0' EXIT
npm run dev --prefix frontend
