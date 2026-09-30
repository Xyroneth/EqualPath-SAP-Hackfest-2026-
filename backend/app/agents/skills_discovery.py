"""Skills Discovery Agent - the functional core agent.

Turns resumes, work samples, projects and learning records into evidence-backed capability records.
Guarantees (enforced in code, independent of the model):
  * every record carries a short quote that is found verbatim in the cited (redacted) source;
  * verification status is derived from the *type* of the source, never from model confidence;
  * a claim that appears only in candidate-authored text stays `self_declared`;
  * `assessed` / `externally_verified` can only be set by later human-reviewed events, never here.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.agents.common import normalise_text, taxonomy
from app.privacy import redact
from app.providers.llm import DemoProvider, LLMError, LLMProvider
from app.schemas import (
    PROFICIENCY_ORDER,
    SELF_AUTHORED_TYPES,
    VERIFICATION_ORDER,
    EvidenceDocument,
    LLMSkillResponse,
    SkillRecord,
)

MAX_LLM_ATTEMPTS = 2

SYSTEM_PROMPT = """You are the Skills Discovery Agent of EQUALPATH, a skills-first career platform.
Extract job-relevant capabilities from the candidate evidence you are given.

Rules:
1. Only extract a capability if a document contains text that shows it. Quote that text EXACTLY
   (copy 8-200 characters verbatim, keep placeholders such as [NAME]) in "evidence_quote" and give its "source_id".
