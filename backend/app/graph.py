"""EQUALPATH Career Orchestrator - one LangGraph workflow with shared state, checkpoints, retries and human interrupts.

intake -> skills_discovery -> [HUMAN 1: candidate_review] -> market_intelligence -> [candidate choice: role_selection]
       -> (learning_pathway || employer_readiness) -> inclusive_matching -> bias_audit -> review_routing
       -> [HUMAN 2: final_review] -> passport            (reject -> END, request_evidence -> await_evidence -> review_routing)
"""
from __future__ import annotations

import operator
import sqlite3
import time
from functools import wraps
from typing import Annotated, Any, Callable, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, interrupt

from app.agents.bias_audit import run_bias_audit
from app.agents.common import employer_for, improved_job_for, job_by_id, match_taxonomy, role_by_id, taxonomy
from app.agents.employer_readiness import assess_employer
from app.agents.inclusive_matching import assess_match
from app.agents.learning_pathway import build_pathway
from app.agents.market_intelligence import rank_roles
from app.agents.skills_discovery import discover_skills
from app.config import get_settings
from app.passport import apply_overlays, compose_passport
from app.privacy import minimise_profile_for_matching, redact
from app.providers.learning_catalog import get_learning_catalog
from app.providers.llm import get_llm_provider
from app.providers.repository import get_repository, utcnow
from app.providers.review_workflow import get_review_workflow
from app.schemas import PROFICIENCY_ORDER, EvidenceDocument

NODE_META = {
    "intake": ("Career Orchestrator", "orchestrator"),
    "skills_discovery": ("Skills Discovery Agent", "agent"),
    "candidate_review": ("Human checkpoint 1 - Candidate review", "human"),
    "market_intelligence": ("Market Intelligence Agent", "agent"),
    "role_selection": ("Candidate choice - target role", "human"),
    "learning_pathway": ("Learning Pathway Agent", "agent"),
    "employer_readiness": ("Employer Readiness Agent", "agent"),
    "inclusive_matching": ("Inclusive Matching Agent", "agent"),
    "bias_audit": ("Bias Audit Agent", "agent"),
    "review_routing": ("Career Orchestrator - review routing", "orchestrator"),
    "final_review": ("Human checkpoint 2 - Counsellor review", "human"),
    "await_evidence": ("Candidate evidence request", "human"),
    "passport": ("Career Orchestrator - Passport composer", "orchestrator"),
}
PAST_TENSE = {"accept": "accepted", "edit": "edited", "remove": "removed"}
PLANNED_ORDER = ["intake", "skills_discovery", "candidate_review", "market_intelligence", "role_selection",
                 "learning_pathway", "employer_readiness", "inclusive_matching", "bias_audit", "review_routing",
                 "final_review", "passport"]


class CareerState(TypedDict, total=False):
    run_id: str
    candidate_id: str
    job_id: str
    provider: dict
    intake: dict
    discovery: dict
    skills: list[dict]
    candidate_review: dict
    ranking: dict
    selected_role_id: str
    role_selection: dict
    pathway: dict
    employer_scan: dict
    matching: dict
    bias_audit: dict
    review_task: dict
    final_review: dict
    evidence_requests: Annotated[list, operator.add]
    passport: dict
    timeline: Annotated[list, operator.add]


# ------------------------------------------------------------------ helpers

def _candidate(state: CareerState) -> dict:
    c = get_repository().get("candidates", state["candidate_id"])
    if c is None:
        raise RuntimeError("candidate data not found (deleted?)")
    return c


def _features(state: CareerState) -> dict:
    return minimise_profile_for_matching(_candidate(state)["profile"])


