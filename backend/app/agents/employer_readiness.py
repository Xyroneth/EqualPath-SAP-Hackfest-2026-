"""Employer Readiness Agent: flags avoidable barriers in a job ad and classifies what the employer claims.

It flags and classifies evidence. It does not certify that an employer is inclusive. Candidate feedback is
treated as a signal, never as verified fact, and any conflict is routed to human review. The suggested
rewrite must be approved by an HR reviewer before it is used.
"""
from __future__ import annotations

import re

CATEGORY_LABELS = {
    "degree_requirement": "Unnecessary degree or institution requirement",
    "career_gap_requirement": "Career-gap or uninterrupted-experience requirement",
    "age_requirement": "Age limit or 'freshers only' rule",
    "gender_or_family_requirement": "Gender, marital or family-status preference",
    "physical_requirement": "Physical requirement the work does not need",
    "exclusionary_or_vague_wording": "Exclusionary or vague wording",
    "unclear_work_conditions": "Unclear work mode, schedule or location",
    "missing_accessible_interview_info": "Inaccessible or unexplained interview process",
    "missing_accommodation_process": "Missing accommodation request process",
    "missing_return_to_work_support": "Missing return-to-work support",
}

_PRESTIGE = r"top[- ]tier|top institution|premier|prestigious|reputed|reputable|\biit\b|\bnit\b|tier[- ]?1"
_ANCHOR = r"degree|b\.\s?tech|btech|b\.\s?e\.|graduat\w*|colleges?|universit(?:y|ies)|institut\w*"

# Text rules: (category, pattern, severity, explanation, fix). fix None = the sentence is removed; "gap" and "duties" are built per job.
TEXT_RULES = [
    ("degree_requirement", rf"\b(?:{_ANCHOR})\b[^.\n]*(?:{_PRESTIGE})|(?:{_PRESTIGE})[^.\n]*\b(?:{_ANCHOR})\b", "high",
     "Institution prestige is not a role-essential requirement and filters out capable candidates from tier-2 and tier-3 cities.",
     "Skills shown through work samples, projects or experience. No specific degree or college is required."),
    ("career_gap_requirement", r"uninterrupted|continuous (?:work )?experience|gaps? in employment will not|no career (?:breaks?|gaps?)|\bno gaps\b|with gaps[^.\n]*not be considered|without (?:any )?(?:career )?(?:breaks?|gaps?)", "high",
     "Continuity requirements penalise caregivers and returners without measuring current capability.", "gap"),
    ("age_requirement", r"\bage[d]?\b[^.\n]{0,30}\b\d{2}\b|\b\d{2}\s*(?:years|yrs)\s*(?:of age|old)\b|freshers? only|recent graduates only|\b20\d\d\s*(?:or 20\d\d\s*)?pass-?outs?|young (?:and|&) (?:dynamic|energetic)", "high",
     "Age limits and 'freshers only' rules exclude returners and experienced people without measuring skill.", None),
    ("gender_or_family_requirement", r"\b(?:male|female|men|women) (?:candidates? )?(?:only|preferred)|\b(?:only|preferably) (?:male|female)\b|\bunmarried\b|\bmarital status\b|(?:no|without) family (?:commitments|responsibilities)|\bbachelors only\b", "high",
     "Gender, marital or family status is not a job requirement. A preference like this is discriminatory.", None),
    ("physical_requirement", r"physically fit|good (?:physical )?health|able-bodied|perfect (?:eye)?sight|no (?:physical )?disabilit|must be able to (?:lift|stand|walk)", "high",
     "A physical requirement the work does not need shuts out disabled people. Describe the real task instead.", None),
    ("exclusionary_or_vague_wording", r"rockstar|ninja|superstar|culture fit|fast-paced|works? hard,? plays? hard|native english|neutral accent|convent[- ]educated", "medium",
     "Vague or exclusionary wording signals an unwritten profile and invites affinity bias.", "duties"),
    ("missing_accessible_interview_info", r"walk-?in (?:drive|interview)s?|no rescheduling|announced at short notice", "medium",
     "Short-notice walk-in drives with no rescheduling shut out carers and disabled candidates who need to plan ahead.",
     "Interviews: Interviews are booked at least 48 hours ahead and you can ask for another slot."),
]

