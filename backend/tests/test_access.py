"""Sign-in, role-based access, evidence files (upload, viewers) and privacy rules."""
import io
import zipfile

import pytest
from conftest import PASSWORDS, H, advance_to_final_review, new_candidate, new_run, wait

from app import tokens
from app.main import app
from fastapi.testclient import TestClient


# ------------------------------------------------------------------ sign-in

def test_each_staff_role_has_its_own_password(client):
    assert len(set(PASSWORDS.values())) == 3
    for role, pw in PASSWORDS.items():
        r = client.post("/api/auth/login", json={"role": role, "password": pw})
        assert r.status_code == 200 and r.json()["role"] == role
        others = [p for r2, p in PASSWORDS.items() if r2 != role]
        assert client.post("/api/auth/login", json={"role": role, "password": others[0]}).status_code == 401


def test_candidate_needs_no_password_but_staff_roles_do(client):
    assert client.post("/api/auth/login", json={"role": "candidate"}).status_code == 200
    for role in PASSWORDS:
        assert client.post("/api/auth/login", json={"role": role}).status_code == 401
        assert client.post("/api/auth/login", json={"role": role, "password": ""}).status_code == 401


def test_repeated_wrong_passwords_lock_sign_in():
    c = TestClient(app)  # a fresh client, same address; use a role nobody else signs into during this test
    codes = [c.post("/api/auth/login", json={"role": "auditor", "password": f"wrong{i}"}).status_code for i in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    assert c.post("/api/auth/login", json={"role": "auditor", "password": PASSWORDS["auditor"]}).status_code == 429  # even the right password waits
    from app.providers.identity import limiter

    limiter._state.clear()


def test_x_demo_role_header_no_longer_grants_access(client):
    assert client.get("/api/reviews", headers={"X-Demo-Role": "counsellor"}).status_code == 403


def test_forged_and_expired_tokens_are_rejected(client):
    assert client.get("/api/reviews", headers={"Authorization": "Bearer not.a.token"}).status_code == 401
    tampered = H("counsellor")["Authorization"][:-3] + "abc"
    assert client.get("/api/reviews", headers={"Authorization": tampered}).status_code == 401
    expired = tokens.sign({"typ": "session", "role": "counsellor"}, -5)
    assert client.get("/api/reviews", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    view_token_as_session = tokens.sign({"typ": "view", "role": "counsellor"}, 300)
    assert client.get("/api/reviews", headers={"Authorization": f"Bearer {view_token_as_session}"}).status_code == 401


def test_sign_in_and_failures_are_audited_without_passwords(client):
    client.post("/api/auth/login", json={"role": "hr_reviewer", "password": "definitely-wrong"})
    ev = client.get("/api/audit", headers=H("auditor")).json()["events"]
    assert any(e["event_type"] == "auth_failed" for e in ev) and any(e["event_type"] == "auth_login" for e in ev)
    assert "definitely-wrong" not in str(ev)


# ------------------------------------------------------------------ who can see what

def test_persona_and_review_queue_are_role_gated(client):
    assert client.get("/api/demo/persona", headers=H("hr_reviewer")).status_code == 403
    assert client.get("/api/demo/persona", headers=H("auditor")).status_code == 403
    assert client.get("/api/reviews").status_code == 403  # candidate
    assert client.get("/api/reviews", headers=H("counsellor")).status_code == 200
    assert client.get("/api/reviews", headers=H("hr_reviewer")).status_code == 200
    assert client.get("/api/reviews", headers=H("auditor")).status_code == 403


def test_raw_evidence_is_only_for_candidate_and_counsellor(client, persona):
    cid = new_candidate(client, persona)
    assert client.get(f"/api/candidates/{cid}/documents").status_code == 200
    assert client.get(f"/api/candidates/{cid}/documents", headers=H("counsellor")).status_code == 200
    for role in ("hr_reviewer", "auditor"):
        assert client.get(f"/api/candidates/{cid}/documents", headers=H(role)).status_code == 403
        assert client.get(f"/api/candidates/{cid}", headers=H(role)).status_code == 403
        assert client.post(f"/api/candidates/{cid}/documents/resume.pdf/view-link", headers=H(role)).status_code == 403
    assert client.post(f"/api/candidates/{cid}/documents/text", headers=H("counsellor"), json={"title": "x" * 3, "text": "y" * 30}).status_code == 403


def test_document_metadata_never_exposes_extracted_text(client, persona):
    cid = new_candidate(client, persona)
    body = client.get(f"/api/candidates/{cid}/documents").json()
    assert len(body["documents"]) == 6
    assert all("text" not in d and d["text_chars"] > 0 for d in body["documents"])


def test_run_view_is_trimmed_for_other_roles(client, persona):
    _, rid = advance_to_final_review(client, persona)
    cand = client.get(f"/api/runs/{rid}").json()["values"]
    assert "skills" in cand and "discovery" in cand
    coun = client.get(f"/api/runs/{rid}", headers=H("counsellor")).json()["values"]
    assert "skills" in coun
    hr = client.get(f"/api/runs/{rid}", headers=H("hr_reviewer")).json()
    assert "skills" not in hr["values"] and "discovery" not in hr["values"] and "employer_scan" in hr["values"]
    assert all("evidence_quote" not in (g.get("evidence") or {}) for g in hr["values"]["pathway"]["gaps"])
    assert "Created and executed" not in str(hr)
    au = client.get(f"/api/runs/{rid}", headers=H("auditor")).json()
    assert set(au["values"]) <= {"bias_audit", "employer_scan", "selected_role_id", "provider", "final_review"}
    assert "Created and executed" not in str(au) and all(t["inputs"] == {} for t in au["timeline"])
    assert au["interrupt"] is None or set(au["interrupt"]) <= {"checkpoint", "title", "required_role"}


def test_hr_gets_only_the_employer_copy_of_the_passport(client, persona):
    _, rid = advance_to_final_review(client, persona)
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "approve"})
    from conftest import wait

    wait(client, rid)
    hr = client.get(f"/api/runs/{rid}/passport", params={"audience": "candidate"}, headers=H("hr_reviewer")).json()
    assert hr["audience"] == "employer"
    assert client.get(f"/api/runs/{rid}/passport", headers=H("auditor")).status_code == 403