def node(node_id: str, handoff_to: list[str] | None = None) -> Callable:
    """Wrap a node: measure duration, write an immutable audit event and a timeline entry."""
    agent, kind = NODE_META[node_id]

    def deco(fn: Callable[[CareerState], dict]) -> Callable[[CareerState], dict]:
        @wraps(fn)
        def wrapper(state: CareerState) -> dict:
            started, t0 = utcnow(), time.perf_counter()
            try:
                out = fn(state)
            except GraphInterrupt:
                raise
            except Exception as exc:
                get_repository().append_audit(event_type="agent_error", actor=agent, run_id=state["run_id"], candidate_id=state["candidate_id"],
                                              summary=f"{agent} failed: {type(exc).__name__}", details={"node": node_id, "error": str(exc)[:300]})
                raise
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            meta = out.pop("_meta", {})
            actor = meta.get("actor", agent)
            ev = get_repository().append_audit(
                event_type=meta.get("event_type", "agent_execution" if kind != "human" else "human_decision"),
                actor=actor, run_id=state["run_id"], candidate_id=state["candidate_id"], summary=meta.get("summary", f"{agent} completed"),
                details={"node": node_id, "duration_ms": duration_ms, "confidence": meta.get("confidence"),
                         "inputs": meta.get("inputs", {}), "outputs": meta.get("outputs", {}), "method": meta.get("method")},
            )
            out["timeline"] = [{
                "node": node_id, "agent": agent, "kind": kind, "actor": actor, "status": "completed",
                "started_at": started, "ended_at": utcnow(), "duration_ms": duration_ms,
                "confidence": meta.get("confidence"), "inputs": meta.get("inputs", {}), "outputs": meta.get("outputs", {}),
                "summary": meta.get("summary", ""), "method": meta.get("method"), "handoff_to": handoff_to or [],
                "message": meta.get("message"), "audit_event_id": ev["event_id"],
            }]
            if kind != "human" and not get_llm_provider().is_live:
                time.sleep(get_settings().demo_step_delay_ms / 1000)  # visual pacing only; excluded from duration_ms
            return out

        return wrapper

    return deco


# ------------------------------------------------------------------ nodes

@node("intake", ["skills_discovery"])
def intake(state: CareerState) -> dict:
    cand = _candidate(state)
    if not cand["consent"].get("process_profile"):
        raise PermissionError("candidate has not consented to processing")
    provider = get_llm_provider().info().as_dict()
    names = [cand["profile"].get("display_name", "")]
    redaction = {}
    for d in cand["documents"]:
        for k, v in redact(d["text"], names).counts.items():
            redaction[k] = redaction.get(k, 0) + v
    features = minimise_profile_for_matching(cand["profile"])
    return {
        "provider": provider,
        "intake": {"documents": len(cand["documents"]), "consent": cand["consent"], "redaction_preview": redaction,
                   "matching_features": sorted(features), "provider": provider},
        "_meta": {"summary": f"Consent confirmed; {len(cand['documents'])} evidence documents loaded; {sum(redaction.values())} identifiers will be redacted before any LLM call.",
                  "inputs": {"documents": len(cand["documents"])}, "outputs": {"documents": len(cand["documents"]), "redactions": sum(redaction.values()), "provider": provider["label"]},
                  "message": "Handing evidence to Skills Discovery with direct identifiers removed."},
    }


@node("skills_discovery", ["candidate_review"])
def skills_discovery(state: CareerState) -> dict:
    cand = _candidate(state)
    docs = [EvidenceDocument(**d) for d in cand["documents"]]
    result = discover_skills(docs, get_llm_provider(), [cand["profile"].get("display_name", "")])
    self_declared = [s["skill_name"] for s in result["skills"] if s["verification_status"] == "self_declared"]
    return {
        "discovery": result,
        "_meta": {"summary": f"Extracted {len(result['skills'])} capabilities ({result['source_supported_count']} source-supported, {result['self_declared_count']} self-declared); {len(result['rejected'])} rejected by validation.",
                  "confidence": result["mean_confidence"], "method": result["method"],
                  "inputs": {"documents": result["documents_processed"], "redacted_identifiers": sum(result["redaction"].values())},
                  "outputs": {"skills": len(result["skills"]), "source_supported": result["source_supported_count"], "self_declared": len(self_declared),
                              "self_declared_names": self_declared, "rejected": len(result["rejected"]), "fallback": result["fallback_reason"]},
                  "message": "Profile ready for the candidate's review. Self-declared claims stay unverified until evidence is reviewed."},
    }


