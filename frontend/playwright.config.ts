import { defineConfig } from '@playwright/test';

// Runs against the production build served by FastAPI (npm run build first). Uses its own port and a fresh database.
const PORT = process.env.EQUALPATH_E2E_PORT ?? '8020';
export default defineConfig({
  testDir: './e2e',
  timeout: 150_000,
  workers: 1,
  use: { baseURL: process.env.EQUALPATH_URL ?? `http://127.0.0.1:${PORT}`, viewport: { width: 1440, height: 900 }, screenshot: 'only-on-failure' },
  webServer: process.env.EQUALPATH_URL
    ? undefined
    : {
        command: `rm -f /tmp/equalpath-e2e*.db* && cd ../backend && DEMO_STEP_DELAY_MS=120 LLM_PROVIDER=demo SQLITE_PATH=/tmp/equalpath-e2e.db CHECKPOINT_PATH=/tmp/equalpath-e2e-ckpt.db .venv/bin/uvicorn app.main:app --port ${PORT}`,
        url: `http://127.0.0.1:${PORT}/api/health`,
        reuseExistingServer: false,
        timeout: 60_000,
      },
});