def test_only_counsellor_reviews_evidence_and_only_hr_approves_jd(client, persona):
    _, rid = advance_to_final_review(client, persona)
    assert client.post(f"/api/runs/{rid}/jd-rewrite/decision", headers=H("counsellor"), json={"decision": "approve", "reason": "looks fine"}).status_code == 403
    assert client.post(f"/api/runs/{rid}/jd-rewrite/decision", headers=H("hr_reviewer"), json={"decision": "approve", "reason": "looks fine"}).status_code == 200
    assert client.post("/api/evidence-submissions/none/decision", headers=H("hr_reviewer"), json={"decision": "accept", "reason": "fine ok"}).status_code == 403
    assert client.get("/api/reviews", headers=H("hr_reviewer")).json()["evidence_reviews"] == []


def test_audit_trail_access(client, persona):
    assert client.get("/api/audit").status_code == 403  # a candidate must name their own run
    cid, rid = advance_to_final_review(client, persona)
    assert client.get("/api/audit", params={"run_id": rid}).status_code == 200
    hr = client.get("/api/audit", params={"run_id": rid}, headers=H("hr_reviewer")).json()["events"]
    assert all(e["details"] == {} for e in hr)


# ------------------------------------------------------------------ viewing evidence

def _link(client, cid, sid, role="candidate"):
    r = client.post(f"/api/candidates/{cid}/documents/{sid}/view-link", headers=H(role))
    assert r.status_code == 200, r.text
    return r.json()["url"]


def test_pdf_opens_as_a_real_pdf_and_xlsx_as_a_formatted_sheet(client, persona):
    cid = new_candidate(client, persona)
    pdf = client.get(_link(client, cid, "resume.pdf"))
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF-")
    assert "inline" in pdf.headers["content-disposition"] and pdf.headers["cache-control"] == "no-store"
    xl = client.get(_link(client, cid, "defect-tracker.xlsx"))
    assert xl.status_code == 200 and xl.headers["content-type"].startswith("text/html")
    html = xl.text
    for needle in ("Defects", "Dashboard", "Triage notes", "Open defects by severity", "<svg", "DEF-1001", "Download original"):
        assert needle in html, needle
    assert "<script" not in html.lower() and "script-src" not in html and "default-src 'none'" in xl.headers["content-security-policy"]
    assert client.get(_link(client, cid, "defect-tracker.xlsx") + "?dl=1").headers["content-disposition"].startswith("attachment")