@node("candidate_review", ["market_intelligence"])
def candidate_review(state: CareerState) -> dict:
    cand = _candidate(state)
    resume = interrupt({
        "checkpoint": "candidate_review", "title": "Candidate review: confirm skills, evidence, work preferences and sharing",
        "required_role": "candidate", "skills": state["discovery"]["skills"], "rejected": state["discovery"]["rejected"],
        "work_conditions": cand["profile"].get("work_conditions", {}), "sharing": cand["consent"],
    })
    body, actor = resume["body"], resume.get("actor", "Candidate")
    repo = get_repository()
    skills = {s["normalized_skill"]: dict(s) for s in state["discovery"]["skills"]}
    corrections = []
    for d in body.get("decisions", []):
        s = skills.get(d["normalized_skill"])
        if not s:
            continue
        if d["action"] == "remove":
            s["candidate_action"] = "removed"
        elif d["action"] == "edit":
            s["candidate_action"] = "edited"
            if d.get("skill_name"):
                s["skill_name"] = d["skill_name"]
            if d.get("proficiency"):
                # A candidate edit is a claim: it can lower the evidence-based level, never raise it.
                if PROFICIENCY_ORDER[d["proficiency"]] < PROFICIENCY_ORDER[s["proficiency"]]:
                    s["proficiency"] = d["proficiency"]
                else:
                    s["claimed_proficiency"] = d["proficiency"]
                    s.setdefault("notes", []).append("Candidate claims a higher level; evidence-based level unchanged.")
        else:
            s["candidate_action"] = "accepted"
        corrections.append({"skill": d["normalized_skill"], "action": d["action"], "reason": d.get("reason")})
        repo.append_audit(event_type="candidate_correction", actor=actor, run_id=state["run_id"], candidate_id=state["candidate_id"],
                          summary=f"Candidate {PAST_TENSE[d['action']]} skill '{s['skill_name']}'",
                          details={"skill": d["normalized_skill"], "action": d["action"], "reason": d.get("reason")})
    for a in body.get("added_skills", []):
        # A skill typed by the candidate is matched to the catalog when possible, so it counts towards role requirements (as a claim).
        known = match_taxonomy(a["skill_name"]) or match_taxonomy(a["normalized_skill"])
        key = known or a["normalized_skill"].strip().lower().replace(" ", "_")
        if key in skills and skills[key].get("candidate_action") != "removed":
            continue  # already found in the evidence; the evidence-based record stays
        skills[key] = {
            "skill_name": taxonomy()[known]["skill_name"] if known else a["skill_name"], "normalized_skill": key,
            "category": taxonomy()[known]["category"] if known else "technical", "proficiency": a.get("proficiency", "basic"),
            "evidence_type": "candidate_added", "evidence_quote": a["evidence_quote"], "source_id": a.get("source_id", "candidate-correction"),
            "recency": utcnow()[:7], "confidence": 1.0, "verification_status": "self_declared", "adjacent_skills": [],
            "additional_sources": [], "claimed_proficiency": a.get("proficiency", "basic"), "extraction_method": "candidate",
            "candidate_action": "added", "notes": ["Added by the candidate. Self-declared until evidence is reviewed."],
        }
        corrections.append({"skill": key, "action": "add"})
        repo.append_audit(event_type="candidate_correction", actor=actor, run_id=state["run_id"], candidate_id=state["candidate_id"],
                          summary=f"Candidate added skill '{a['skill_name']}' (self-declared)", details={"skill": key, "action": "add"})
    for s in skills.values():
        if s["candidate_action"] == "pending":
            s["candidate_action"] = "accepted"
    if body.get("work_conditions"):
        cand["profile"]["work_conditions"] = {**cand["profile"].get("work_conditions", {}), **body["work_conditions"]}
    if body.get("sharing"):
        cand["consent"] = {**cand["consent"], **body["sharing"]}
        repo.append_audit(event_type="consent_update", actor=actor, run_id=state["run_id"], candidate_id=state["candidate_id"],
                          summary="Candidate updated sharing permissions", details={"sharing": body["sharing"]})
    repo.put("candidates", state["candidate_id"], cand, owner_id=state["candidate_id"])
    final = list(skills.values())
    return {
        "skills": final,
        "candidate_review": {"approved": True, "actor": actor, "at": utcnow(), "corrections": corrections, "sharing": cand["consent"]},
        "_meta": {"actor": actor, "summary": f"Candidate approved profile with {len(corrections)} correction(s).",
                  "outputs": {"skills_active": sum(1 for s in final if s["candidate_action"] != "removed"), "corrections": len(corrections)},
                  "message": "Approved profile handed to Market Intelligence."},
    }


@node("market_intelligence", ["role_selection"])
def market_intelligence(state: CareerState) -> dict:
    ranking = rank_roles(state["skills"], _features(state))
    rec = ranking["top_roles"][0]
    return {
        "ranking": ranking,
        "_meta": {"summary": f"Ranked {len(ranking['top_roles']) + len(ranking['other_roles'])} catalog roles; recommended {rec['title']}.",
                  "confidence": rec["total"], "inputs": {"features_used": ranking["features_used"]},
                  "outputs": {"ranked": len(ranking["top_roles"]) + len(ranking["other_roles"]), "recommended": rec["title"], "recommended_id": rec["role_id"], "top_roles": [r["title"] for r in ranking["top_roles"]]},
                  "message": "Three role options sent to the candidate; protected attributes were not inputs."},
    }


