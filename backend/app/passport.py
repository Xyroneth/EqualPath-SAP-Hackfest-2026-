"""Mutual Readiness Passport composer and reviewed-evidence overlays."""
from __future__ import annotations

import copy
import html
import uuid

from app.agents.common import active_skills, role_by_id
from app.agents.learning_pathway import classify_gaps
from app.providers.repository import get_repository, utcnow

ALLOWED_OUTCOMES = ("Ready to Proceed", "Ready with Learning Milestone", "Employer Action Required", "Human Review Required")
DISCLAIMER = ("Decision-support document, not a job guarantee or certification. Every claim shows its source and evidence status. "
              "Human reviewers own the decision.")


def apply_overlays(run_id: str, values: dict) -> dict:
    """Apply human-reviewed milestone evidence: an accepted submission upgrades that capability to `assessed`."""
    if not values.get("candidate_id"):
        return values
    repo = get_repository()
    subs = [s for s in repo.list("evidence_submissions", owner_id=values["candidate_id"]) if s["run_id"] == run_id]
    progress = {p["milestone_id"]: p for p in repo.list("milestone_progress", owner_id=values["candidate_id"]) if p["run_id"] == run_id}
    if not subs and not progress:
        return values
    v = copy.deepcopy(values)
    pathway = v.get("pathway")
    if not pathway:
        return v
    by_mid = {m["milestone_id"]: m for m in pathway["milestones"]}
    for mid, p in progress.items():
        if mid in by_mid:
            by_mid[mid]["progress"] = p["progress"]
    skills = {s["normalized_skill"]: s for s in v.get("skills", [])}
    for sub in sorted(subs, key=lambda s: s["submitted_at"]):
        m = by_mid.get(sub["milestone_id"])
        if not m:
            continue
        m["progress"] = {"pending_review": "evidence_submitted", "accepted": "accepted", "rejected": "needs_more_evidence",
                         "request_more": "needs_more_evidence"}.get(sub["status"], m["progress"])
        m.setdefault("submissions", []).append({k: sub[k] for k in ("submission_id", "evidence_kind", "title", "status", "submitted_at")})
        if sub["status"] == "accepted":
            gap = next((g for g in pathway["gaps"] if g["capability"] == m["capability"]), {})
            skills[m["capability"]] = {
                **skills.get(m["capability"], {}),
                "skill_name": m["gap"], "normalized_skill": m["capability"], "category": skills.get(m["capability"], {}).get("category", "technical"),
                "proficiency": gap.get("required_level", "basic"), "evidence_type": "learning_evidence",
                "evidence_quote": sub["content"][:200], "source_id": f"milestone:{m['milestone_id']}/{sub['submission_id']}",
                "recency": sub["submitted_at"][:7], "confidence": 1.0, "verification_status": "assessed",
                "adjacent_skills": skills.get(m["capability"], {}).get("adjacent_skills", []),
                "additional_sources": [], "extraction_method": "human_reviewed_milestone", "candidate_action": "accepted",
                "notes": [f"Milestone evidence accepted by {sub['review']['actor']} on {sub['review']['at'][:10]}: {sub['review']['reason']}"],
            }
    v["skills"] = list(skills.values())
    role = role_by_id(v.get("selected_role_id", ""))
    if role:
        pathway["gaps"] = classify_gaps(v["skills"], role)
        pathway["counts"] = {s: sum(1 for g in pathway["gaps"] if g["status"] == s) for s in ("verified", "developing", "missing")}
    return v


