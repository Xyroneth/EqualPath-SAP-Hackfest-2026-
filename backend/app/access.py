"""Who may see what. Personal evidence stays with the candidate (and their counsellor); everyone else sees only what they need."""
from __future__ import annotations

import copy

# Roles that may open the candidate's raw evidence files and extracted skill quotes.
EVIDENCE_ROLES = ("candidate", "counsellor")
# Roles that may open the personal parts of a run (skills, quotes, profile).
PERSONAL_VIEW_ROLES = ("candidate", "counsellor")

_PERSONAL_KEYS = ("skills", "discovery", "candidate_review", "intake")
_INTERRUPT_KEEP = ("checkpoint", "title", "required_role")
# Text fields of agent outputs that carry no personal data (catalog role names, decisions, routing).
_SAFE_TEXT_OUTPUTS = ("recommended", "recommended_id", "role_id", "role_title", "decision", "workflow", "status", "reason")


def scrub_run_view(view: dict, role: str) -> dict:
    """Return the run view a given role is allowed to see (deep copy; the original is untouched)."""
    if role in PERSONAL_VIEW_ROLES:
        return view
    v = copy.deepcopy(view)
    vals = v["values"]
    for k in _PERSONAL_KEYS + ("ranking", "role_selection"):
        vals.pop(k, None)
    for t in v["timeline"]:
        t["inputs"], t["outputs"] = {}, {k: x for k, x in (t.get("outputs") or {}).items() if isinstance(x, (int, float, bool)) or k in _SAFE_TEXT_OUTPUTS}
    ba = vals.get("bias_audit")
    if ba:
        ba.get("baseline", {}).pop("reference_rules", None)  # would reveal e.g. the length of her career break
        # The twins are synthetic, but their "before" values are the candidate's own details (name, age, gender...).
        for tw in ba.get("counterfactuals", []):
            if not any(d["field"] == "name" for d in tw.get("diff", [])):
                tw["twin_name"] = None
            for d in tw.get("diff", []):
                d["before"] = None
    pw = vals.get("pathway")
    if pw:
        for g in pw.get("gaps", []):
            if g.get("evidence"):
                g["evidence"] = {"verification_status": g["evidence"].get("verification_status"), "proficiency": g["evidence"].get("proficiency")}
    if role == "auditor":
        keep = {"bias_audit", "employer_scan", "selected_role_id", "provider", "final_review", "review_task"}
        for k in list(vals):
            if k not in keep:
                vals.pop(k, None)
        if "employer_scan" in vals:
            es = vals["employer_scan"]
            vals["employer_scan"] = {k: es.get(k) for k in ("summary", "job_id", "job_title", "version_label", "high_count", "categories_flagged", "conflict_count", "disclaimer", "data_label")}
        if "final_review" in vals:
            fr = vals["final_review"]
            vals["final_review"] = {k: fr.get(k) for k in ("decision", "actor", "reviewer_role", "at", "via")}
        vals.pop("review_task", None)
    if v.get("interrupt"):
        v["interrupt"] = {k: v["interrupt"].get(k) for k in _INTERRUPT_KEEP}
        if role == "hr_reviewer" and v["interrupt"]["checkpoint"] == "final_review":
            v["interrupt"]["task"] = view["interrupt"].get("task")
    return v
