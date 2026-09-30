"""Bias Audit Agent.

For one person we cannot prove statistical fairness. We run three checks that anyone can follow:
 1. Twin test (counterfactuals) - make "twins" of the candidate that differ in ONE personal detail only (name, gender,
    age, career break, disability, college, how the home town is written), keep every skill and document the same, rerun
    the matching and compare the actual scores. Any change larger than 0.01 points goes to a human.
 2. Control test - run the same twins through a deliberately biased reference filter (simulated, with rules commonly
    reported for keyword resume filters). The test must catch that filter; this shows it is able to detect bias.
 3. Feature-use audit - confirm personal details are not matching inputs and that perturbing them changes nothing.
Production monitoring (group rates on aggregated, privacy-protected data) is shown separately as a prototype.
"""
from __future__ import annotations

import copy
import re

from app.agents.market_intelligence import rank_roles
from app.agents.skills_discovery import discover_skills
from app.privacy import MATCHING_FEATURE_ALLOWLIST, PROTECTED_ATTRIBUTES, minimise_profile_for_matching
from app.providers.llm import DemoProvider
from app.schemas import EvidenceDocument

MATERIAL_SCORE_DELTA = 0.01  # points out of 100

# Wording from the optional sample persona's documents, reworded when a twin changes that detail (ignored for anyone else).
_SAMPLE_BREAK_SENTENCE = "Returning to work after a four-year career break (2022-2026) for family caregiving. "
_SAMPLE_BREAK_PHRASE = "four-year career break (2022-2026)"
_SAMPLE_EDUCATION = "B.Sc. (Computer Science), 2018"
_FAMOUS_COLLEGE = re.compile(r"\b(IIT|NIT|BITS)\b", re.I)


def _pick(options: list[str], current: str) -> str:
    """The first twin name that is not the candidate's own name."""
    return next((o for o in options if o.lower() != (current or "").strip().lower()), options[0])


def _name_swaps(old: str, new: str) -> list[tuple[str, str]]:
    """Every form of the name that can appear in documents: full, upper-case, e-mail and handle styles, first name."""
    old = (old or "").strip()
    if not old or old.lower() == new.lower():
        return []
    o, n = old.split(), new.split()
    swaps = [(old, new), (old.upper(), new.upper())]
    if len(o) > 1 and len(n) > 1:
        swaps += [(".".join(o).lower(), ".".join(n).lower()), ("-".join(o).lower(), "-".join(n).lower())]
    swaps.append((o[0], n[0]))
    return swaps