def test_view_links_expire_and_are_audited(client, persona):
    cid = new_candidate(client, persona)
    expired = tokens.sign({"typ": "view", "cid": cid, "sid": "resume.pdf", "role": "candidate"}, -1)
    assert client.get(f"/api/view/{expired}").status_code == 403
    hr_token = tokens.sign({"typ": "view", "cid": cid, "sid": "resume.pdf", "role": "hr_reviewer"}, 300)
    assert client.get(f"/api/view/{hr_token}").status_code == 403
    _link(client, cid, "resume.pdf", "counsellor")
    ev = client.get("/api/audit", params={"candidate_id": cid}, headers=H("auditor")).json()["events"]
    assert any(e["event_type"] == "evidence_viewed" and "Counsellor" in e["summary"] for e in ev)


# ------------------------------------------------------------------ uploading evidence

def _upload(client, cid, name, data, **form):
    return client.post(f"/api/candidates/{cid}/documents/upload", files={"file": (name, data)}, data={"title": form.pop("title", "My file"), **form})


def _docx(paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def _pptx(slides):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i, lines in enumerate(slides, 1):
            paras = "".join(f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in lines)
            z.writestr(f"ppt/slides/slide{i}.xml", f'<p:sld xmlns:p="p" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld>{paras}</p:cSld></p:sld>')
    return buf.getvalue()


def test_all_common_file_types_can_be_added_and_viewed(client, persona):
    from openpyxl import Workbook

    cid = new_candidate(client, persona, seed=False)
    wb = Workbook(); wb.active.append(["Test", "Result"]); wb.active.append(["Login works", "Pass"]); xbuf = io.BytesIO(); wb.save(xbuf)
    pdf = (__import__("pathlib").Path(__file__).parent.parent / "app/data/evidence/resume.pdf").read_bytes()
    files = {"notes.pdf": pdf, "report.docx": _docx(["Automated the login tests with Playwright and pytest."]), "slides.pptx": _pptx([["Demo", "Selenium test run"]]),
             "results.xlsx": xbuf.getvalue(), "data.csv": b"id,status\n1,pass\n", "readme.md": b"# Notes\nWrote API tests with Postman.", "data.json": b'{"a": 1}',
             "script.py": b"def test_login():\n    assert True\n"}
    for name, data in files.items():
        r = _upload(client, cid, name, data)
        assert r.status_code == 200, (name, r.text)
        assert r.json()["text_chars"] > 0
        view = client.get(_link(client, cid, name))
        assert view.status_code == 200, name
    img = _upload(client, cid, "shot.png", b"\x89PNG\r\n\x1a\n" + b"0" * 40, description="Screenshot of a passing pytest run for the login tests")
    assert img.status_code == 200 and img.json()["kind"] == "image"
    assert client.get(_link(client, cid, "shot.png")).headers["content-type"] == "image/png"
    docs = client.get(f"/api/candidates/{cid}/documents").json()["documents"]
    assert len(docs) == len(files) + 1


def test_bad_uploads_are_rejected_with_clear_messages(client, persona):
    cid = new_candidate(client, persona, seed=False)
    assert _upload(client, cid, "virus.exe", b"MZ....").status_code == 422
    assert "save it as .docx" in _upload(client, cid, "old.doc", b"x" * 50).text
    assert _upload(client, cid, "fake.pdf", b"not a pdf at all").status_code == 422
    assert _upload(client, cid, "empty.txt", b"").status_code == 422
    assert _upload(client, cid, "big.txt", b"a" * (8 * 1024 * 1024 + 10)).status_code == 422
    assert "describe" in _upload(client, cid, "shot.png", b"\x89PNG\r\n\x1a\n" + b"0" * 40).text
    assert _upload(client, cid, "evil.html", b"<script>alert(1)</script>").status_code == 422
    assert client.post(f"/api/candidates/{cid}/documents/upload", files={"file": ("a.txt", b"hello world " * 5)}, data={"evidence_type": "nonsense"}).status_code == 422
    assert _upload(client, cid, "x.txt", b"hello world " * 5, ).status_code == 200
    assert _upload(client, cid, "../../etc/passwd.txt", b"hello world " * 5).json()["source_id"] == "passwd.txt"


def test_uploaded_text_feeds_the_skills_agent_and_can_be_removed(client, persona):
    from conftest import wait

    cid = new_candidate(client, persona, seed=False)
    _upload(client, cid, "api.md", b"Wrote 12 API tests with Postman and checked every status code and JSON response for the orders service.", evidence_type="work_sample")
    rid = client.post("/api/runs", json={"candidate_id": cid}).json()["run_id"]
    v = wait(client, rid)
    skills = {s["normalized_skill"]: s for s in v["values"]["discovery"]["skills"]}
    assert skills["api_testing"]["verification_status"] == "source_supported" and skills["api_testing"]["source_id"] == "api.md"
    cid2 = new_candidate(client, persona, seed=False)
    _upload(client, cid2, "a.md", b"Wrote a lot of notes here for testing purposes only.")
    assert client.delete(f"/api/candidates/{cid2}/documents/a.md").status_code == 200
    assert client.get(f"/api/candidates/{cid2}/documents").json()["documents"] == []


def test_run_needs_at_least_one_document(client, persona):
    cid = new_candidate(client, persona, seed=False)
    assert client.post("/api/runs", json={"candidate_id": cid}).status_code == 422


def test_profile_update_keeps_private_note_out_of_the_profile_record(client, persona):
    from app.providers.repository import get_repository

    cid = new_candidate(client, persona)
    stored = get_repository().get("candidates", cid)
    assert "private_note" not in stored["profile"]["accommodations"]
    assert client.get(f"/api/candidates/{cid}").json()["profile"]["accommodations"]["private_note"]
    assert "private_note" not in client.get(f"/api/candidates/{cid}", headers=H("counsellor")).json()["profile"]["accommodations"]
    prof = client.get(f"/api/candidates/{cid}").json()["profile"]
    prof["accommodations"]["private_note"] = "changed note"
    assert client.put(f"/api/candidates/{cid}", json={"profile": prof}).status_code == 200
    assert client.get(f"/api/candidates/{cid}").json()["profile"]["accommodations"]["private_note"] == "changed note"
    assert client.put(f"/api/candidates/{cid}", headers=H("counsellor"), json={"profile": prof}).status_code == 403


def test_deleting_the_candidate_removes_their_files(client, persona):
    from app.providers.repository import get_repository

    cid = new_candidate(client, persona)
    assert get_repository().get("files", f"{cid}:resume.pdf")
    client.delete(f"/api/candidates/{cid}")
    assert get_repository().get("files", f"{cid}:resume.pdf") is None
    with pytest.raises(Exception):
        client.get(_link(client, cid, "resume.pdf"))


# ------------------------------------------------------------------ employer side (HR Reviewer) and oversight (Auditor)

def _choose_role(client, persona, role_id):
    cid, rid = new_run(client, persona)
    wait(client, rid)
    client.post(f"/api/runs/{rid}/candidate-review", json={"decisions": []})
    wait(client, rid)
    client.post(f"/api/runs/{rid}/role-selection", json={"role_id": role_id})
    return cid, rid, wait(client, rid)


@pytest.mark.parametrize("role_id,employer", [("software-test-analyst", "kaveri"), ("application-support-analyst", "gomti"), ("data-quality-associate", "indus")])
def test_every_role_choice_gets_its_own_employer_ad_and_scan(client, persona, role_id, employer):
    _, rid, v = _choose_role(client, persona, role_id)
    scan = v["values"]["employer_scan"]
    assert scan["employer_id"] == employer and scan["job_text"] and scan["claims"] and scan["flags"]
    assert scan["improved_job_id"] and scan["suggested_rewrite"]["changes"]
    assert client.get(f"/api/runs/{rid}/jd-rewrite").json()["employer_id"] == employer


def test_hr_answers_conflicting_claims_and_responds_to_the_candidate(client, persona):
    cid, rid = advance_to_final_review(client, persona)
    tasks = client.get(f"/api/runs/{rid}/employer-tasks", headers=H("hr_reviewer")).json()
    assert [t["status"] for t in tasks["tasks"]] == ["todo", "todo", "locked"]
    body = {"resolution": "fix_ad", "note": "We will remove the uninterrupted-experience line this week."}
    assert client.post(f"/api/runs/{rid}/claims/career_breaks/response", headers=H("counsellor"), json=body).status_code == 403
    assert client.post(f"/api/runs/{rid}/claims/work_mode/response", headers=H("hr_reviewer"), json=body).status_code == 409  # not in conflict
    assert client.post(f"/api/runs/{rid}/claims/career_breaks/response", headers=H("hr_reviewer"), json=body).status_code == 200
    decision = {"decision": "invite", "reason": "Strong verified testing evidence.", "adjustments": ["Interviews scheduled with at least 48 hours notice"]}
    assert client.post(f"/api/runs/{rid}/employer-decision", headers=H("hr_reviewer"), json=decision).status_code == 409  # no passport yet
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "approve"})
    wait(client, rid)
    assert client.post(f"/api/runs/{rid}/employer-decision", headers=H("hr_reviewer"), json={**decision, "adjustments": ["Anything I like"]}).status_code == 422
    assert client.post(f"/api/runs/{rid}/employer-decision", headers=H("hr_reviewer"), json=decision).status_code == 200
    assert client.post(f"/api/runs/{rid}/employer-decision", headers=H("hr_reviewer"), json=decision).status_code == 409  # only once
    p = client.get(f"/api/runs/{rid}/passport").json()
    assert p["employer_response"]["decision"] == "invite" and p["employer_response"]["adjustments"] == decision["adjustments"]
    assert "career_breaks" in p["sections"]["employer_readiness"]["claim_responses"]
    types = {e["event_type"] for e in client.get(f"/api/audit?run_id={rid}").json()["events"]}
    assert {"employer_claim_response", "employer_decision"} <= types


