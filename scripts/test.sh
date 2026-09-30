#!/usr/bin/env bash
# Unit/API tests (pytest) + end-to-end Priya journey (Playwright, against the production build)
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && .venv/bin/python -m pytest -q)
npm run build --prefix frontend
(cd frontend && npx playwright install chromium >/dev/null && npx playwright test --reporter=line)