def build_twins(profile: dict) -> list[dict]:
    """Twins of THIS candidate. Each one changes one personal detail (the gender twin changes name and gender together, as a
    real person would differ). "profile" edits the structured profile; "text" rewords the documents so skill extraction is
    re-checked on the reworded evidence."""
    name = profile.get("display_name") or ""
    gender = profile.get("gender")
    age = profile.get("age")
    cb = profile.get("career_break") or {}
    months = int(cb.get("months") or 0)
    city = profile.get("location_city") or ""
    college = profile.get("college") or ""

    to_male = gender != "male"
    gender_name = _pick(["Rahul Verma", "Amit Joshi"] if to_male else ["Priya Sharma", "Neha Gupta"], name)
    community_name = _pick(["Imran Sheikh", "Joseph D'Souza"] if gender == "male" else ["Ayesha Khan", "Mary D'Souza"], name)
    twins = [
        {"id": "man" if to_male else "woman", "why": "gender", "profile": {"display_name": gender_name, "gender": "male" if to_male else "female"},
         "text": _name_swaps(name, gender_name), "fields": ["name", "gender"]},
        {"id": "name_community", "why": "community", "profile": {"display_name": community_name}, "text": _name_swaps(name, community_name), "fields": ["name"]},
    ]

    young = 24 if age is None or age > 26 else max(18, age - 4)
    older = 45 if age is None or age < 43 else min(80, age + 10)
    if young != age:
        twins.append({"id": "age_young", "why": "age", "profile": {"age": young}, "text": [], "fields": ["age"]})
    if older != age:
        twins.append({"id": "age_older", "why": "age", "profile": {"age": older}, "text": [], "fields": ["age"]})

    own_wording = [(cb["wording"], "")] if cb.get("wording") else []
    if months >= 6:
        longer = months + 48
        twins.append({"id": "break_none", "why": "career_break", "profile": {"career_break": {"months": 0, "reason": None, "wording": ""}},
                      "text": [(_SAMPLE_BREAK_SENTENCE, "")] + own_wording, "fields": ["career_break"]})
        twins.append({"id": "break_long", "why": "career_break", "profile": {"career_break": {"months": longer, "reason": cb.get("reason"), "wording": ""}},
                      "text": [(_SAMPLE_BREAK_PHRASE, "eight-year career break (2018-2026)")], "fields": ["career_break"]})
    else:
        twins.append({"id": "break_added", "why": "career_break", "profile": {"career_break": {"months": 48, "reason": "caregiving", "wording": ""}},
                      "text": [], "fields": ["career_break"]})
        twins.append({"id": "break_long", "why": "career_break", "profile": {"career_break": {"months": 96, "reason": "caregiving", "wording": ""}},
                      "text": [], "fields": ["career_break"]})

    twins.append({"id": "disability", "why": "disability", "profile": {"disability": "Uses a screen reader"}, "text": [], "fields": ["disability"]})

    other_college = "A state university" if _FAMOUS_COLLEGE.search(college) else "IIT Delhi"
    twins.append({"id": "college", "why": "college", "profile": {"college": other_college},
                  "text": [(_SAMPLE_EDUCATION, f"B.Tech (Computer Science), {other_college}, 2018")] + ([(college, other_college)] if college else []),
                  "fields": ["college"]})

    if city.strip().lower() == "lucknow":  # the same city in its Hindi spelling, without the "tier-2" label
        twins.append({"id": "hometown", "why": "hometown", "profile": {"location_wording": "Lakhnau, UP", "location_city": "Lakhnau"},
                      "text": [("Lucknow, Uttar Pradesh", "Lakhnau, UP")], "fields": ["hometown"]})
    elif city:  # only how the home town is described changes; the city the person can commute to stays the same
        label = "metro city" if "small town" in (profile.get("location_wording") or "").lower() else "small town"
        twins.append({"id": "hometown", "why": "hometown", "profile": {"location_wording": f"{city} ({label})"}, "text": [], "fields": ["hometown"]})
    return twins


# A deliberately biased reference filter (SIMULATED). It is never used for any decision: it only proves the test can catch bias.
REFERENCE_RULES = [
    {"code": "gap_penalty", "text": "Minus 3 points for every year of career break (up to minus 24)."},
    {"code": "age_cutoff", "text": "Minus 10 points above age 35."},
    {"code": "college_bonus", "text": "Plus 10 points for IIT, NIT or BITS."},
]


def _field_value(profile: dict, field: str):
    if field == "name":
        return profile.get("display_name")
    if field == "gender":
        return profile.get("gender")
    if field == "age":
        return profile.get("age")
    if field == "career_break":
        return int((profile.get("career_break") or {}).get("months") or 0)
    if field == "disability":
        return profile.get("disability")
    if field == "college":
        return profile.get("college")
    if field == "hometown":
        return profile.get("location_wording")
    return None


def _variant_profile(profile: dict, changes: dict) -> dict:
    p = copy.deepcopy(profile)
    p.update(changes)
    if "location_city" in changes:
        p.setdefault("work_conditions", {})["commute_city"] = changes["location_city"]
    return p


def _scores(ranking: dict) -> dict:
    return {r["role_id"]: round(r["total"] * 100, 2) for r in ranking["top_roles"] + ranking["other_roles"]}


def _order(ranking: dict) -> list[str]:
    return [r["role_id"] for r in ranking["top_roles"] + ranking["other_roles"]]


