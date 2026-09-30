"""Market Intelligence Agent: ranks roles from the local, clearly labelled role catalog.

Only allow-listed matching features are used (see privacy.MATCHING_FEATURE_ALLOWLIST). Protected
attributes and career-break duration are not inputs, so they contribute exactly zero points.
"""
from __future__ import annotations

from app.agents.common import EVIDENCE_WEIGHT, roles
from app.agents.learning_pathway import classify_gaps
from app.privacy import MATCHING_FEATURE_ALLOWLIST

WEIGHTS = {"capability_coverage": 0.35, "evidence_strength": 0.15, "work_condition_fit": 0.25, "entry_realism": 0.10, "gap_feasibility": 0.15}
PRE_PATHWAY_HOURS = {"developing": 5, "missing": 8}  # rough effort before a pathway exists


def conditions_fit(role: dict, features: dict) -> dict:
    modes = set(role["work_modes"])
    cand_modes = set(features["work_modes"])
    mode_ok = bool(modes & cand_modes)
    remote_ok = "remote" in modes and "remote" in cand_modes
    locs = {l.lower() for l in role["locations"]}
    loc_ok = remote_ok or features["commute_city"] in locs or features["can_relocate"]
    lang_ok = all(l in features["languages"] for l in role["languages_required"])
    items = {
        "work_mode": {"fit": mode_ok, "detail": f"Role: {', '.join(role['work_modes'])}; candidate: {', '.join(features['work_modes'])}"},
        "location": {"fit": loc_ok, "detail": f"Role: {', '.join(role['locations'])}; candidate city: {features['commute_city'].title()}, relocation {'possible' if features['can_relocate'] else 'not possible now'}"},
        "language": {"fit": lang_ok, "detail": f"Required: {', '.join(role['languages_required'])}"},
    }
    return {"score": round(sum(1 for v in items.values() if v["fit"]) / len(items), 3), "items": items}


def score_role(role: dict, skills: list[dict], features: dict) -> dict:
    assert set(features) <= MATCHING_FEATURE_ALLOWLIST, "non-allow-listed feature passed to matching"
    gaps = classify_gaps(skills, role)
    essential = [g for g in gaps if g["importance"] == "essential"]
    credit = {"verified": 1.0, "developing": 0.5, "missing": 0.0}
    coverage = sum(credit[g["status"]] for g in essential) / len(essential) if essential else 0.0
    with_ev = [g for g in essential if g["evidence"]]
    evidence = sum(EVIDENCE_WEIGHT[g["evidence"]["verification_status"]] for g in with_ev) / len(with_ev) if with_ev else 0.0
    cond = conditions_fit(role, features)
    entry = min(1.0, features["relevant_experience_years"] / role["min_relevant_experience_years"]) if role["min_relevant_experience_years"] else 1.0
    hours = sum(PRE_PATHWAY_HOURS.get(g["status"], 0) for g in essential)
    weeks = hours / max(features["weekly_learning_hours"], 1)
    feasibility = 1.0 if weeks <= 4 else 0.75 if weeks <= 8 else 0.5 if weeks <= 12 else 0.25
    components = {
        "capability_coverage": round(coverage, 3),
        "evidence_strength": round(evidence, 3),
        "work_condition_fit": cond["score"],
        "entry_realism": round(entry, 3),
        "gap_feasibility": feasibility,
    }
    total = round(sum(WEIGHTS[k] * v for k, v in components.items()), 3)
    counts = {s: sum(1 for g in essential if g["status"] == s) for s in ("verified", "developing", "missing")}
    reasons = [
        f"{counts['verified']} of {len(essential)} essential capabilities verified with evidence, {counts['developing']} developing, {counts['missing']} missing.",
        "Work conditions: " + "; ".join(f"{k.replace('_', ' ')} {'fits' if v['fit'] else 'conflicts'}" for k, v in cond["items"].items()) + ".",
        f"Estimated {hours} learning hours to close gaps (~{weeks:.1f} weeks at {features['weekly_learning_hours']:g} h/week).",
    ]
    return {
        "role_id": role["role_id"], "title": role["title"], "summary": role["summary"], "total": total,
        "components": components, "weights": WEIGHTS, "conditions": cond["items"], "gap_counts": counts, "hours": hours, "weeks": round(weeks, 1),
        "work_modes": role["work_modes"], "locations": role["locations"],
        "reasons": reasons, "demand_signal": role["demand_signal"], "demand_note": role["demand_note"],
        "has_seeded_job": bool(role["job_ids"]),
    }


def rank_roles(skills: list[dict], features: dict, top_n: int = 3) -> dict:
    scored = sorted((score_role(r, skills, features) for r in roles()), key=lambda s: s["total"], reverse=True)
    for i, s in enumerate(scored, 1):
        s["rank"] = i
    top = scored[:top_n]
    rec = top[0]
    explanation = (
        f"{rec['title']} is recommended: it has the best combined fit. "
        + " ".join(rec["reasons"])
        + " Protected attributes and career-break duration are not inputs to this ranking."
    )
    return {"top_roles": top, "other_roles": scored[top_n:], "recommended_role_id": rec["role_id"], "explanation": explanation,
            "features_used": sorted(features), "data_label": "Local role catalog - seeded, illustrative (no job-site scraping)."}
