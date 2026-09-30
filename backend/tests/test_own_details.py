"""The app is not tied to the sample persona: anyone can enter their own (or another person's) details and evidence."""
import pytest
from conftest import H, wait

from app.agents.common import roles

ARJUN = {
    "display_name": "Arjun Mehta", "age": 44, "gender": "male", "location_city": "Pune", "location_state": "Maharashtra",
    "languages": ["marathi", "hindi", "english"], "relevant_experience_years": 2, "college": "NIT Nagpur", "goal": "A frontend developer role",
    "work_conditions": {"work_modes": ["hybrid", "remote"], "can_relocate": False, "weekly_learning_hours": 8},
    "accommodations": {"shareable_work_accommodations": ["Interviews after 17:00"], "private_note": "Looking after a parent in the mornings."},
}
RESUME = ("Arjun Mehta, Pune. arjun.mehta@example.com. Frontend developer with 2 years of experience. "
          "Built responsive web pages with HTML, CSS and JavaScript. Used Git and GitHub for version control in an agile team. Basic SQL with MySQL. "
          "Fluent in Marathi, Hindi and English. B.Tech, NIT Nagpur.")
PROJECT = ("Food ordering app. Arjun built the cart page as React components with unit tests in Jest. "
           "He fixed 14 bugs reported by users and wrote steps to reproduce for each. The order export was checked in Excel with a pivot table.")
CONSENT = {"process_profile": True, "share_with_employer": True, "share_accommodations": True}


def own_candidate(client, profile=ARJUN):
    r = client.post("/api/candidates", json={"profile": profile, "consent": CONSENT})
    assert r.status_code == 200, r.text
    cid = r.json()["candidate_id"]
    for title, kind, text in [("My resume", "resume", RESUME), ("Food ordering project", "project", PROJECT)]:
        assert client.post(f"/api/candidates/{cid}/documents/text", json={"title": title, "evidence_type": kind, "text": text}).status_code == 200
    return cid


def test_blank_profile_and_validation(client):
    blank = client.get("/api/profile/blank").json()["profile"]
    assert blank["display_name"] == "" and blank["work_conditions"]["work_modes"] == [] and blank["career_break"]["months"] == 0
    bad = lambda patch: client.post("/api/candidates", json={"profile": {**ARJUN, **patch}, "consent": CONSENT})
    assert bad({"display_name": ""}).status_code == 422
    assert bad({"location_city": " "}).status_code == 422
    assert bad({"age": 140}).status_code == 422
    assert bad({"languages": []}).status_code == 422
    assert "work mode" in bad({"work_conditions": {"work_modes": []}}).json()["detail"]


def test_own_details_start_without_sample_documents_and_are_normalised(client):
    cid = client.post("/api/candidates", json={"profile": ARJUN, "consent": CONSENT}).json()["candidate_id"]
    c = client.get(f"/api/candidates/{cid}").json()
    assert c["documents"] == []  # nothing of the sample persona is loaded
    p = c["profile"]
    assert p["languages"] == ["Marathi", "Hindi", "English"] and p["location_wording"] == "Pune, Maharashtra"
    assert p["work_conditions"]["commute_city"] == "Pune" and p["career_break"] == {"months": 0, "reason": None, "wording": ""}
    assert p["accommodations"]["private_note"] == "Looking after a parent in the mornings."  # returned to the candidate only
    assert client.post("/api/runs", json={"candidate_id": cid}).status_code == 422  # evidence is needed first


