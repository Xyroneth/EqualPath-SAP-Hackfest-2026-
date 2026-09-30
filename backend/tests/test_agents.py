"""Unit tests for the agents and their guardrails."""
from app.agents.bias_audit import run_bias_audit
from app.agents.common import employer_for, improved_job_for, job_by_id, role_by_id, roles
from app.agents.employer_readiness import CATEGORY_LABELS, assess_employer
from app.agents.learning_pathway import build_pathway
from app.agents.market_intelligence import rank_roles
from app.agents.skills_discovery import discover_skills, locate_quote
from app.privacy import MATCHING_FEATURE_ALLOWLIST, minimise_profile_for_matching, redact
from app.providers.learning_catalog import get_learning_catalog
from app.providers.llm import DemoProvider, LLMProvider, ProviderInfo
from app.schemas import EvidenceDocument, SkillRecord
from app.seed import seed_documents


def _seed_dicts():
    return [{k: d[k] for k in ("source_id", "title", "evidence_type", "date", "text")} for d in seed_documents()]


def _docs(persona):
    return [EvidenceDocument(**d) for d in _seed_dicts()]


def _skills(persona):
    return discover_skills(_docs(persona), DemoProvider(), ["Priya Sharma"])["skills"]


class FakeLLM(LLMProvider):
    """Simulates a configured LLM, including a dishonest record that tries to inflate verification."""

    kind = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def info(self):
        return ProviderInfo("fake", "Fake LLM", "fake-1", True, "test double")

    def complete_json(self, system, user):
        self.calls.append(user)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


GOOD_LLM_RESPONSE = {"skills": [
    {"skill_name": "Manual software testing", "normalized_skill": "software_testing.manual", "category": "technical", "proficiency": "intermediate",
     "evidence_quote": "Created and executed 42 regression test cases", "source_id": "test-cases.pdf", "confidence": 0.9, "adjacent_skills": []},
    {"skill_name": "Browser test automation", "normalized_skill": "test_automation.browser", "category": "technical", "proficiency": "advanced",
     "evidence_quote": "Proficient in Selenium WebDriver automation", "source_id": "resume.pdf", "confidence": 0.97,
     "verification_status": "externally_verified", "adjacent_skills": []},
    {"skill_name": "Kubernetes", "normalized_skill": "other.kubernetes", "category": "technical", "proficiency": "advanced",
     "evidence_quote": "Managed Kubernetes clusters in production", "source_id": "resume.pdf", "confidence": 0.8, "adjacent_skills": []},
]}


def test_every_skill_has_a_verbatim_quote_and_valid_schema(persona):
    docs = {d.source_id: d.text for d in _docs(persona)}
    for s in _skills(persona):
        SkillRecord.model_validate(s)
        assert locate_quote(s["evidence_quote"], redact(docs[s["source_id"]], ["Priya Sharma"]).text)


def test_unsupported_resume_claims_remain_self_declared(persona):
    skills = {s["normalized_skill"]: s for s in _skills(persona)}
    assert skills["test_automation.browser"]["verification_status"] == "self_declared"
    assert skills["data.sql"]["verification_status"] == "self_declared"
    assert skills["software_testing.manual"]["verification_status"] == "source_supported"


def test_llm_output_is_validated_and_cannot_upgrade_verification(persona):
    llm = FakeLLM([GOOD_LLM_RESPONSE])
    r = discover_skills(_docs(persona), llm, ["Priya Sharma"])
    skills = {s["normalized_skill"]: s for s in r["skills"]}
    assert r["method"] == "llm:fake"
    assert skills["test_automation.browser"]["verification_status"] == "self_declared"
    assert any("blocked" in n for n in skills["test_automation.browser"]["notes"])
    assert "other.kubernetes" not in skills  # quote not in any source -> rejected
    assert any("not found" in x["reason"] for x in r["rejected"])
    assert "Priya" not in llm.calls[0] and "98765" not in llm.calls[0]  # PII redacted before the call


def test_llm_retry_then_deterministic_fallback(persona):
    llm = FakeLLM([{"not": "valid"}, {"skills": "nope"}])
    r = discover_skills(_docs(persona), llm, ["Priya Sharma"])
    assert r["method"] == "deterministic" and r["fallback_reason"] and len(llm.calls) == 2


def test_redaction_removes_direct_identifiers():
    r = redact("Priya Sharma, priya.sharma.qa@example.com, +91 98765 43210, github.com/priya-sharma-demo", ["Priya Sharma"])
    assert "Priya" not in r.text and "example.com" not in r.text and "98765" not in r.text and "github.com/priya" not in r.text


def test_market_intelligence_recommends_qa_automation(persona):
    ranking = rank_roles(_skills(persona), minimise_profile_for_matching(persona["profile"]))
    assert ranking["recommended_role_id"] == "qa-automation-associate"
    assert len(ranking["top_roles"]) == 3
    assert set(ranking["top_roles"][0]["components"]) == {"capability_coverage", "evidence_strength", "work_condition_fit", "entry_realism", "gap_feasibility"}


def test_matching_features_exclude_protected_attributes(persona):
    f = minimise_profile_for_matching(persona["profile"])
    assert set(f) <= MATCHING_FEATURE_ALLOWLIST
    for attr in ("gender", "age", "display_name", "career_break", "disability"):
        assert attr not in f