# Presence rules: flagged when NONE of the patterns appear.
PRESENCE_RULES = [
    ("unclear_work_conditions", "work_mode", [r"\bhybrid\b", r"\bremote\b", r"on-?site", r"office days?", r"work from"], "high",
     "Work mode is not stated. Candidates who cannot relocate or need hybrid work cannot judge fit."),
    ("unclear_work_conditions", "schedule", [r"\d{1,2}[:.]\d{2}\s*(to|-)\s*\d{1,2}[:.]\d{2}", r"working hours", r"core (collaboration )?hours", r"\bshift\b"], "medium",
     "Working hours or schedule expectations are not stated."),
    ("missing_accessible_interview_info", "interviews", [r"interview[^.\n]*(notice|adjust|accessib|accommodat|contact|hours ahead)"], "medium",
     "No accessible interview information or contact is provided."),
    ("missing_accommodation_process", "accommodations", [r"accommodation", r"reasonable adjustment", r"workplace adjustment"], "medium",
     "No process for requesting workplace accommodations is described."),
    ("missing_return_to_work_support", "return_to_work", [r"return-to-work", r"returner", r"returnship", r"career breaks? (are|is) (welcome|encouraged)|career breaks?:"], "low",
     "No return-to-work support is mentioned."),
]

# Which claims each document can support or contradict (work mode is compared by mode, below).
CLAIM_EVIDENCE_RULES = {
    "career_breaks": {"supports": r"career breaks? (?:are|is) (?:welcome|encouraged|evaluated fairly)|do not penalise gaps|returners? (?:are )?welcome",
                      "contradicts": r"uninterrupted|gaps? in employment will not|continuous (?:work )?experience|no career (?:breaks?|gaps?)|freshers? only|pass-?outs?"},
    "return_to_work": {"supports": r"returner programme|return-to-work programme|returnship|return-to-work support", "contradicts": None},
    "accessible_interviews": {"supports": r"interview adjustment|accessible recruiting|interview[^.]*(?:48 hours|adjust|accommodat)",
                              "contradicts": r"walk-?in (?:drive|interview)s? only|no rescheduling|announced at short notice"},
    "accommodation_process": {"supports": r"workplace accommodation|reasonable adjustment|accommodation request", "contradicts": None},
}
_MODES = {"hybrid": r"\bhybrid\b|office days? (?:per|a) week", "remote": r"\bremote\b|work from home", "onsite": r"on-?site|five days a week at|5 days a week at"}
EXPERIENCE_VALIDATION_MIN = 3  # consented, consistent candidate reports needed for experience_validated
NOT_OFFERED = re.compile(r"^\s*(?:no\b|not\b)", re.I)


def _lines(text: str):
    for m in re.finditer(r"[^\n]+", text):
        yield m.start(), m.end(), m.group(0)


def scan_text(text: str) -> list[dict]:
    flags = []
    for cat, pattern, severity, why, fix in TEXT_RULES:
        rx = re.compile(pattern, re.I)
        for start, end, line in _lines(text):
            if rx.search(line):
                flags.append({"flag_id": f"f-{len(flags) + 1}", "category": cat, "label": CATEGORY_LABELS[cat], "severity": severity,
                              "kind": "text", "text": line.strip(" -"), "start": start, "end": end, "explanation": why,
                              "fix": "remove" if fix is None else "rewrite"})
    for cat, aspect, patterns, severity, why in PRESENCE_RULES:
        if not any(re.search(p, text, re.I) for p in patterns):
            flags.append({"flag_id": f"f-{len(flags) + 1}", "category": cat, "label": CATEGORY_LABELS[cat], "severity": severity,
                          "kind": "missing", "aspect": aspect, "text": None, "explanation": why, "fix": "add"})
    return flags


def _modes(text: str) -> set[str]:
    return {m for m, rx in _MODES.items() if re.search(rx, text, re.I)}