def reference_rules_fired(profile: dict) -> list[dict]:
    """Which rules of the simulated biased filter apply to this profile, and how many points each one adds or removes."""
    fired = []
    years = round(int((profile.get("career_break") or {}).get("months") or 0) / 12)
    if years:
        fired.append({"code": "gap_penalty", "points": -min(24, 3 * years), "years": years})
    if (profile.get("age") or 0) > 35:
        fired.append({"code": "age_cutoff", "points": -10})
    if _FAMOUS_COLLEGE.search(str(profile.get("college") or "")):
        fired.append({"code": "college_bonus", "points": 10})
    return fired


def reference_filter_score(profile: dict, base_points: float) -> float:
    """Simulated biased filter: starts from the same skills score and applies rules often found in resume filters."""
    return round(base_points + sum(r["points"] for r in reference_rules_fired(profile)), 2)


def _reasons(before: list[dict], after: list[dict]) -> list[dict]:
    """The rules whose effect differs between the real profile and the twin: this is WHY the biased filter moved."""
    b = {r["code"]: r["points"] for r in before}
    a = {r["code"]: r["points"] for r in after}
    return [{"code": c, "points": round(a.get(c, 0) - b.get(c, 0), 2)} for c in dict.fromkeys(list(b) + list(a)) if a.get(c, 0) != b.get(c, 0)]


def _skill_sig(skills: list[dict]) -> list:
    return sorted((s["normalized_skill"], s["verification_status"]) for s in skills)


def _twin_result(profile: dict, documents: list[dict], skills: list[dict], selected_role_id: str, changes: dict, text: list[tuple[str, str]],
                 fields: list[str], base: dict) -> dict:
    """Run one twin through EQUALPATH's matching (and a skill re-extraction if its documents change) and through the biased filter."""
    variant = _variant_profile(profile, changes)
    ranking = rank_roles(skills, minimise_profile_for_matching(variant))
    order, scores = _order(ranking), _scores(ranking)
    max_delta = max(abs(scores[k] - base["scores"][k]) for k in base["scores"])
    docs, changed_text = [], False
    for d in documents:
        t = d["text"]
        for old, new in text:
            if old and old in t:
                changed_text = True
                t = t.replace(old, new)
        docs.append(EvidenceDocument(**{**d, "text": t}))
    re_skills = discover_skills(docs, DemoProvider(), [variant.get("display_name", "")])["skills"] if changed_text else None
    skills_changed = re_skills is not None and _skill_sig(re_skills) != base["skill_sig"]
    material = order != base["order"] or max_delta > MATERIAL_SCORE_DELTA or skills_changed
    ref_after = reference_filter_score(variant, scores[selected_role_id])
    rules_after = reference_rules_fired(variant)
    return {
        "twin_name": variant.get("display_name"),
        "diff": [{"field": f, "before": _field_value(profile, f), "after": _field_value(variant, f)} for f in fields],
        "top_role": order[0], "top_role_same": order[0] == base["order"][0], "ranking_changed": order != base["order"],
        "selected_score_before": base["selected"], "selected_score_after": scores[selected_role_id],
        "max_score_delta": round(max_delta, 2), "selected_role_score_delta": round(abs(scores[selected_role_id] - base["selected"]), 2),
        "extraction_rechecked": re_skills is not None, "extraction_changed": skills_changed,
        "skills_before": len(base["skill_sig"]), "skills_after": len(re_skills) if re_skills is not None else None,
        "material_change": material,
        "reference": {"before": base["ref"], "after": ref_after, "delta": round(ref_after - base["ref"], 2),
                      "would_flag": abs(ref_after - base["ref"]) > MATERIAL_SCORE_DELTA,
                      "reasons": _reasons(base["ref_rules"], rules_after)},
    }


def _baseline(profile: dict, documents: list[dict], skills: list[dict], selected_role_id: str) -> tuple[dict, dict]:
    rank = rank_roles(skills, minimise_profile_for_matching(profile))
    scores = _scores(rank)
    selected = scores[selected_role_id]
    det = discover_skills([EvidenceDocument(**d) for d in documents], DemoProvider(), [profile.get("display_name", "")])["skills"]
    base = {"order": _order(rank), "scores": scores, "selected": selected, "skill_sig": _skill_sig(det),
            "ref": reference_filter_score(profile, selected), "ref_rules": reference_rules_fired(profile)}
    return base, rank