@node("role_selection", ["learning_pathway", "employer_readiness"])
def role_selection(state: CareerState) -> dict:
    resume = interrupt({"checkpoint": "role_selection", "title": "Candidate choice: select a target role", "required_role": "candidate",
                        "top_roles": state["ranking"]["top_roles"], "recommended_role_id": state["ranking"]["recommended_role_id"]})
    role = role_by_id(resume["role_id"])
    return {
        "selected_role_id": role["role_id"],
        "role_selection": {"role_id": role["role_id"], "actor": resume.get("actor", "Candidate"), "reason": resume.get("reason"), "at": utcnow(),
                           "followed_recommendation": role["role_id"] == state["ranking"]["recommended_role_id"]},
        "_meta": {"actor": resume.get("actor", "Candidate"), "summary": f"Candidate selected target role: {role['title']}.",
                  "outputs": {"role_id": role["role_id"], "role_title": role["title"]}, "message": "Learning Pathway and Employer Readiness start in parallel."},
    }


@node("learning_pathway", ["inclusive_matching"])
def learning_pathway(state: CareerState) -> dict:
    role = role_by_id(state["selected_role_id"])
    weekly = _features(state)["weekly_learning_hours"]
    pw = build_pathway(state["skills"], role, get_learning_catalog(), get_llm_provider(), weekly)
    return {
        "pathway": pw,
        "_meta": {"summary": f"Gap map: {pw['counts']['verified']} verified, {pw['counts']['developing']} developing, {pw['counts']['missing']} missing; {len(pw['milestones'])} milestones, {pw['total_hours']:g} h (~{pw['estimated_weeks']} weeks).",
                  "method": pw["method"], "confidence": 1.0 if pw["method"] == "deterministic" else 0.8,
                  "inputs": {"role": role["title"], "requirements": len(role["requirements"])},
                  "outputs": {**pw["counts"], "milestones": len(pw["milestones"]), "hours": pw["total_hours"], "weeks": pw["estimated_weeks"],
                              "sap_assets": pw["sap_assets_used"], "fallback": pw["fallback_reason"]},
                  "message": "Gap feasibility shared with Inclusive Matching."},
    }


@node("employer_readiness", ["inclusive_matching"])
def employer_readiness(state: CareerState) -> dict:
    role = role_by_id(state["selected_role_id"])
    job = job_by_id(state["job_id"]) if state.get("job_id") and job_by_id(state["job_id"]) and job_by_id(state["job_id"])["role_id"] == role["role_id"] else None
    if job is None and role["job_ids"]:
        job = job_by_id(role["job_ids"][0])
    if job is None:
        scan = {"job_id": None, "flags": [], "claims": [], "conflicts_requiring_review": [], "employer_action_required": True,
                "summary": "No seeded job description for this role; employer readiness cannot be assessed.", "suggested_rewrite": {"text": None, "status": "not_available"},
                "categories_checked": [], "flags_by_category": {}, "disclaimer": "", "data_label": "No data"}
    else:
        scan = assess_employer(job, employer_for(job))
        improved = improved_job_for(job)
        scan["improved_job_id"] = improved["job_id"] if improved and improved["job_id"] != job["job_id"] else None
        if scan["suggested_rewrite"]["text"]:
            get_repository().put("jd_rewrites", state["run_id"], {"run_id": state["run_id"], "job_id": job["job_id"], "employer_id": job["employer_id"],
                                                                  "job_title": job["title"], "employer": scan["employer"], "original": job["text"],
                                                                  "suggested": scan["suggested_rewrite"]["text"], "changes": scan["suggested_rewrite"]["changes"],
                                                                  "status": "pending_hr_approval", "history": []}, owner_id=state["candidate_id"])
    return {
        "employer_scan": scan,
        "_meta": {"summary": scan["summary"], "confidence": 1.0, "method": "rule-based scanner v2",
                  "inputs": {"job_id": scan["job_id"]}, "outputs": {"flags": len(scan["flags"]), "high": scan.get("high_count", 0), "categories": scan.get("categories_flagged", 0),
                                                                   "conflicts": len(scan["conflicts_requiring_review"])},
                  "message": "Unconfirmed work conditions shared with Inclusive Matching; rewrite queued for HR approval."},
    }


