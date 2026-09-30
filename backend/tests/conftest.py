import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_tmp = tempfile.mkdtemp(prefix="equalpath-test-")
os.environ.update(SQLITE_PATH=f"{_tmp}/test.db", CHECKPOINT_PATH=f"{_tmp}/ckpt.db", DEMO_STEP_DELAY_MS="0", LLM_PROVIDER="demo",
                  OPENAI_API_KEY="", AICORE_SERVICE_KEY="", SBPA_API_URL="", LOGIN_MAX_ATTEMPTS="5", LOGIN_LOCK_SECONDS="60")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASSWORDS = {"counsellor": "Counsel@2026", "hr_reviewer": "HRreview@2026", "auditor": "Audit@2026"}
_tokens: dict[str, str] = {}


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def H(role: str) -> dict:
    """Authorization header for a role (the Candidate is the open demo user and needs none)."""
    if role == "candidate":
        return {}
    if role not in _tokens:
        r = TestClient(app).post("/api/auth/login", json={"role": role, "password": PASSWORDS[role]})
        assert r.status_code == 200, r.text
        _tokens[role] = r.json()["token"]
    return {"Authorization": f"Bearer {_tokens[role]}"}


@pytest.fixture(scope="session")
def persona(client):
    return client.get("/api/demo/persona").json()


def wait(client, run_id, timeout=30, role="candidate"):
    end = time.time() + timeout
    while time.time() < end:
        v = client.get(f"/api/runs/{run_id}", headers=H(role)).json()
        if v["run"]["status"] != "running":
            return v
        time.sleep(0.05)
    raise AssertionError("run did not settle")


def new_candidate(client, persona, share=True, seed=True):
    r = client.post("/api/candidates", json={"profile": persona["profile"], "seed_persona": "priya" if seed else None,
                                             "consent": {"process_profile": True, "share_with_employer": share, "share_accommodations": share}})
    assert r.status_code == 200, r.text
    return r.json()["candidate_id"]


def new_run(client, persona, share=True):
    cid = new_candidate(client, persona, share)
    rid = client.post("/api/runs", json={"candidate_id": cid}).json()["run_id"]
    return cid, rid


def advance_to_final_review(client, persona):
    cid, rid = new_run(client, persona)
    wait(client, rid)
    assert client.post(f"/api/runs/{rid}/candidate-review", json={"decisions": []}).status_code == 200
    wait(client, rid)
    assert client.post(f"/api/runs/{rid}/role-selection", json={"role_id": "qa-automation-associate"}).status_code == 200
    v = wait(client, rid)
    assert v["interrupt"]["checkpoint"] == "final_review"
    return cid, rid


@pytest.fixture(autouse=True)
def _fresh_login_limiter():
    from app.providers.identity import limiter

    limiter._state.clear()
    yield