def _outcomes(v: dict) -> list[dict]:
    pathway, scan, bias = v.get("pathway", {}), v.get("employer_scan", {}), v.get("bias_audit", {})
    open_essential = [g for g in pathway.get("gaps", []) if g["importance"] == "essential" and g["status"] != "verified"]
    out = []
    if bias and not bias.get("passed", True):
        out.append({"outcome": "Human Review Required", "side": "Process", "responsible": "Counsellor", "code": "bias_flag", "params": {},
                    "explanation": "The bias audit flagged a material counterfactual change."})
    if open_essential:
        names = ", ".join(g["capability_name"] for g in open_essential)
        out.append({"outcome": "Ready with Learning Milestone", "side": "Candidate", "responsible": "Candidate, with counsellor review", "code": "learning",
                    "params": {"n": len(open_essential), "capabilities": [g["capability"] for g in open_essential], "hours": pathway.get("total_hours", 0),
                               "weeks": pathway.get("estimated_weeks")},
                    "explanation": f"Strong verified base; {len(open_essential)} essential capability gap(s) remain: {names}. "
                                   f"Plan: {pathway.get('total_hours', 0):g} h (~{pathway.get('estimated_weeks')} weeks)."})
    else:
        out.append({"outcome": "Ready to Proceed", "side": "Candidate", "responsible": "Employer (interview)", "code": "ready", "params": {},
                    "explanation": "All essential capabilities are verified with evidence."})
    if scan.get("employer_action_required"):
        high = [f for f in scan.get("flags", []) if f["severity"] == "high"]
        out.append({"outcome": "Employer Action Required", "side": "Employer", "responsible": "Employer HR", "code": "employer",
                    "params": {"n": len(scan.get("flags", [])), "high": len(high), "categories": sorted({f["category"] for f in high})[:3]},
                    "explanation": f"{len(scan.get('flags', []))} barrier(s) in the job description ({len(high)} high severity), e.g. "
                                   + "; ".join(f["label"] for f in high[:3]) + "."})
    override = (v.get("final_review") or {}).get("overrides", {}).get("outcome.override")
    if override:
        chosen = [o for o in ([override] if isinstance(override, str) else override) if o in ALLOWED_OUTCOMES]
        if chosen:
            reason = next((e["reason"] for e in v["final_review"]["edits"] if e["target"] == "outcome.override"), "")
            out = [{"outcome": o, "side": "Reviewer override", "responsible": "Reviewer", "code": "override", "params": {"reason": reason},
                    "explanation": f"Set by human reviewer: {reason}"} for o in chosen]
    return out


def _next_actions(v: dict) -> list[dict]:
    acts = []
    pathway, scan = v.get("pathway", {}), v.get("employer_scan", {})
    for m in pathway.get("milestones", []):
        if m.get("progress") != "accepted" and m["importance"] == "essential":
            acts.append({"action": f"Complete milestone '{m['gap']}' ({m['estimated_hours']:g} h) and submit: {', '.join(m['required_evidence'])}.",
                         "responsible": "Candidate", "status": m.get("progress", "not_started"), "code": "milestone",
                         "params": {"capability": m["capability"], "gap": m["gap"], "hours": m["estimated_hours"]}})
    if any(m.get("progress") == "evidence_submitted" for m in pathway.get("milestones", [])):
        acts.append({"action": "Review submitted milestone evidence before any capability status changes.", "responsible": "Counsellor", "status": "open",
                     "code": "review_evidence", "params": {}})
    rewrite = get_repository().get("jd_rewrites", v.get("run_id", "")) or {}
    if scan.get("flags"):
        acts.append({"action": "Approve the suggested job-description rewrite." if rewrite.get("status") == "pending_hr_approval"
                     else f"Job-description rewrite status: {rewrite.get('status', 'n/a').replace('_', ' ')}.", "responsible": "HR reviewer",
                     "status": rewrite.get("status", "n/a"), "code": "jd_rewrite", "params": {"status": rewrite.get("status", "n/a")}})
        for f in [f for f in scan["flags"] if f["severity"] == "high"]:
            acts.append({"action": f"Fix: {f['label']}" + (f" - \"{f['text'][:90]}\"" if f.get("text") else ""), "responsible": "Employer HR", "status": "open",
                         "code": "fix_flag", "params": {"category": f["category"], "aspect": f.get("aspect"), "text": (f.get("text") or "")[:90]}})
    repo = get_repository()
    for cid in scan.get("conflicts_requiring_review", []):
        answered = repo.get("claim_responses", f"{v.get('run_id', '')}:{cid}")
        acts.append({"action": f"Resolve conflicting evidence on employer claim '{cid.replace('_', ' ')}' before shortlisting.", "responsible": "HR reviewer",
                     "status": "completed" if answered else "open", "code": "resolve_conflict", "params": {"claim": cid}})
    decision = repo.get("employer_decisions", v.get("run_id", ""))
    acts.append({"action": "Respond to the candidate: invite to interview, keep in the talent pool or decline, with a reason.", "responsible": "HR reviewer",
                 "status": "completed" if decision else "open", "code": "employer_response", "params": {}})
    rec = (v.get("final_review") or {}).get("overrides", {}).get("recommendation.next_action")
    if rec:
        acts.insert(0, {"action": rec, "responsible": "Counsellor (reviewer recommendation)", "status": "open", "code": "reviewer_action", "params": {"text": rec}})
    return acts


