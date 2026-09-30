"""Learning Pathway Agent - functional supporting agent.

1. Deterministically classifies every role requirement as verified / developing / missing (auditable rules).
2. For each developing or missing capability, creates the smallest useful evidence-building milestone.
   With a live LLM the milestone wording is drafted by the model, then validated: the learning asset must
   come from the curated catalog for that capability, effort is bounded, evidence is required and the
   completion rule is always a human review.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.common import active_skills, capability_name, is_evidence_backed, level_meets, taxonomy
from app.providers.learning_catalog import LearningCatalogProvider
from app.providers.llm import DemoProvider, LLMError, LLMProvider
from app.schemas import LLMPathwayResponse, Milestone

COMPLETION_RULE = "Human reviewer accepts the submitted evidence"

# Deterministic milestone templates: small, practical, evidence-producing.
TEMPLATES: dict[str, dict] = {
    "test_automation.browser": {
        "preferred_assets": ["ext-selenium-getting-started", "ext-playwright-python"],
        "estimated_hours": 6,
        "practice_task": "Automate the login and form-validation checks of the EQUALPATH practice application (/practice) with Selenium WebDriver or Playwright and pytest: one passing login, one wrong-password case and two field-validation cases.",
        "required_evidence": ["test script (file or repository link)", "execution screenshot or pytest report", "short reflection (5-8 sentences)"],
        "why_it_matters": "The role automates regression tests. Priya already writes pytest unit tests and designs strong manual test cases; this milestone turns her self-declared Selenium claim into reviewable evidence.",
        "why_it_matters_hi": "यह भूमिका रिग्रेशन टेस्ट को ऑटोमेट करती है। यह माइलस्टोन प्रिया के Selenium दावे को समीक्षा-योग्य प्रमाण में बदलता है।",
    },
    "api_testing": {
        "preferred_assets": ["ext-postman-api-testing"],
        "estimated_hours": 4,
        "practice_task": "Write five API tests for the EQUALPATH practice API (GET /api/practice/orders and POST /api/practice/orders): status codes, one JSON field check, and two negative cases (missing field, invalid quantity).",
        "required_evidence": ["exported test collection or pytest file", "test run result screenshot", "short reflection"],
        "why_it_matters": "Enterprise applications are tested through their APIs as well as their screens. The job description lists REST API testing.",
        "why_it_matters_hi": "एंटरप्राइज़ एप्लिकेशन की जाँच API के माध्यम से भी होती है। जॉब विवरण में REST API टेस्टिंग शामिल है।",
    },
    "enterprise_apps.sap_context": {
        "preferred_assets": ["sap-build-develop-automate", "sap-btp-exploring", "sap-cloud-alm-intro"],
        "estimated_hours": 4,
        "practice_task": "Study the introductory units, then write eight test scenarios (happy path, rejection, missing mandatory field, wrong approver role, and four boundary cases) for a simple approval process built with SAP Build Process Automation, with expected results.",
        "required_evidence": ["test scenario sheet", "screenshot of the SAP Learning unit or tutorial step reached", "short reflection on how enterprise workflows are tested"],
        "why_it_matters": "The role supports enterprise business applications. Basic SAP BTP / SAP Build context lets Priya test business workflows, not only web pages.",
        "why_it_matters_hi": "यह भूमिका एंटरप्राइज़ बिज़नेस एप्लिकेशन से जुड़ी है। SAP BTP / SAP Build की बुनियादी समझ से प्रिया बिज़नेस वर्कफ़्लो की भी जाँच कर पाएगी।",
    },
    "data.sql": {
        "preferred_assets": ["sap-hana-cloud-jumpstart"],
        "estimated_hours": 3,
        "practice_task": "Write six SQL queries that validate test data (row counts, duplicates, missing values, joins) against a sample table in the SAP HANA Cloud trial or any SQL sandbox.",
        "required_evidence": ["SQL file", "query result screenshot"],
        "why_it_matters": "Test data validation is a common part of QA and support roles.",
        "why_it_matters_hi": "टेस्ट डेटा की जाँच QA और सपोर्ट भूमिकाओं का सामान्य हिस्सा है।",
    },
}

GENERIC_TEMPLATE = {
    "estimated_hours": 4,
    "practice_task": "Complete the recommended learning asset and produce one small work sample that demonstrates the capability.",
    "required_evidence": ["work sample", "short reflection"],
    "why_it_matters": "This capability is listed as essential for the target role.",
    "why_it_matters_hi": "यह क्षमता लक्षित भूमिका के लिए आवश्यक है।",
}

SYSTEM_PROMPT = """You are the Learning Pathway Agent of EQUALPATH. For each capability gap, draft the SMALLEST useful
milestone that produces reviewable evidence. The candidate learns in short evening sessions ({weekly} hours/week)
and prefers practical tasks. Use ONLY a learning_asset_id from the allowed list given for that gap.
Return JSON only: {{"milestones":[{{"capability":str,"learning_asset_id":str,"estimated_hours":number,
"practice_task":str,"required_evidence":[str],"why_it_matters":str}}]}}"""


def classify_gaps(skills: list[dict], role: dict) -> list[dict]:
    """verified: level met AND evidence-backed; developing: claimed, lower level, or adjacent skill; missing: none."""
    profile = {s["normalized_skill"]: s for s in active_skills(skills)}
    have_names = {s["skill_name"].lower() for s in profile.values()} | {k.split(".")[-1].replace("_", " ") for k in profile}
    gaps = []
    for req in role["requirements"]:
        cap, need = req["capability"], req["level"]
        s = profile.get(cap)
        evidence = None
        if s:
            evidence = {k: s.get(k) for k in ("skill_name", "verification_status", "proficiency", "source_id", "evidence_quote", "evidence_type")}
        params: dict = {}
        if s and is_evidence_backed(s["verification_status"]) and level_meets(s["proficiency"], need):
            status, code, params = "verified", "met", {"need": need, "have": s["proficiency"], "status": s["verification_status"]}
            reason = f"Required {need}; evidence shows {s['proficiency']} ({s['verification_status'].replace('_', ' ')})."
        elif s and not is_evidence_backed(s["verification_status"]):
            status, code, params = "developing", "unsupported", {"source": s["source_id"]}
            reason = f"Claimed in {s['source_id']} but not yet supported by a work sample or assessment."
        elif s:
            status, code, params = "developing", "lower", {"need": need, "have": s["proficiency"]}
            reason = f"Evidence shows {s['proficiency']}; role needs {need}."
        else:
            adj = [a for a in taxonomy().get(cap, {}).get("adjacent_skills", []) if a.lower() in have_names]
            if adj:
                status, code, params = "developing", "adjacent", {"adjacent": adj}
                reason = f"No direct evidence, but adjacent capability present: {', '.join(adj)}."
            else:
                status, code = "missing", "none"
                reason = "No capability or evidence found yet."
        gaps.append({
            "capability": cap, "capability_name": capability_name(cap), "required_level": need,
            "importance": req["importance"], "status": status, "reason": reason, "reason_code": code, "reason_params": params, "evidence": evidence,
        })
    return gaps


def _template_milestone(idx: int, gap: dict, catalog: LearningCatalogProvider) -> Milestone | None:
    t = TEMPLATES.get(gap["capability"], GENERIC_TEMPLATE)
    asset = None
    for aid in t.get("preferred_assets", []):
        asset = catalog.get(aid)
        if asset:
            break
    if asset is None:
        options = catalog.for_capability(gap["capability"])
        asset = options[0] if options else None
    if asset is None:
        return None
    return Milestone(
        milestone_id=f"ms-{idx}", gap=gap["capability_name"], capability=gap["capability"], status=gap["status"],
        learning_asset_id=asset["asset_id"], learning_asset_title=asset["title"], learning_asset_url=asset["url"],
        learning_asset_provider=asset["provider"], estimated_hours=t["estimated_hours"], practice_task=t["practice_task"],
        required_evidence=t["required_evidence"], completion_rule=COMPLETION_RULE, why_it_matters=t["why_it_matters"],
        importance=gap["importance"], generated_by="deterministic template",
    )


def _llm_milestones(provider: LLMProvider, gaps: list[dict], catalog: LearningCatalogProvider, weekly_hours: float) -> dict[str, dict]:
    allowed = {g["capability"]: [{"learning_asset_id": a["asset_id"], "title": a["title"], "provider": a["provider"]}
                                 for a in catalog.for_capability(g["capability"])] for g in gaps}
    payload = json.dumps({"gaps": [{"capability": g["capability"], "name": g["capability_name"], "status": g["status"],
                                    "required_level": g["required_level"], "reason": g["reason"],
                                    "allowed_assets": allowed[g["capability"]]} for g in gaps]}, ensure_ascii=False)
    raw = provider.complete_json(SYSTEM_PROMPT.format(weekly=weekly_hours), payload)
    parsed = LLMPathwayResponse.model_validate(raw)
    out = {}
    for d in parsed.milestones:
        ids = {a["learning_asset_id"] for a in allowed.get(d.capability, [])}
        if d.learning_asset_id in ids and 1 <= d.estimated_hours <= 20 and d.required_evidence and len(d.practice_task) > 10:
            out[d.capability] = d.model_dump()
    return out


def build_pathway(skills: list[dict], role: dict, catalog: LearningCatalogProvider, provider: LLMProvider,
                  weekly_hours: float = 6) -> dict[str, Any]:
    gaps = classify_gaps(skills, role)
    open_gaps = [g for g in gaps if g["status"] != "verified" and (g["importance"] == "essential" or g["capability"] in TEMPLATES)]
    method, fallback_reason, llm_drafts = "deterministic", None, {}
    if not isinstance(provider, DemoProvider) and provider.is_live and open_gaps:
        try:
            llm_drafts = _llm_milestones(provider, open_gaps, catalog, weekly_hours)
            method = f"llm:{provider.info().kind}"
        except (LLMError, ValidationError) as exc:
            fallback_reason = f"LLM pathway draft rejected ({str(exc)[:140]}); deterministic templates used."
    milestones: list[Milestone] = []
    for i, gap in enumerate(open_gaps, start=1):
        base = _template_milestone(i, gap, catalog)
        if base is None:
            continue
        d = llm_drafts.get(gap["capability"])
        if d:
            asset = catalog.get(d["learning_asset_id"])
            base = base.model_copy(update={
                "learning_asset_id": asset["asset_id"], "learning_asset_title": asset["title"], "learning_asset_url": asset["url"],
                "learning_asset_provider": asset["provider"], "estimated_hours": d["estimated_hours"],
                "practice_task": d["practice_task"], "required_evidence": d["required_evidence"],
                "why_it_matters": d["why_it_matters"], "generated_by": method,
            })
        milestones.append(base)
    ms = [m.model_dump() | {"why_it_matters_hi": TEMPLATES.get(m.capability, GENERIC_TEMPLATE)["why_it_matters_hi"]} for m in milestones]
    total = sum(m["estimated_hours"] for m in ms if m["importance"] == "essential")
    return {
        "role_id": role["role_id"], "gaps": gaps, "milestones": ms, "method": method, "fallback_reason": fallback_reason,
        "total_hours": total, "weekly_hours": weekly_hours,
        "estimated_weeks": round(total / weekly_hours, 1) if weekly_hours else None,
        "counts": {s: sum(1 for g in gaps if g["status"] == s) for s in ("verified", "developing", "missing")},
        "sap_assets_used": sorted({m["learning_asset_id"] for m in ms if m["learning_asset_provider"].startswith("SAP")}),
    }