def run_bias_audit(profile: dict, documents: list[dict], skills: list[dict], selected_role_id: str, employer_scan: dict | None = None) -> dict:
    base, base_rank = _baseline(profile, documents, skills, selected_role_id)
    base_features = minimise_profile_for_matching(profile)
    base_selected, base_ref = base["selected"], base["ref"]
    orig_sig = base["skill_sig"]
    twins = [{"id": tw["id"], "why": tw["why"], **_twin_result(profile, documents, skills, selected_role_id, tw["profile"], tw["text"], tw["fields"], base)}
             for tw in build_twins(profile)]

    # Feature-use audit: the matching only ever receives allow-listed features; changing personal details changes nothing.
    features_used = sorted(base_features)
    protected_in_features = sorted(set(features_used) & set(PROTECTED_ATTRIBUTES))
    perturbation = []
    for attr, values in {"gender": ["female", "male", "non-binary", None], "age": [22, 31, 58], "career_break": [{"months": 0}, {"months": 52}, {"months": 180}],
                         "disability": [None, "disclosed"], "display_name": [profile.get("display_name") or "Candidate", "A. N. Other"], "college": [None, "IIT Delhi"]}.items():
        totals = set()
        for v in values:
            f = minimise_profile_for_matching(_variant_profile(profile, {attr: v}))
            totals.add(tuple(sorted(_scores(rank_roles(skills, f)).items())))
        perturbation.append({"attribute": attr, "values_tested": len(values), "contribution": 0.0 if len(totals) == 1 else "NON-ZERO"})
    feature_audit = {
        "features_used": features_used,
        "allowlist_respected": set(features_used) <= MATCHING_FEATURE_ALLOWLIST,
        "protected_in_features": protected_in_features,
        "perturbation": perturbation,
        "passed": not protected_in_features and all(p["contribution"] == 0.0 for p in perturbation),
    }
    material = [t for t in twins if t["material_change"]]
    ref_flagged = [t for t in twins if t["reference"]["would_flag"]]
    passed = not material and feature_audit["passed"]
    top3 = base_rank["top_roles"]
    return {
        "counterfactuals": twins,
        "baseline": {"ranking": [{"role_id": r["role_id"], "title": r["title"], "score": round(r["total"] * 100, 2)} for r in top3],
                     "selected_role_id": selected_role_id, "selected_score": base_selected, "skills": len(orig_sig), "reference_score": base_ref,
                     "reference_rules": base["ref_rules"]},
        "reference_filter": {"label": "SIMULATED biased reference filter. Never used for decisions; it shows the test can detect bias.",
                             "rules": REFERENCE_RULES, "flagged": len(ref_flagged), "flagged_ids": [t["id"] for t in ref_flagged],
                             "passed": not ref_flagged},
        "threshold_points": MATERIAL_SCORE_DELTA,
        "feature_audit": feature_audit,
        "passed": passed,
        "result": (f"PASS - all {len(twins)} twins got the same roles, order and scores; personal details contribute 0 points. "
                   f"The same test flags {len(ref_flagged)} of {len(twins)} twins for a simulated biased filter.")
                  if passed else f"FLAG - {len(material)} twin(s) changed the outcome; routed to human review.",
        "triggers_human_review": not passed or bool(employer_scan and employer_scan.get("conflicts_requiring_review")),
        "material_count": len(material),
        "limitation_codes": ["single_person", "llm_not_rerun", "group_monitoring"],
        "limitations": [
            "A single-person twin test is not statistical proof of fairness.",
            "Extraction re-checks use the deterministic engine; LLM extraction is not re-run for every twin in the prototype.",
            "Group-level fairness requires production monitoring on aggregated, privacy-protected outcomes.",
        ],
    }


TRY_FIELDS = ("name", "gender", "age", "career_break_years", "disability", "college", "hometown")
GENDERS = ("female", "male", "non_binary", "other")