def compose_passport(state: dict, draft: bool) -> dict:
    v = apply_overlays(state["run_id"], dict(state))
    repo = get_repository()
    cand = repo.get("candidates", v["candidate_id"]) or {"profile": {}, "consent": {}}
    role = role_by_id(v.get("selected_role_id", "")) or {"title": "-"}
    consent = cand.get("consent", {})
    fr = v.get("final_review")
    rewrite = repo.get("jd_rewrites", v["run_id"]) or {}
    skills = active_skills(v.get("skills", []))
    passport = {
        "passport_id": ("draft-" if draft else "MRP-") + uuid.uuid4().hex[:8].upper(),
        "draft": draft, "issued_at": None if draft else utcnow(), "run_id": v["run_id"], "candidate_ref": v["candidate_id"],
        "candidate_display_name": cand["profile"].get("display_name"), "target_role": role["title"],
        "provider": v.get("provider", {}), "disclaimer": DISCLAIMER,
        "outcomes": _outcomes(v),
        "sections": {
            "capability_evidence": {"shared_with_employer": consent.get("share_with_employer", False), "items": [
                {k: s.get(k) for k in ("skill_name", "normalized_skill", "verification_status", "proficiency", "claimed_proficiency",
                                       "evidence_quote", "source_id", "evidence_type", "recency", "confidence")} for s in skills]},
            "role_gap_map": {"shared_with_employer": consent.get("share_with_employer", False), "role": role["title"],
                             "counts": v.get("pathway", {}).get("counts"), "gaps": v.get("pathway", {}).get("gaps", []),
                             "milestones": v.get("pathway", {}).get("milestones", []), "total_hours": v.get("pathway", {}).get("total_hours"),
                             "estimated_weeks": v.get("pathway", {}).get("estimated_weeks")},
            "work_condition_fit": {"shared_with_employer": consent.get("share_with_employer", False),
                                   "conditions": [c if consent.get("share_accommodations") or not c["condition"].startswith("Work accommodations")
                                                  else {**c, "candidate": "Not shared by candidate"} for c in
                                                  (v.get("matching", {}).get("components", {}).get("work_conditions", []))]},
            "employer_readiness": {"shared_with_employer": True, "summary": v.get("employer_scan", {}).get("summary"),
                                   "employer": v.get("employer_scan", {}).get("employer"), "job_title": v.get("employer_scan", {}).get("job_title"),
                                   "flags": [{k: f.get(k) for k in ("label", "category", "aspect", "severity", "kind", "text", "explanation", "fix")} for f in v.get("employer_scan", {}).get("flags", [])],
                                   "claims": v.get("employer_scan", {}).get("claims", []), "rewrite_status": rewrite.get("status", "not_needed"),
                                   "claim_responses": {c: r for c in v.get("employer_scan", {}).get("conflicts_requiring_review", [])
                                                       for r in [repo.get("claim_responses", f"{v['run_id']}:{c}")] if r},
                                   "disclaimer": v.get("employer_scan", {}).get("disclaimer"), "data_label": v.get("employer_scan", {}).get("data_label")},
            "bias_audit": {"shared_with_employer": True, "result": v.get("bias_audit", {}).get("result"), "passed": v.get("bias_audit", {}).get("passed"),
                           "counterfactuals_run": len(v.get("bias_audit", {}).get("counterfactuals", [])),
                           "feature_audit_passed": v.get("bias_audit", {}).get("feature_audit", {}).get("passed"),
                           "reference_flagged": (v.get("bias_audit", {}).get("reference_filter") or {}).get("flagged"),
                           "auditor_review": repo.get("fairness_reviews", v["run_id"]),
                           "limitations": v.get("bias_audit", {}).get("limitations", [])},
            "human_review": {"shared_with_employer": True, "decision": fr["decision"] if fr else "pending", "reason": fr.get("reason") if fr else None,
                             "reviewer": fr.get("actor") if fr else None, "reviewer_role": fr.get("reviewer_role") if fr else None,
                             "at": fr.get("at") if fr else None, "edits": fr.get("edits", []) if fr else [],
                             "candidate_review": v.get("candidate_review"), "via": fr.get("via") if fr else None},
            "next_actions": {"shared_with_employer": True, "items": _next_actions(v)},
        },
        "employer_response": repo.get("employer_decisions", v["run_id"]),
        "sharing": {"share_with_employer": consent.get("share_with_employer", False), "share_accommodations": consent.get("share_accommodations", False)},
    }
    return passport


