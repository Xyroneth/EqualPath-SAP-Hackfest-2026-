"""Workflow / API tests: human interrupts, approval gating, audit log, privacy controls."""
from conftest import H, advance_to_final_review, new_candidate, new_run, wait


def test_graph_pauses_for_candidate_review_and_passport_is_blocked(client, persona):
    _, rid = new_run(client, persona)
    v = wait(client, rid)
    assert v["run"]["status"] == "waiting_for_human" and v["interrupt"]["checkpoint"] == "candidate_review"
    assert client.get(f"/api/runs/{rid}/passport").status_code == 409


def test_consent_is_required(client, persona):
    r = client.post("/api/candidates", json={"profile": persona["profile"], "seed_persona": "priya", "consent": {"process_profile": False}})
    assert r.status_code == 403


def test_final_review_is_gated_by_role_and_reason(client, persona):
    _, rid = advance_to_final_review(client, persona)
    assert client.get(f"/api/runs/{rid}/passport").status_code == 409
    assert client.post(f"/api/runs/{rid}/final-review", json={"decision": "approve"}).status_code == 403
    assert client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "reject"}).status_code == 422
    edit = {"target": "milestone:ms-3.estimated_hours", "new_value": 6, "reason": "Short evening sessions need a buffer"}
    assert client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "edit", "edits": [edit]}).status_code == 422
    r = client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "edit", "reason": "Adjust effort", "edits": [edit]})
    assert r.status_code == 200
    v = wait(client, rid)
    assert v["run"]["status"] == "completed"
    p = client.get(f"/api/runs/{rid}/passport").json()
    outcomes = [o["outcome"] for o in p["outcomes"]]
    assert outcomes == ["Ready with Learning Milestone", "Employer Action Required"]
    assert p["sections"]["human_review"]["edits"][0]["reason"] == "Short evening sessions need a buffer"
    assert set(p["sections"]) == {"capability_evidence", "role_gap_map", "work_condition_fit", "employer_readiness", "bias_audit", "human_review", "next_actions"}


def test_rejected_run_never_produces_a_passport(client, persona):
    _, rid = advance_to_final_review(client, persona)
    # The HR reviewer speaks for the employer, so the candidate's passport decision belongs to the counsellor alone.
    assert client.post(f"/api/runs/{rid}/final-review", headers=H("hr_reviewer"), json={"decision": "approve"}).status_code == 403
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "reject", "reason": "Evidence needs re-check"})
    v = wait(client, rid)
    assert v["run"]["status"] == "rejected"
    assert client.get(f"/api/runs/{rid}/passport").status_code == 409


def test_request_evidence_loops_back_to_review(client, persona):
    _, rid = advance_to_final_review(client, persona)
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "request_evidence", "reason": "Please add the Selenium script"})
    v = wait(client, rid)
    assert v["interrupt"]["checkpoint"] == "evidence_request"
    client.post(f"/api/runs/{rid}/evidence-response", json={"note": "Uploaded script"})
    v = wait(client, rid)
    assert v["interrupt"]["checkpoint"] == "final_review"


def test_milestone_evidence_changes_status_only_after_human_review(client, persona):
    _, rid = advance_to_final_review(client, persona)
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "approve"})
    wait(client, rid)
    ms = client.get(f"/api/runs/{rid}").json()["values"]["pathway"]["milestones"]
    sap = next(m for m in ms if m["learning_asset_provider"].startswith("SAP"))
    assert sap["learning_asset_url"].startswith("https://")
    sub = client.post(f"/api/runs/{rid}/milestones/{sap['milestone_id']}/evidence",
                      json={"evidence_kind": "reflection", "title": "Scenarios", "content": "Eight test scenarios for an approval workflow."}).json()
    gaps = {g["capability"]: g["status"] for g in client.get(f"/api/runs/{rid}").json()["values"]["pathway"]["gaps"]}
    assert gaps[sap["capability"]] != "verified"
    client.post(f"/api/evidence-submissions/{sub['submission_id']}/decision", headers=H("counsellor"), json={"decision": "accept", "reason": "Covers edge cases"})
    v = client.get(f"/api/runs/{rid}").json()
    gaps = {g["capability"]: g for g in v["values"]["pathway"]["gaps"]}
    assert gaps[sap["capability"]]["status"] == "verified"
    assert gaps[sap["capability"]]["evidence"]["verification_status"] == "assessed"


def test_audit_log_records_agents_and_humans_and_is_immutable(client, persona):
    _, rid = advance_to_final_review(client, persona)
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "approve"})
    wait(client, rid)
    a = client.get("/api/audit", params={"run_id": rid}).json()
    types = {e["event_type"] for e in a["events"]}
    assert {"run_started", "agent_execution", "human_decision"} <= types
    actors = {e["actor"] for e in a["events"]}
    for agent in ("Skills Discovery Agent", "Market Intelligence Agent", "Learning Pathway Agent", "Inclusive Matching Agent",
                  "Employer Readiness Agent", "Bias Audit Agent"):
        assert agent in actors
    assert a["chain"]["valid"]
    import sqlite3
    import os
    import pytest
    conn = sqlite3.connect(os.environ["SQLITE_PATH"])
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE audit_events SET summary='tampered'")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM audit_events")
    conn.rollback()
    conn.close()


def test_private_note_never_in_passport_and_data_can_be_deleted(client, persona):
    cid, rid = advance_to_final_review(client, persona)
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "approve"})
    wait(client, rid)
    html = client.get(f"/api/runs/{rid}/passport.html").text
    assert persona["profile"]["accommodations"]["private_note"] not in html
    emp = client.get(f"/api/runs/{rid}/passport", params={"audience": "employer"}).json()
    assert emp["audience"] == "employer"
    assert client.get(f"/api/candidates/{cid}/export").status_code == 200
    assert client.delete(f"/api/candidates/{cid}").json()["deleted_records"] > 0
    assert client.get(f"/api/candidates/{cid}").status_code == 404


def test_system_status_shows_active_provider_and_sap_services(client):
    s = client.get("/api/system/status").json()
    assert s["provider"]["kind"] == "demo" and s["provider"]["live"] is False
    names = {x["service"] for x in s["sap_services"]}
    assert "SAP AI Core - generative AI hub" in names and "SAP Build Process Automation" in names
    assert all(x["state"] != "connected" for x in s["sap_services"])  # nothing claims to be live without credentials


def test_sap_build_process_automation_callback_resumes_run(client, persona, monkeypatch):
    from app.config import get_settings
    _, rid = advance_to_final_review(client, persona)
    body = {"runId": rid, "decision": "approve", "reviewer": "A. Counsellor"}
    assert client.post("/api/integrations/sap-build/review-decision", json=body).status_code == 503  # not configured
    monkeypatch.setattr(get_settings(), "sbpa_callback_secret", "s3cret")
    assert client.post("/api/integrations/sap-build/review-decision", json=body, headers={"X-EqualPath-Callback-Secret": "bad"}).status_code == 401
    assert client.post("/api/integrations/sap-build/review-decision", json=body, headers={"X-EqualPath-Callback-Secret": "s3cret"}).status_code == 200
    v = wait(client, rid)
    assert v["run"]["status"] == "completed"
    assert v["values"]["final_review"]["via"] == "SAP Build Process Automation inbox"