@node("inclusive_matching", ["bias_audit"])
def inclusive_matching(state: CareerState) -> dict:
    cand = _candidate(state)
    role = role_by_id(state["selected_role_id"])
    shared = cand["profile"].get("accommodations", {}).get("shareable_work_accommodations", []) if cand["consent"].get("share_accommodations") else []
    m = assess_match(role, _features(state), state["pathway"], state["employer_scan"], shared)
    c = m["components"]
    return {
        "matching": m,
        "_meta": {"summary": f"Mutual fit: {c['capability_coverage']['verified']}/{c['capability_coverage']['total_essential']} essential verified, evidence {c['evidence_strength']['value']}, gap feasibility {c['gap_feasibility']['level']}, {len(m['employer_actions'])} employer action(s).",
                  "confidence": c["evidence_strength"]["value"], "outputs": {"verified": c["capability_coverage"]["verified"], "total": c["capability_coverage"]["total_essential"],
                                                                        "evidence": c["evidence_strength"]["value"], "feasibility": c["gap_feasibility"]["level"], "employer_actions": len(m["employer_actions"])},
                  "message": "Component view (no single score) handed to Bias Audit."},
    }


@node("bias_audit", ["review_routing"])
def bias_audit(state: CareerState) -> dict:
    cand = _candidate(state)
    b = run_bias_audit(cand["profile"], cand["documents"], state["skills"], state["selected_role_id"], state.get("employer_scan"))
    return {
        "bias_audit": b,
        "_meta": {"summary": b["result"], "confidence": 1.0 if b["passed"] else 0.5,
                  "outputs": {"counterfactuals": len(b["counterfactuals"]), "passed": b["passed"], "feature_audit": b["feature_audit"]["passed"], "changed": b["material_count"]},
                  "message": "Audit attached to the human review packet."},
    }


@node("review_routing", ["final_review"])
def review_routing(state: CareerState) -> dict:
    role = role_by_id(state["selected_role_id"])
    preview = compose_passport(state, draft=True)
    task = {
        "task_id": f"review-{state['run_id']}", "type": "final_review", "run_id": state["run_id"], "candidate_id": state["candidate_id"],
        "role_title": role["title"], "proposed_outcomes": [o["outcome"] for o in preview["outcomes"]],
        "gap_summary": f"{state['pathway']['counts']}", "employer_flag_count": len(state["employer_scan"]["flags"]),
        "bias_result": state["bias_audit"]["result"], "status": "open", "created_at": utcnow(),
        "review_url": f"/review?run={state['run_id']}",
    }
    ext = get_review_workflow().submit(task)
    task["workflow"] = ext
    get_repository().put("review_tasks", task["task_id"], task, owner_id=state["candidate_id"])
    return {
        "review_task": task,
        "_meta": {"summary": f"Review packet routed to {ext['provider']} ({ext['status']}).", "outputs": {"workflow": ext["provider"], "status": ext["status"]},
                  "message": "Waiting for a counsellor or HR reviewer. No passport can be issued before approval."},
    }


@node("final_review", ["passport"])
def final_review(state: CareerState) -> dict:
    resume = interrupt({"checkpoint": "final_review", "title": "Final review: approve, edit, reject or request more evidence",
                        "required_role": "counsellor", "task": state["review_task"]})
    body, actor = resume["body"], resume.get("actor", "Reviewer")
    applied = []
    pathway = dict(state["pathway"])
    milestones = [dict(m) for m in pathway["milestones"]]
    overrides = {}
    for e in body.get("edits", []):
        target, value = e["target"], e["new_value"]
        if target.startswith("milestone:"):
            mid, field = target.split(":", 1)[1].split(".", 1)
            for m in milestones:
                if m["milestone_id"] == mid and field in ("estimated_hours", "practice_task", "importance", "required_evidence", "why_it_matters"):
                    old = m[field]
                    m[field] = float(value) if field == "estimated_hours" else ([v.strip() for v in value.split(",")] if field == "required_evidence" and isinstance(value, str) else value)
                    if field != "estimated_hours" and field != "importance":
                        m["text_edited"] = True
                    applied.append({"target": target, "old": old, "new": m[field], "reason": e["reason"]})
        elif target in ("recommendation.next_action", "outcome.override"):
            overrides[target] = value
            applied.append({"target": target, "old": None, "new": value, "reason": e["reason"]})
    for a in applied:
        get_repository().append_audit(event_type="human_override", actor=actor, run_id=state["run_id"], candidate_id=state["candidate_id"],
                                      summary=f"Reviewer edited {a['target']}", details=a)
    pathway["milestones"] = milestones
    pathway["total_hours"] = sum(m["estimated_hours"] for m in milestones if m["importance"] == "essential")
    if pathway.get("weekly_hours"):
        pathway["estimated_weeks"] = round(pathway["total_hours"] / pathway["weekly_hours"], 1)
    decision = body["decision"]
    task = dict(state["review_task"])
    task["status"] = {"approve": "approved", "edit": "approved_with_edits", "reject": "rejected", "request_evidence": "evidence_requested"}[decision]
    get_repository().put("review_tasks", task["task_id"], task, owner_id=state["candidate_id"])
    fr = {"decision": decision, "reason": body.get("reason"), "reviewer_note": body.get("reviewer_note"), "actor": actor,
          "reviewer_role": resume.get("role"), "at": utcnow(), "edits": applied, "overrides": overrides, "via": resume.get("via", "EQUALPATH review screen")}
    out = {"final_review": fr, "review_task": task, "_meta": {"actor": actor, "event_type": "human_decision",
           "summary": f"Final review decision: {decision}" + (f" - reason: {body.get('reason')}" if body.get("reason") else ""),
           "outputs": {"decision": decision, "edits": len(applied), "reason": body.get("reason")}}}
    if applied:
        out["pathway"] = pathway
    return out


