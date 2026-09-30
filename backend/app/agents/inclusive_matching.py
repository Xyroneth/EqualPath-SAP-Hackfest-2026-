"""Inclusive Matching Agent: a transparent mutual-fit assessment shown as components, not one score.

Accessibility and schedule needs are candidate-controlled constraints. When the employer has not stated
how it meets them, the item is marked "unconfirmed - employer action", never counted against the candidate.
"""
from __future__ import annotations

from app.agents.common import EVIDENCE_WEIGHT
from app.agents.market_intelligence import conditions_fit


def assess_match(role: dict, features: dict, pathway: dict, employer_scan: dict, shared_accommodations: list[str]) -> dict:
    gaps = pathway["gaps"]
    essential = [g for g in gaps if g["importance"] == "essential"]
    counts = {s: sum(1 for g in essential if g["status"] == s) for s in ("verified", "developing", "missing")}
    with_ev = [g for g in essential if g["evidence"]]
    evidence = round(sum(EVIDENCE_WEIGHT[g["evidence"]["verification_status"]] for g in with_ev) / len(with_ev), 2) if with_ev else 0.0
    base = conditions_fit(role, features)["items"]
    categories = {f["category"] for f in employer_scan["flags"]}
    claims = {c["claim_id"]: c for c in employer_scan["claims"]}

    def employer_state(flag_category: str, claim_id: str | None) -> tuple[str, dict]:
        if flag_category not in categories:
            return "fit", {"code": "stated"}
        claim = claims.get(claim_id) if claim_id else None
        if claim:
            return "unconfirmed", {"code": "employer_says", "answer": claim["answer"], "level": claim["evidence_level"]}
        return "unconfirmed", {"code": "not_stated"}

    def english(note: dict) -> str:
        if note["code"] == "stated":
            return "Stated in the job description."
        if note["code"] == "employer_says":
            return f"Not stated in the job description. Employer questionnaire: \"{note['answer']}\" ({note['level'].replace('_', ' ')})."
        return "Not stated in the job description."

    wm_state, wm_note = employer_state("unclear_work_conditions", "work_mode")
    int_state, int_note = employer_state("missing_accessible_interview_info", "accessible_interviews")
    acc_state, acc_note = employer_state("missing_accommodation_process", "accommodation_process")
    conditions = [
        {"key": "work_mode", "condition": "Work mode", "candidate": ", ".join(features["work_modes"]), "candidate_list": features["work_modes"], "role_list": role["work_modes"],
         "status": "fit" if base["work_mode"]["fit"] and wm_state == "fit" else ("conflict" if not base["work_mode"]["fit"] else "unconfirmed"),
         "detail": base["work_mode"]["detail"] + ". " + english(wm_note), "note": wm_note, "responsible": "Employer" if wm_state != "fit" else None},
        {"key": "location", "condition": "Location", "candidate": features["commute_city"].title(), "candidate_list": [features["commute_city"].title()], "role_list": role["locations"],
         "status": "fit" if base["location"]["fit"] else "conflict", "detail": base["location"]["detail"], "note": {"code": "stated"}, "responsible": None},
        {"key": "language", "condition": "Language", "candidate": ", ".join(features["languages"]), "candidate_list": features["languages"], "role_list": role["languages_required"],
         "status": "fit" if base["language"]["fit"] else "conflict", "detail": base["language"]["detail"], "note": {"code": "stated"}, "responsible": None},
        {"key": "schedule", "condition": "Interview schedule", "candidate": features["schedule_needs"], "candidate_list": [], "role_list": [],
         "status": int_state, "detail": english(int_note), "note": int_note, "responsible": "Employer" if int_state != "fit" else None},
        {"key": "accommodations", "condition": "Work accommodations (candidate-approved)", "candidate": "; ".join(shared_accommodations) or "None shared",
         "candidate_list": shared_accommodations, "role_list": [], "status": acc_state if shared_accommodations else "fit",
         "detail": english(acc_note) if shared_accommodations else "No accommodation shared by the candidate.",
         "note": acc_note if shared_accommodations else {"code": "none_shared"}, "responsible": "Employer" if shared_accommodations and acc_state != "fit" else None},
    ]
    weeks = pathway.get("estimated_weeks")
    feasibility = "high" if weeks is not None and weeks <= 4 else "medium" if weeks is not None and weeks <= 8 else "low"
    return {
        "role_id": role["role_id"],
        "components": {
            "capability_coverage": {"verified": counts["verified"], "developing": counts["developing"], "missing": counts["missing"], "total_essential": len(essential),
                                    "explanation": f"{counts['verified']} of {len(essential)} essential capabilities are verified with evidence."},
            "evidence_strength": {"value": evidence, "explanation": "Average evidence weight of matched capabilities: self-declared 0.25, source-supported 0.70, assessed 0.90, externally verified 1.00."},
            "work_conditions": conditions,
            "gap_feasibility": {"level": feasibility, "hours": pathway["total_hours"], "weeks": weeks, "weekly_hours": pathway["weekly_hours"],
                                "explanation": f"{pathway['total_hours']:g} hours of milestones at {pathway['weekly_hours']:g} h/week in short evening sessions = about {weeks} weeks."},
        },
        "not_used_as_features": ["gender", "age", "disability", "name", "college prestige", "career-break duration"],
        "employer_actions": [c for c in conditions if c["responsible"] == "Employer"],
    }