def classify_claims(employer: dict, jd_text: str) -> list[dict]:
    out = []
    docs = [("job_description", jd_text)] + [(d["source_id"], d["text"]) for d in employer["policy_documents"]]
    for q in employer["questionnaire"]:
        not_offered = bool(NOT_OFFERED.match(q["answer"]))
        if q["claim_id"] == "work_mode":
            claim_modes = _modes(q["answer"])
            supports = [sid for sid, t in docs if _modes(t) & claim_modes]
            contradicts = [sid for sid, t in docs if _modes(t) and not _modes(t) & claim_modes]
        else:
            rule = CLAIM_EVIDENCE_RULES.get(q["claim_id"], {})
            supports = [] if not_offered else [sid for sid, t in docs if rule.get("supports") and re.search(rule["supports"], t, re.I)]
            contradicts = [] if not_offered else [sid for sid, t in docs if rule.get("contradicts") and re.search(rule["contradicts"], t, re.I)]
        fb = [f for f in employer["candidate_feedback"] if f["claim_id"] == q["claim_id"]]
        consented = [f for f in fb if f["consented"]]
        fb_sup = [f for f in consented if f["sentiment"] == "supports"]
        fb_con = [f for f in consented if f["sentiment"] == "contradicts"]
        if contradicts:
            level = "conflicting_evidence"
        elif len(fb_sup) >= EXPERIENCE_VALIDATION_MIN and not fb_con:
            level = "experience_validated"
        elif supports:
            level = "document_verified"
        else:
            level = "declared"
        needs_review = level == "conflicting_evidence" or bool(fb_con)
        notes, note_codes = [], []
        if not_offered:
            notes.append("The employer says this is not offered.")
            note_codes.append({"code": "not_offered"})
        if contradicts:
            notes.append(f"Employer statement is contradicted by: {', '.join(contradicts)}.")
            note_codes.append({"code": "contradicted_by", "sources": contradicts})
        if fb_sup and level != "experience_validated":
            note_codes.append({"code": "feedback_supports", "n": len(fb_sup)})
        if fb_con:
            notes.append(f"{len(fb_con)} consented candidate report(s) contradict the claim (signal, not fact).")
            note_codes.append({"code": "feedback_contradicts", "n": len(fb_con)})
        if len(fb) > len(consented):
            notes.append(f"{len(fb) - len(consented)} feedback item(s) excluded: no consent.")
            note_codes.append({"code": "feedback_excluded", "n": len(fb) - len(consented)})
        if "job_description" not in supports and level != "conflicting_evidence" and not not_offered:
            notes.append("Not stated in this job description.")
            note_codes.append({"code": "not_in_jd"})
        out.append({
            "claim_id": q["claim_id"], "question": q["question"], "answer": q["answer"], "evidence_level": level, "not_offered": not_offered,
            "supporting_sources": supports, "contradicting_sources": contradicts,
            "sources": [{"source_id": sid, "kind": "job_ad" if sid == "job_description" else "policy",
                         "title": "Job ad" if sid == "job_description" else next(d["title"] for d in employer["policy_documents"] if d["source_id"] == sid),
                         "effect": "supports" if sid in supports else "contradicts"} for sid in dict.fromkeys(supports + contradicts)],
            "consented_feedback": {"supports": len(fb_sup), "contradicts": len(fb_con), "excluded": len(fb) - len(consented)},
            "feedback_quotes": [{"sentiment": f["sentiment"], "summary": f["summary"]} for f in consented][:3],
            "requires_human_review": needs_review, "notes": notes, "note_codes": note_codes,
        })
    return out


def _gap_fix(line: str) -> str:
    m = re.search(r"(\d+)\+?\s*years?", line)
    lead = f"{m.group(1)} years of relevant experience in total" if m else "Relevant experience counts in total"
    return f"{lead}. It does not need to be continuous; career breaks are welcome."


def _claim(employer: dict, claim_id: str) -> str | None:
    q = next((q for q in employer["questionnaire"] if q["claim_id"] == claim_id), None)
    if not q or NOT_OFFERED.match(q["answer"]):
        return None
    return re.sub(r"^Yes[.,]\s*", "", q["answer"]).rstrip(".") + "."