2. Prefer normalized_skill keys from the taxonomy provided. Use "other.<snake_case>" only if nothing fits.
3. "proficiency" is one of awareness | basic | intermediate | advanced, judged from the evidence, not from adjectives.
4. "confidence" (0-1) is your confidence that the quote shows the capability. It is NOT verification.
5. Do not judge verification. Do not infer skills from gender, age, name, location or career breaks.
6. Return one record per (skill, source) you find. Return JSON only:
{"skills":[{"skill_name":str,"normalized_skill":str,"category":"technical|domain|professional|learning",
"proficiency":str,"evidence_quote":str,"source_id":str,"confidence":float,"adjacent_skills":[str]}]}"""


def _redacted_documents(documents: list[EvidenceDocument], names: list[str]) -> tuple[list[EvidenceDocument], dict[str, int]]:
    out, totals = [], {}
    for d in documents:
        r = redact(d.text, names)
        for k, v in r.counts.items():
            totals[k] = totals.get(k, 0) + v
        out.append(d.model_copy(update={"text": r.text}))
    return out, totals


def status_for_source(evidence_type: str) -> str:
    return "self_declared" if evidence_type in SELF_AUTHORED_TYPES else "source_supported"


def locate_quote(quote: str, text: str) -> bool:
    """True if the quote (or each '...'-separated fragment of it) occurs in the source text."""
    haystack = normalise_text(text)
    fragments = [normalise_text(f) for f in re.split(r"\.\.\.|…", quote) if len(f.strip()) >= 6]
    return bool(fragments) and all(f.strip(" .\"'") in haystack for f in fragments)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -\t\u2022") for p in parts if len(p.strip(" \u2022")) > 6]


def _claimed_level(sentence: str) -> str | None:
    """Level the candidate explicitly claims in their own words, or None if no level is stated."""
    s = sentence.lower()
    if re.search(r"\b(expert|advanced)\b", s):
        return "advanced"
    if re.search(r"\b(proficient|strong|hands-on)\b", s):
        return "intermediate"
    if re.search(r"\b(beginner|basic|familiar)\b", s):
        return "basic"
    return None


# ---------------------------------------------------------------- deterministic engine

def _window(sentence: str, patterns: list[re.Pattern]) -> str:
    """A verbatim excerpt (about 200 characters, cut at word boundaries) around the first pattern match of a very long line."""
    m = next((mm for mm in (p.search(sentence) for p in patterns) if mm), None)
    start = max(0, (m.start() if m else 0) - 60)
    if start:
        start = sentence.rfind(" ", 0, start) + 1
    end = min(len(sentence), start + 200)
    if end < len(sentence):
        end = sentence.rfind(" ", start, end)
    return sentence[start:end].strip()


def _deterministic_candidates(docs: list[EvidenceDocument]) -> list[dict]:
    found: list[dict] = []
    for doc in docs:
        sentences = _sentences(doc.text)
        for key, spec in taxonomy().items():
            patterns = [re.compile(p, re.I) for p in spec["patterns"]]
            hits = [(s, sum(1 for p in patterns if p.search(s))) for s in sentences]
            hits = [h for h in hits if h[1] > 0]
            if not hits:
                continue
            distinct = sum(1 for p in patterns if p.search(doc.text))
            best = max(hits, key=lambda h: (h[1], len(h[0]) < 220, -len(h[0])))[0]
            quote = best if len(best) <= 220 else _window(best, patterns)
            base = 0.72 if doc.evidence_type in SELF_AUTHORED_TYPES else 0.8
            found.append({
                "skill_name": spec["skill_name"], "normalized_skill": key, "category": spec["category"],
                "proficiency": (_claimed_level(best) or "basic") if doc.evidence_type in SELF_AUTHORED_TYPES else "basic",
                "_explicit_claim": _claimed_level(best) if doc.evidence_type in SELF_AUTHORED_TYPES else None,
                "evidence_quote": quote, "source_id": doc.source_id,
                "confidence": round(min(0.95, base + 0.06 * (distinct - 1)), 2),
                "adjacent_skills": spec["adjacent_skills"],
            })
    return found


# ---------------------------------------------------------------- LLM engine

def _llm_candidates(provider: LLMProvider, docs: list[EvidenceDocument]) -> tuple[list[dict], int, list[str]]:
    tax = [{"normalized_skill": k, "skill_name": v["skill_name"], "category": v["category"]} for k, v in taxonomy().items()]
    payload = json.dumps({
        "taxonomy": tax,
        "documents": [{"source_id": d.source_id, "evidence_type": d.evidence_type, "date": d.date, "text": d.text} for d in docs],
    }, ensure_ascii=False)
    errors: list[str] = []
    for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
        user = payload if not errors else payload + "\n\nYour previous answer was rejected: " + errors[-1] + " Return valid JSON only."
        try:
            raw = provider.complete_json(SYSTEM_PROMPT, user)
            parsed = LLMSkillResponse.model_validate(raw)
            return [c.model_dump() for c in parsed.skills], attempt, errors
        except (LLMError, ValidationError) as exc:
            errors.append(str(exc)[:300])
    raise LLMError("; ".join(errors))


# ---------------------------------------------------------------- validation + merge (shared by both engines)

def _validate(cands: list[dict], docs_by_id: dict[str, EvidenceDocument], method: str) -> tuple[list[SkillRecord], list[dict]]:
    accepted: list[SkillRecord] = []
    rejected: list[dict] = []
    tax = taxonomy()
    for c in cands:
        doc = docs_by_id.get(c.get("source_id", ""))
        if doc is None:
            rejected.append({"skill_name": c.get("skill_name"), "reason": f"unknown source_id '{c.get('source_id')}'"})
            continue
        quote = (c.get("evidence_quote") or "").strip()
        if len(quote) < 8 or not locate_quote(quote, doc.text):
            rejected.append({"skill_name": c.get("skill_name"), "source_id": doc.source_id,
                             "reason": "evidence quote not found verbatim in the cited source"})
            continue
        key = (c.get("normalized_skill") or "").strip().lower().replace(" ", "_")
        if key not in tax:
            match = next((k for k, v in tax.items() if v["skill_name"].lower() == (c.get("skill_name") or "").lower()), None)
            key = match or (key if key.startswith("other.") else f"other.{re.sub(r'[^a-z0-9]+', '_', key or 'skill').strip('_')}")
        allowed = status_for_source(doc.evidence_type)
        notes = []
        claimed = c.get("verification_status")
        if claimed and claimed in VERIFICATION_ORDER and VERIFICATION_ORDER[claimed] > VERIFICATION_ORDER[allowed]:
            notes.append(f"Model suggested '{claimed}'; blocked. Status is derived from the source type ({doc.evidence_type}).")
        prof = c.get("proficiency") if c.get("proficiency") in PROFICIENCY_ORDER else "basic"
        spec = tax.get(key, {})
        try:
            accepted.append(SkillRecord(
                skill_name=spec.get("skill_name") or c.get("skill_name") or key,
                normalized_skill=key,
                category=spec.get("category") or c.get("category") or "technical",
                proficiency=prof,
                evidence_type=doc.evidence_type,
                evidence_quote=quote[:400],
                source_id=doc.source_id,
                recency=doc.date,
                confidence=float(c.get("confidence", 0.5)),
                verification_status=allowed,
                adjacent_skills=spec.get("adjacent_skills") or c.get("adjacent_skills") or [],
                extraction_method=method,
                notes=notes,
                claimed_proficiency=c.get("_explicit_claim") if method == "deterministic" else (prof if doc.evidence_type in SELF_AUTHORED_TYPES else None),
            ))
        except ValidationError as exc:
            rejected.append({"skill_name": c.get("skill_name"), "reason": f"schema validation failed: {exc.errors()[0]['msg']}"})
    return accepted, rejected


def _merge(records: list[SkillRecord]) -> list[SkillRecord]:
    """One record per capability: strongest evidence wins, other sources are listed; proficiency is evidence-capped."""
    by_key: dict[str, list[SkillRecord]] = {}
    for r in records:
        by_key.setdefault(r.normalized_skill, []).append(r)
    merged: list[SkillRecord] = []
    for key, recs in by_key.items():
        recs.sort(key=lambda r: (VERIFICATION_ORDER[r.verification_status], r.confidence, r.recency or ""), reverse=True)
        best = recs[0].model_copy(deep=True)
        supported_sources = sorted({r.source_id for r in recs if r.verification_status != "self_declared"})
        best.additional_sources = sorted({r.source_id for r in recs} - {best.source_id})
        claimed_levels = [r.claimed_proficiency for r in recs if r.evidence_type in SELF_AUTHORED_TYPES and r.claimed_proficiency]
        if best.verification_status == "self_declared":
            # Keep the candidate's own claim visible, but it is only a claim.
            best.claimed_proficiency = max(claimed_levels, key=PROFICIENCY_ORDER.get) if claimed_levels else None
            best.proficiency = best.claimed_proficiency or best.proficiency
            best.notes.append("Mentioned only in candidate-authored text. Remains self-declared until evidence is submitted and reviewed.")
        else:
            # Evidence-capped proficiency: 1 supporting source -> basic, 2+ -> intermediate. Advanced needs an assessment.
            evidence_level = "intermediate" if len(supported_sources) >= 2 else "basic"
            model_level = best.proficiency
            best.proficiency = min(evidence_level, model_level, key=PROFICIENCY_ORDER.get) if best.extraction_method != "deterministic" else evidence_level
            best.claimed_proficiency = max(claimed_levels, key=PROFICIENCY_ORDER.get) if claimed_levels else None
        # Recency comes from the evidence itself; a resume date only counts when nothing else supports the skill.
        dated = [r for r in recs if r.verification_status != "self_declared"] or recs
        best.recency = max((r.recency or "" for r in dated), default=None) or None
        merged.append(best)
    order = {"technical": 0, "domain": 1, "professional": 2, "learning": 3}
    merged.sort(key=lambda r: (order.get(r.category, 9), -VERIFICATION_ORDER[r.verification_status], r.skill_name))
    return merged


def discover_skills(documents: list[EvidenceDocument], provider: LLMProvider, candidate_names: list[str] | None = None) -> dict[str, Any]:
    """Run the agent. Returns validated skill records plus full provenance for the audit log."""
    redacted, redaction_counts = _redacted_documents(documents, candidate_names or [])
    docs_by_id = {d.source_id: d for d in redacted}
    info = provider.info()
    attempts, errors, fallback_reason = 0, [], None
    method = "deterministic"
    if isinstance(provider, DemoProvider) or not provider.is_live:
        cands = _deterministic_candidates(redacted)
    else:
        try:
            cands, attempts, errors = _llm_candidates(provider, redacted)
            method = f"llm:{info.kind}"
        except LLMError as exc:
            fallback_reason = f"LLM output failed validation or transport after {MAX_LLM_ATTEMPTS} attempts ({str(exc)[:160]}). Deterministic engine used."
            cands = _deterministic_candidates(redacted)
    accepted, rejected = _validate(cands, docs_by_id, method)
    merged = _merge(accepted)
    return {
        "skills": [s.model_dump() for s in merged],
        "rejected": rejected,
        "method": method,
        "provider": info.as_dict(),
        "llm_attempts": attempts,
        "llm_errors": errors,
        "fallback_reason": fallback_reason,
        "redaction": redaction_counts,
        "documents_processed": len(documents),
        "self_declared_count": sum(1 for s in merged if s.verification_status == "self_declared"),
        "source_supported_count": sum(1 for s in merged if s.verification_status == "source_supported"),
        "mean_confidence": round(sum(s.confidence for s in merged) / len(merged), 2) if merged else 0.0,
    }