@pytest.mark.parametrize("role_id", [r["role_id"] for r in roles()])
def test_another_person_goes_through_the_whole_journey_for_every_role(client, role_id):
    cid = own_candidate(client)
    rid = client.post("/api/runs", json={"candidate_id": cid}).json()["run_id"]
    v = wait(client, rid)
    found = {s["normalized_skill"]: s for s in v["values"]["discovery"]["skills"]}
    assert {"frontend.react", "programming.javascript", "version_control.git", "data.spreadsheet_analysis"} <= set(found)
    assert found["frontend.react"]["verification_status"] == "source_supported"      # shown in a project
    assert found["programming.javascript"]["verification_status"] == "self_declared"  # only claimed in the resume
    assert all("Arjun" not in s["evidence_quote"] for s in found.values())            # name redacted before extraction
    added = [{"skill_name": "Python", "normalized_skill": "python", "evidence_quote": "Wrote small scripts at work", "proficiency": "basic"}]
    assert client.post(f"/api/runs/{rid}/candidate-review", json={"decisions": [], "added_skills": added}).status_code == 200
    v = wait(client, rid)
    assert any(s["normalized_skill"] == "programming.python" and s["verification_status"] == "self_declared" for s in v["values"]["skills"])
    assert client.post(f"/api/runs/{rid}/role-selection", json={"role_id": role_id}).status_code == 200
    v = wait(client, rid)
    assert v["interrupt"]["checkpoint"] == "final_review", v["run"]
    vals = v["values"]
    # every gap that is not yet proven gets a concrete learning step with a real resource
    open_essential = [g for g in vals["pathway"]["gaps"] if g["importance"] == "essential" and g["status"] != "verified"]
    planned = {m["capability"] for m in vals["pathway"]["milestones"]}
    assert {g["capability"] for g in open_essential} <= planned, role_id
    assert all(m["learning_asset_url"].startswith("https://") for m in vals["pathway"]["milestones"])
    assert vals["employer_scan"]["role_id"] == role_id and vals["employer_scan"]["flags"]
    # the fairness twins are built from THIS person, not from the sample persona
    twins = {t["id"]: t for t in vals["bias_audit"]["counterfactuals"]}
    assert vals["bias_audit"]["passed"] and "woman" in twins and "man" not in twins and "break_added" in twins
    assert twins["woman"]["diff"][0] == {"field": "name", "before": "Arjun Mehta", "after": "Priya Sharma"}
    assert twins["college"]["diff"][0]["after"] == "A state university" and twins["college"]["reference"]["delta"] == -10
    assert all(t["selected_score_before"] == t["selected_score_after"] for t in twins.values())
    client.post(f"/api/runs/{rid}/final-review", headers=H("counsellor"), json={"decision": "approve"})
    wait(client, rid)
    p = client.get(f"/api/runs/{rid}/passport").json()
    assert p["candidate_display_name"] == "Arjun Mehta" and p["outcomes"]
    assert "Looking after a parent" not in str(p)  # the private note never leaves the profile


def test_someone_with_no_catalog_skills_still_gets_a_full_honest_result(client):
    chef = {**ARJUN, "display_name": "Meera Nair", "gender": None, "age": None, "college": None, "languages": ["Malayalam", "English"]}
    cid = client.post("/api/candidates", json={"profile": chef, "consent": CONSENT}).json()["candidate_id"]
    text = "Meera Nair worked as a line cook for five years and ran the evening kitchen shift for a busy restaurant."
    client.post(f"/api/candidates/{cid}/documents/text", json={"title": "My work", "evidence_type": "resume", "text": text})
    rid = client.post("/api/runs", json={"candidate_id": cid}).json()["run_id"]
    v = wait(client, rid)
    assert v["values"]["discovery"]["skills"] == []  # nothing is invented
    client.post(f"/api/runs/{rid}/candidate-review", json={"decisions": []})
    v = wait(client, rid)
    role_id = v["values"]["ranking"]["top_roles"][0]["role_id"]
    client.post(f"/api/runs/{rid}/role-selection", json={"role_id": role_id})
    v = wait(client, rid)
    assert v["interrupt"]["checkpoint"] == "final_review"
    pw = v["values"]["pathway"]
    assert pw["counts"]["verified"] == 0 and pw["milestones"], "every missing skill still gets a learning step"
    twins = {t["id"]: t for t in v["values"]["bias_audit"]["counterfactuals"]}
    assert twins["age_young"]["diff"][0]["before"] is None and v["values"]["bias_audit"]["passed"]