def test_employer_cannot_respond_without_the_candidates_consent(client, persona):
    cid, rid = new_run(client, persona, share=False)
    wait(client, rid)
    client.post(f"/api/runs/{rid}/candidate-review", json={"decisions": []})
    wait(client, rid)
    client.post(f"/api/runs/{rid}/role-selection", json={"role_id": "qa-automation-associate"})
    wait(client, rid)
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "approve"})
    wait(client, rid)
    r = client.post(f"/api/runs/{rid}/employer-decision", headers=H("hr_reviewer"), json={"decision": "invite", "reason": "Looks good to us."})
    assert r.status_code == 409 and "agreed" in r.json()["detail"]


def test_auditor_verifies_the_log_and_signs_off_fairness(client, persona):
    cid, rid = advance_to_final_review(client, persona)
    assert client.post("/api/audit/verify", headers=H("hr_reviewer")).status_code == 403
    r = client.post("/api/audit/verify", headers=H("auditor")).json()
    assert r["valid"] and r["events"] > 0
    body = {"finding": "no_concerns", "note": "Twins identical; control test catches the biased filter."}
    assert client.post(f"/api/runs/{rid}/fairness-review", headers=H("counsellor"), json=body).status_code == 403
    assert client.post(f"/api/runs/{rid}/fairness-review", headers=H("auditor"), json=body).status_code == 200
    assert client.get(f"/api/runs/{rid}/fairness-review", headers=H("counsellor")).json()["review"]["finding"] == "no_concerns"
    events = client.get("/api/audit", headers=H("auditor")).json()["events"]
    assert {"audit_verified", "fairness_reviewed"} <= {e["event_type"] for e in events}