def employer_copy(p: dict) -> dict:
    """Only what the candidate approved: unshared sections are withheld; no private notes ever appear."""
    c = copy.deepcopy(p)
    c["audience"] = "employer"
    if not p["sharing"]["share_with_employer"]:
        c.pop("candidate_display_name", None)
    for name, sec in c["sections"].items():
        if not sec.get("shared_with_employer"):
            c["sections"][name] = {"shared_with_employer": False, "withheld": "Not shared by the candidate."}
    return c


def passport_html(p: dict) -> str:
    e = html.escape
    s = p["sections"]
    status_badge = lambda t: f'<span class="b b-{e(str(t))}">{e(str(t).replace("_", " "))}</span>'

    def table(rows, cols):
        head = "".join(f"<th>{e(c[1])}</th>" for c in cols)
        body = "".join("<tr>" + "".join(f"<td>{c[2](r) if len(c) > 2 else e(str(r.get(c[0], '') or ''))}</td>" for c in cols) + "</tr>" for r in rows)
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    parts = [f"<h1>Mutual Readiness Passport</h1><p class='meta'>{e(p['passport_id'])} &middot; issued {e(str(p['issued_at']))} &middot; "
             f"target role: <b>{e(p['target_role'])}</b> &middot; candidate: {e(p.get('candidate_display_name') or p['candidate_ref'])}</p>",
             "<div class='outcomes'>" + "".join(f"<div class='o'><b>{e(o['outcome'])}</b><small>{e(o['side'])} &middot; {e(o['responsible'])}</small><p>{e(o['explanation'])}</p></div>" for o in p["outcomes"]) + "</div>"]
    if s["capability_evidence"].get("items"):
        parts.append("<h2>1. Capability Evidence</h2>" + table(s["capability_evidence"]["items"], [
            ("skill_name", "Capability"), ("verification_status", "Status", lambda r: status_badge(r["verification_status"])),
            ("proficiency", "Level"), ("evidence_quote", "Evidence quote", lambda r: f"&ldquo;{e(r['evidence_quote'] or '')}&rdquo;"), ("source_id", "Source")]))
    else:
        parts.append("<h2>1. Capability Evidence</h2><p>Not shared by the candidate.</p>")
    if s["role_gap_map"].get("gaps"):
        parts.append("<h2>2. Role Gap Map</h2>" + table(s["role_gap_map"]["gaps"], [
            ("capability_name", "Capability"), ("required_level", "Required"), ("status", "Status", lambda r: status_badge(r["status"])), ("reason", "Why")]))
        parts.append(table(s["role_gap_map"]["milestones"], [("gap", "Milestone"), ("learning_asset_title", "Learning asset", lambda r: f"<a href='{e(r['learning_asset_url'])}'>{e(r['learning_asset_title'])}</a> <small>({e(r['learning_asset_provider'])})</small>"),
                                                           ("estimated_hours", "Hours"), ("practice_task", "Practice task"), ("completion_rule", "Completion rule"), ("progress", "Progress")]))
    if s["work_condition_fit"].get("conditions"):
        parts.append("<h2>3. Work-Condition Fit</h2>" + table(s["work_condition_fit"]["conditions"], [
            ("condition", "Condition"), ("candidate", "Candidate"), ("status", "Status", lambda r: status_badge(r["status"])), ("detail", "Detail")]))
    er = s["employer_readiness"]
    parts.append(f"<h2>4. Employer Readiness</h2><p>{e(er.get('summary') or '')}</p>" + table(er.get("flags", []), [("label", "Barrier"), ("severity", "Severity"), ("text", "Flagged text")])
                 + table(er.get("claims", []), [("question", "Employer claim"), ("answer", "Answer"), ("evidence_level", "Evidence level", lambda r: status_badge(r["evidence_level"]))])
                 + f"<p class='note'>{e(er.get('disclaimer') or '')} JD rewrite: {e(er.get('rewrite_status', ''))}. {e(er.get('data_label') or '')}</p>")
    b = s["bias_audit"]
    ar = b.get("auditor_review")
    parts.append(f"<h2>5. Bias Audit Result</h2><p>{e(b.get('result') or '')}</p>"
                 + (f"<p>Auditor review: <b>{e(ar['finding'].replace('_', ' '))}</b> by {e(ar['actor'])} - {e(ar['note'])}</p>" if ar else "")
                 + "<ul>" + "".join(f"<li>{e(l)}</li>" for l in b.get("limitations", [])) + "</ul>")
    h = s["human_review"]
    parts.append(f"<h2>6. Human Review Decision</h2><p><b>{e(h['decision'])}</b> by {e(str(h.get('reviewer')))} ({e(str(h.get('reviewer_role')))}) at {e(str(h.get('at')))}. Reason: {e(str(h.get('reason') or '-'))}</p>"
                 + (table(h["edits"], [("target", "Edited"), ("old", "From"), ("new", "To"), ("reason", "Reason")]) if h.get("edits") else ""))
    er_resp = p.get("employer_response")
    if er_resp:
        parts.append(f"<h2>Employer response</h2><p><b>{e(er_resp['decision'].replace('_', ' '))}</b> by {e(er_resp['actor'])} at {e(er_resp['at'])}. Reason: {e(er_resp['reason'])}"
                     + (f". Agreed interview adjustments: {e('; '.join(er_resp['adjustments']))}" if er_resp.get("adjustments") else "") + "</p>")
    parts.append("<h2>7. Next Actions</h2>" + table(s["next_actions"]["items"], [("action", "Action"), ("responsible", "Responsible party"), ("status", "Status")]))
    parts.append(f"<p class='note'>{e(p['disclaimer'])} AI provider: {e(p['provider'].get('label', ''))}.</p>")
    css = """body{font-family:Arial,Helvetica,sans-serif;color:#1F2937;max-width:1000px;margin:24px auto;padding:0 16px}h1{color:#0A1F44}h2{color:#0A6ED1;border-bottom:2px solid #F4F8FC;padding-bottom:4px;margin-top:28px}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}th,td{border:1px solid #d6dee8;padding:6px;text-align:left;vertical-align:top}th{background:#F4F8FC}
.meta{color:#475569}.outcomes{display:flex;gap:12px;flex-wrap:wrap}.o{border:2px solid #0A6ED1;border-radius:8px;padding:10px;flex:1;min-width:260px}.o small{display:block;color:#475569}
.b{padding:2px 6px;border-radius:4px;font-size:12px;background:#e5e7eb}.b-verified,.b-source_supported,.b-assessed,.b-fit,.b-document_verified,.b-experience_validated{background:#e6f4ea;color:#188038}
.b-developing,.b-self_declared,.b-unconfirmed,.b-declared{background:#fef3c7;color:#92400e}.b-missing,.b-conflict,.b-conflicting_evidence{background:#fde2e2;color:#9b1c1c}.note{font-size:12px;color:#475569}"""
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Mutual Readiness Passport {e(p['passport_id'])}</title><style>{css}</style></head><body>{''.join(parts)}</body></html>"