def _rewrite(job: dict, flags: list[dict], employer: dict) -> tuple[str, list[dict]]:
    """Fix flagged sentences in place, add what is missing from the employer's own answers, and list every change."""
    text = job["text"]
    by_line: dict[str, list[dict]] = {}
    for f in flags:
        if f["kind"] == "text":
            by_line.setdefault(f["text"], []).append(f)
    changes, out = [], []
    for line in text.split("\n"):
        key = line.strip(" -")
        fs = by_line.get(key)
        if line.strip() == "Requirements:":
            out.append("What you need (role-essential):")
            continue
        if re.match(r"^\s*Apply\b", line):
            continue
        if not fs:
            out.append(line)
            continue
        fixes = []
        for f in fs:
            rule = next(r for r in TEXT_RULES if r[0] == f["category"])
            fix = rule[4]
            if fix == "gap":
                fix = _gap_fix(line)
            elif fix == "duties":
                fix = f"How you will work: {job.get('duties') or 'You work with your team, share progress in writing and plan your week around agreed priorities.'}"
            if fix:
                fixes.append(fix)
        cats = [f["category"] for f in fs]
        if fixes:
            prefix = "- " if line.lstrip().startswith("-") else ""
            new = prefix + fixes[0]
            out.append(new)
            changes.append({"kind": "replaced", "categories": cats, "before": key, "after": new.strip(" -")})
        else:
            changes.append({"kind": "removed", "categories": cats, "before": key, "after": None})
    body = "\n".join(out).rstrip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    missing = {f.get("aspect") for f in flags if f["kind"] == "missing"}
    contact = employer.get("recruiting_contact") or "[accessible recruiting contact - employer to provide]"
    extra = []
    if "work_mode" in missing:
        extra.append(("unclear_work_conditions", "Work mode and location: " + (_claim(employer, "work_mode") or "[employer to specify]")))
    if "schedule" in missing:
        hours = next((m.group(0) for d in employer["policy_documents"] for m in [re.search(r"(?:core collaboration|standard working|working) hours[^.]*", d["text"], re.I)] if m), None)
        extra.append(("unclear_work_conditions", "Working hours: " + (hours[0].upper() + hours[1:] + "." if hours else "[employer to specify before publishing].")))
    if "return_to_work" in missing:
        rtw = _claim(employer, "return_to_work")
        offer = re.sub(r"^(?:A|An)\s", lambda m: "We offer " + m.group(0).lower(), rtw) if rtw and re.search(r"programme|mentor|buddy", rtw, re.I) else None
        extra.append(("missing_return_to_work_support", "Career breaks: Candidates with career breaks are encouraged to apply. "
                      + (offer or "We assess current, demonstrated skills.")))
    if "interviews" in missing and "accommodations" in missing:
        extra.append(("missing_accessible_interview_info", "Interviews and accommodations: Interviews are scheduled with at least 48 hours notice. "
                      f"To request an interview adjustment or a workplace accommodation, contact {contact}."))
    elif "interviews" in missing:
        extra.append(("missing_accessible_interview_info", f"Interviews: Interviews are scheduled with at least 48 hours notice. To request an interview adjustment, contact {contact}."))
    elif "accommodations" in missing:
        extra.append(("missing_accommodation_process", f"Workplace accommodations: To request a workplace accommodation, contact {contact}. We reply within two working days."))
    for cat, para in extra:
        body += "\n\n" + para
        changes.append({"kind": "added", "categories": [cat], "before": None, "after": para})
    body += "\n\nApply with your resume or work samples."
    return body, changes


def ad_facts(text: str) -> dict:
    """Small 'at a glance' facts read from the ad itself (never guessed)."""
    modes = sorted(_modes(text))
    hours = re.search(r"\d{1,2}[:.]\d{2}\s*(?:to|-)\s*\d{1,2}[:.]\d{2}(?:\s*IST)?", text)
    reqs, in_reqs = [], False
    for line in text.split("\n"):
        s = line.strip()
        if re.match(r"^(Requirements|What you need)", s):
            in_reqs = True
            continue
        if in_reqs and s.startswith("-"):
            reqs.append(s.strip(" -"))
        elif in_reqs and s:
            in_reqs = False
    return {"work_modes": modes, "hours": hours.group(0) if hours else None, "requirements": reqs}


def assess_employer(job: dict, employer: dict) -> dict:
    flags = scan_text(job["text"])
    claims = classify_claims(employer, job["text"])
    by_cat = {c: [f for f in flags if f["category"] == c] for c in CATEGORY_LABELS}
    high = sum(1 for f in flags if f["severity"] == "high")
    rewrite, changes = _rewrite(job, flags, employer) if flags else (None, [])
    facts = ad_facts(job["text"])
    facts["requirement_flags"] = [[f["category"] for f in flags if f["kind"] == "text" and f["text"] == r] for r in facts["requirements"]]
    return {
        "job_id": job["job_id"], "role_id": job.get("role_id"), "job_title": job["title"], "version_label": job["version_label"],
        "employer": employer["name"], "employer_id": employer["employer_id"], "employer_short": employer.get("short_name", employer["name"]),
        "employer_city": employer.get("city"), "employer_industry": employer.get("industry"),
        "job_text": job["text"], "facts": facts,
        "flags": flags, "flags_by_category": {c: len(v) for c, v in by_cat.items()},
        "categories_checked": [{"category": c, "label": l, "flagged": bool(by_cat[c])} for c, l in CATEGORY_LABELS.items()],
        "claims": claims,
        "conflicts_requiring_review": [c["claim_id"] for c in claims if c["requires_human_review"]],
        "suggested_rewrite": {"text": rewrite, "changes": changes, "status": "pending_hr_approval" if flags else "not_needed"},
        "employer_action_required": bool(flags), "high_count": high, "categories_flagged": sum(1 for v in by_cat.values() if v),
        "categories_total": len(CATEGORY_LABELS),
        "conflict_count": sum(1 for c in claims if c["requires_human_review"]),
        "summary": f"{len(flags)} barrier flag(s) ({high} high severity) across {sum(1 for v in by_cat.values() if v)} of {len(CATEGORY_LABELS)} categories; "
                   f"{sum(1 for c in claims if c['requires_human_review'])} employer claim(s) need human review.",
        "disclaimer": "The agent flags and classifies evidence. It does not certify that an employer is inclusive.",
        "data_label": "Seeded job ad and simulated employer data.",
    }