@node("await_evidence", ["review_routing"])
def await_evidence(state: CareerState) -> dict:
    resume = interrupt({"checkpoint": "evidence_request", "title": "Reviewer requested more evidence", "required_role": "candidate",
                        "request": state["final_review"].get("reason")})
    body, actor = resume["body"], resume.get("actor", "Candidate")
    return {"evidence_requests": [{"request": state["final_review"].get("reason"), "response": body.get("note"), "at": utcnow()}],
            "_meta": {"actor": actor, "summary": "Candidate responded to the evidence request.", "outputs": {"note": body.get("note")}}}


@node("passport", [])
def passport(state: CareerState) -> dict:
    p = compose_passport(state, draft=False)
    get_repository().put("passports", state["run_id"], p, owner_id=state["candidate_id"])
    return {"passport": p, "_meta": {"summary": "Mutual Readiness Passport issued: " + " + ".join(o["outcome"] for o in p["outcomes"]),
                                     "outputs": {"outcomes": [o["outcome"] for o in p["outcomes"]]}}}


def _after_final_review(state: CareerState) -> str:
    d = state["final_review"]["decision"]
    return {"approve": "passport", "edit": "passport", "reject": END, "request_evidence": "await_evidence"}[d]


# ------------------------------------------------------------------ build

_graph = None


def build_graph(checkpointer=None):
    g = StateGraph(CareerState)
    retry = RetryPolicy(max_attempts=2, initial_interval=0.5)
    for name, fn in [("intake", intake), ("skills_discovery", skills_discovery), ("market_intelligence", market_intelligence),
                     ("learning_pathway", learning_pathway), ("employer_readiness", employer_readiness),
                     ("inclusive_matching", inclusive_matching), ("bias_audit", bias_audit), ("review_routing", review_routing),
                     ("passport", passport)]:
        g.add_node(name, fn, retry_policy=retry)
    for name, fn in [("candidate_review", candidate_review), ("role_selection", role_selection), ("final_review", final_review),
                     ("await_evidence", await_evidence)]:
        g.add_node(name, fn)
    g.add_edge(START, "intake")
    g.add_edge("intake", "skills_discovery")
    g.add_edge("skills_discovery", "candidate_review")
    g.add_edge("candidate_review", "market_intelligence")
    g.add_edge("market_intelligence", "role_selection")
    g.add_edge("role_selection", "learning_pathway")
    g.add_edge("role_selection", "employer_readiness")
    g.add_edge(["learning_pathway", "employer_readiness"], "inclusive_matching")
    g.add_edge("inclusive_matching", "bias_audit")
    g.add_edge("bias_audit", "review_routing")
    g.add_edge("review_routing", "final_review")
    g.add_conditional_edges("final_review", _after_final_review, ["passport", "await_evidence", END])
    g.add_edge("await_evidence", "review_routing")
    g.add_edge("passport", END)
    if checkpointer is None:
        conn = sqlite3.connect(get_settings().checkpoint_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    return g.compile(checkpointer=checkpointer)


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def reset_graph(checkpointer=None) -> None:
    global _graph
    _graph = build_graph(checkpointer) if checkpointer is not None else None


def effective_values(run_id: str, values: dict[str, Any]) -> dict[str, Any]:
    return apply_overlays(run_id, values)