def test_fairness_twins_hide_the_candidates_real_details_from_staff_without_access(client, persona):
    cid, rid = advance_to_final_review(client, persona)
    mine = client.get(f"/api/runs/{rid}").json()["values"]["bias_audit"]["counterfactuals"]
    assert any(d["before"] == persona["profile"]["display_name"] for t in mine for d in t["diff"])
    for role in ("auditor", "hr_reviewer"):
        twins = client.get(f"/api/runs/{rid}", headers=H(role)).json()["values"]["bias_audit"]["counterfactuals"]
        assert all(d["before"] is None for t in twins for d in t["diff"])
        assert all(t["twin_name"] in (None, "Rahul Verma", "Ayesha Khan") for t in twins)


def test_anyone_can_run_their_own_twin_and_only_the_biased_filter_moves(client, persona):
    cid, rid = advance_to_final_review(client, persona)
    try_ = lambda field, value, role="candidate": client.post(f"/api/runs/{rid}/fairness/try", headers=H(role) if role != "candidate" else {}, json={"field": field, "value": value})
    for field, value, ref_moves in [("age", "58", True), ("college", "IIT Bombay", True), ("career_break_years", "0", True),
                                    ("name", "Mohammed Iqbal", False), ("gender", "male", False), ("disability", "Wheelchair user", False)]:
        r = try_(field, value).json()
        assert r["selected_score_before"] == r["selected_score_after"] and not r["material_change"], field  # EQUALPATH never moves
        assert r["reference"]["would_flag"] is ref_moves, field                                              # the biased filter does
        if ref_moves:
            assert r["reference"]["reasons"], field
    assert try_("age", "abc").status_code == 422 and try_("religion", "x").status_code == 422
    au = try_("age", "58", "auditor").json()
    assert au["diff"][0]["before"] is None and au["diff"][0]["after"] == 58
    assert "reference_rules" not in client.get(f"/api/runs/{rid}", headers=H("auditor")).json()["values"]["bias_audit"]["baseline"]