def try_twin(profile: dict, documents: list[dict], skills: list[dict], selected_role_id: str, field: str, value: str) -> dict:
    """A twin the user designs: change ONE detail and run the same check on EQUALPATH and on the biased filter."""
    value = (value or "").strip()
    if field not in TRY_FIELDS or not value:
        raise ValueError("Choose one of the listed details and give it a value.")
    changes: dict = {}
    text: list[tuple[str, str]] = []
    shown = field
    if field == "name":
        if len(value) > 60:
            raise ValueError("Please use a shorter name.")
        changes = {"display_name": value}
        text = _name_swaps(profile.get("display_name") or "", value)
    elif field == "gender":
        if value not in GENDERS:
            raise ValueError("Unknown gender value.")
        changes = {"gender": value}
    elif field == "age":
        if not value.isdigit() or not 16 <= int(value) <= 80:
            raise ValueError("Age must be a number between 16 and 80.")
        changes = {"age": int(value)}
    elif field == "career_break_years":
        if not value.isdigit() or int(value) > 30:
            raise ValueError("Career break must be a number of years between 0 and 30.")
        years = int(value)
        changes = {"career_break": {"months": years * 12, "reason": "caregiving" if years else None, "wording": ""}}
        own = (profile.get("career_break") or {}).get("wording")
        text = ([(_SAMPLE_BREAK_SENTENCE, "")] + ([(own, "")] if own else [])) if years == 0 else [(_SAMPLE_BREAK_PHRASE, f"{years}-year career break ({2026 - years}-2026)")]
        shown = "career_break"
    elif field in ("disability", "college", "hometown"):
        if len(value) > 80:
            raise ValueError("Please keep it under 80 characters.")
        if field == "disability":
            changes = {"disability": value}
        elif field == "college":
            changes = {"college": value}
            own = profile.get("college")
            text = [(_SAMPLE_EDUCATION, f"B.Sc. (Computer Science), {value}, 2018")] + ([(own, value)] if own else [])
        else:
            changes = {"location_wording": value}  # how the home town is written; the commute city (a real job need) stays the same
    base, _ = _baseline(profile, documents, skills, selected_role_id)
    return {"field": field, **_twin_result(profile, documents, skills, selected_role_id, changes, text, [shown], base)}


def monitoring_prototype() -> dict:
    """Clearly labelled synthetic illustration of the production monitoring dashboard layout."""
    groups = [
        {"dimension": "Gender", "group": "Women", "n": 420, "recommended": 0.62, "approved": 0.48, "rejected": 0.14},
        {"dimension": "Gender", "group": "Men", "n": 455, "recommended": 0.64, "approved": 0.50, "rejected": 0.13},
        {"dimension": "Gender", "group": "Undisclosed", "n": 7, "recommended": None, "approved": None, "rejected": None},
        {"dimension": "Career break", "group": "Break of 1+ years", "n": 180, "recommended": 0.58, "approved": 0.36, "rejected": 0.21},
        {"dimension": "Career break", "group": "No break", "n": 702, "recommended": 0.64, "approved": 0.51, "rejected": 0.12},
        {"dimension": "City tier", "group": "Tier-2 / Tier-3", "n": 390, "recommended": 0.61, "approved": 0.47, "rejected": 0.15},
        {"dimension": "City tier", "group": "Tier-1", "n": 492, "recommended": 0.65, "approved": 0.50, "rejected": 0.13},
    ]
    ref = {"Gender": "Men", "Career break": "No break", "City tier": "Tier-1"}
    for g in groups:
        if g["n"] < 10:
            g["suppressed"] = True
            g["impact_ratio"] = None
            g["alert"] = False
            continue
        r = next(x for x in groups if x["dimension"] == g["dimension"] and x["group"] == ref[g["dimension"]])
        g["suppressed"] = False
        g["impact_ratio"] = round(g["approved"] / r["approved"], 2)
        g["alert"] = g["impact_ratio"] < 0.8
    return {
        "label": "SYNTHETIC ILLUSTRATION - not real outcomes. Shows how production monitoring would work.",
        "method": "Approval-rate impact ratio vs. reference group (four-fifths rule, alert below 0.80). Groups with n < 10 are suppressed. "
                  "Only aggregated counts are stored; group attributes are self-reported, optional and kept separate from matching features.",
        "groups": groups,
    }