def test_career_break_and_protected_attributes_do_not_reduce_score(persona):
    skills = _skills(persona)
    base = rank_roles(skills, minimise_profile_for_matching(persona["profile"]))
    for change in ({"career_break": {"months": 180}}, {"career_break": {"months": 0}}, {"gender": "male"}, {"age": 58}, {"display_name": "X"}):
        other = rank_roles(skills, minimise_profile_for_matching({**persona["profile"], **change}))
        assert [r["total"] for r in other["top_roles"]] == [r["total"] for r in base["top_roles"]]


def test_bias_audit_passes_and_states_limitations(persona):
    b = run_bias_audit(persona["profile"], _seed_dicts(), _skills(persona), "qa-automation-associate")
    assert b["passed"] and b["feature_audit"]["passed"]
    assert len(b["counterfactuals"]) >= 6
    assert any(c["extraction_rechecked"] for c in b["counterfactuals"]), "career-break / name wording must actually change the document text"
    for c in b["counterfactuals"]:
        assert c["selected_score_before"] == c["selected_score_after"] and c["diff"] and all(d["before"] != d["after"] for d in c["diff"])
    # Control test: the same twins catch a deliberately biased reference filter, so the test is able to detect bias.
    assert b["reference_filter"]["flagged"] >= 3
    assert {"break_none", "age_older", "college"} <= set(b["reference_filter"]["flagged_ids"])
    assert b["baseline"]["ranking"][0]["score"] > 0
    assert any("not statistical proof" in l for l in b["limitations"])


def test_learning_pathway_has_gap_statuses_sap_asset_and_evidence_tasks(persona):
    pw = build_pathway(_skills(persona), role_by_id("qa-automation-associate"), get_learning_catalog(), DemoProvider(), 6)
    assert pw["counts"]["verified"] > 0 and pw["counts"]["developing"] > 0 and pw["counts"]["missing"] > 0
    assert pw["sap_assets_used"], "at least one SAP Learning asset"
    for m in pw["milestones"]:
        assert m["required_evidence"] and m["practice_task"] and m["completion_rule"] == "Human reviewer accepts the submitted evidence"
        assert get_learning_catalog().get(m["learning_asset_id"]) is not None


def test_employer_readiness_identifies_all_seeded_barriers():
    job = job_by_id("northstar-qa-automation-v1")
    scan = assess_employer(job, employer_for(job))
    flagged = {f["category"] for f in scan["flags"]}
    assert flagged == set(CATEGORY_LABELS) - {"age_requirement", "gender_or_family_requirement", "physical_requirement"}
    assert any("uninterrupted" in (f["text"] or "") for f in scan["flags"])
    assert any(f.get("aspect") == "work_mode" for f in scan["flags"])
    claims = {c["claim_id"]: c for c in scan["claims"]}
    assert claims["career_breaks"]["evidence_level"] == "conflicting_evidence" and claims["career_breaks"]["requires_human_review"]
    assert claims["accessible_interviews"]["evidence_level"] == "experience_validated"
    assert claims["return_to_work"]["evidence_level"] == "document_verified"
    assert claims["accommodation_process"]["evidence_level"] == "declared"
    assert scan["suggested_rewrite"]["status"] == "pending_hr_approval"


def test_every_role_has_an_employer_ad_whose_improved_version_and_rewrite_scan_clean():
    for role in roles():
        original = job_by_id(role["job_ids"][0])
        improved = improved_job_for(original)
        employer = employer_for(original)
        scan = assess_employer(original, employer)
        assert original["version"] == "original" and improved and improved["employer_id"] == original["employer_id"]
        assert len(scan["flags"]) >= 2, role["role_id"]
        assert len(scan["claims"]) == 5 and scan["facts"]["requirements"], role["role_id"]
        assert assess_employer(improved, employer)["flags"] == [], improved["job_id"]
        rewrite = scan["suggested_rewrite"]
        assert rewrite["changes"] and assess_employer({**original, "text": rewrite["text"]}, employer)["flags"] == [], role["role_id"]


def test_new_barrier_types_are_found_and_removed_by_the_rewrite():
    job = job_by_id("kaveri-test-analyst-v1")
    scan = assess_employer(job, employer_for(job))
    cats = {f["category"] for f in scan["flags"]}
    assert {"age_requirement", "gender_or_family_requirement", "career_gap_requirement", "missing_accessible_interview_info"} <= cats
    removed = [c for c in scan["suggested_rewrite"]["changes"] if c["kind"] == "removed"]
    assert {c["categories"][0] for c in removed} == {"age_requirement", "gender_or_family_requirement"}
    claims = {c["claim_id"]: c for c in scan["claims"]}
    assert claims["accessible_interviews"]["evidence_level"] == "conflicting_evidence"  # "walk-in only, no rescheduling" vs "you can ask for another slot"
    assert claims["work_mode"]["evidence_level"] == "document_verified"  # an honest onsite claim is not a conflict
    assert claims["return_to_work"]["not_offered"] and claims["return_to_work"]["evidence_level"] == "declared"
    indus = job_by_id("indus-data-quality-v1")
    assert "physical_requirement" in {f["category"] for f in assess_employer(indus, employer_for(indus))["flags"]}
    gomti = job_by_id("gomti-app-support-v1")
    g = {c["claim_id"]: c for c in assess_employer(gomti, employer_for(gomti))["claims"]}
    assert g["career_breaks"]["evidence_level"] == "experience_validated"
