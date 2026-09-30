"""EQUALPATH API (FastAPI)."""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from app import documents as docs
from app import runner, tokens
from app.access import EVIDENCE_ROLES, PERSONAL_VIEW_ROLES, scrub_run_view
from app.agents.bias_audit import monitoring_prototype, try_twin
from app.agents.common import employer_for, jobs_data, role_by_id, roles
from app.agents.employer_readiness import assess_employer, scan_text
from app.agents.skills_discovery import discover_skills
from app.config import get_settings, load_json, running_on_btp
from app.graph import get_graph
from app.passport import compose_passport, employer_copy, passport_html
from app.providers.identity import (ROLE_LABELS, Principal, authenticate, current_principal, default_passwords_in_use, get_identity_provider,
                                    require_roles)
from app.providers.learning_catalog import get_learning_catalog
from app.providers.llm import get_llm_provider
from app.providers.repository import get_repository, repository_note, utcnow
from app.providers.review_workflow import get_review_workflow
from app.schemas import (CandidateReviewBody, ClaimResponseBody, CreateCandidateBody, EmployerDecisionBody, EvidenceDecisionBody, EvidenceResponseBody,
                         FairnessReviewBody, FairnessTryBody, FinalReviewBody, JDRewriteDecisionBody, LoginBody, MilestoneEvidenceBody, RoleSelectionBody, ScanBody,
                         SkillsDiscoveryBody, StartRunBody, TextDocumentBody, UpdateCandidateBody)
from app.security import decrypt, encrypt, production_key_configured
from app.seed import load_persona, seed_files

app = FastAPI(title="EQUALPATH API", version="1.1.0",
              description="Skills-first multi-agent Career Orchestrator - SAP Hackfest 2026 prototype. Consumable from SAP Build Apps / SAP Build Process Automation.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_methods=["*"], allow_headers=["*"])

audit = lambda **kw: get_repository().append_audit(**kw)  # noqa: E731

ROLE_INFO = [
    {"role": "candidate", "requires_password": False},
    {"role": "counsellor", "requires_password": True},
    {"role": "hr_reviewer", "requires_password": True},
    {"role": "auditor", "requires_password": True},
]


def _actor(p: Principal) -> str:
    return f"{p.label} ({p.user_id})"


def _run_or_404(run_id: str) -> dict:
    view = runner.run_view(run_id)
    if view is None:
        raise HTTPException(404, "run not found")
    return view


def _expect_checkpoint(run_id: str, checkpoint: str) -> dict:
    view = _run_or_404(run_id)
    if view["run"]["status"] == "running":
        raise HTTPException(409, "run is still executing")
    it = view["interrupt"]
    if not it or it["checkpoint"] != checkpoint:
        raise HTTPException(409, f"run is not waiting at '{checkpoint}' (waiting at: {it['checkpoint'] if it else 'nothing'})")
    return view


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ------------------------------------------------------------------ sign-in

@app.get("/api/auth/roles")
def auth_roles():
    return {"roles": [{**r, "label": ROLE_LABELS[r["role"]]} for r in ROLE_INFO], "mode": get_identity_provider().kind,
            "default_passwords": default_passwords_in_use()}


@app.post("/api/auth/login")
def auth_login(body: LoginBody, request: Request):
    try:
        session = authenticate(body.role, body.password, _client(request))
    except HTTPException as exc:
        if body.role != "candidate":
            audit(event_type="auth_failed", actor=ROLE_LABELS[body.role], run_id=None, candidate_id=None,
                  summary=f"Failed sign-in attempt for role {ROLE_LABELS[body.role]}", details={"status": exc.status_code})
        raise
    if body.role != "candidate":
        audit(event_type="auth_login", actor=ROLE_LABELS[body.role], run_id=None, candidate_id=None, summary=f"{ROLE_LABELS[body.role]} signed in", details={})
    return session


@app.get("/api/me")
def me(p: Principal = Depends(current_principal)):
    return {"user_id": p.user_id, "role": p.role, "label": p.label, "source": p.source}


# ------------------------------------------------------------------ system

@app.get("/api/health")
def health():
    return {"ok": True, "time": utcnow()}


@app.get("/api/system/status")
def system_status():
    s = get_settings()
    info = get_llm_provider().info()
    repo = get_repository()
    wf = get_review_workflow()
    services = [
        {"service": "SAP AI Core - generative AI hub", "use": "Skills Discovery and Learning Pathway prompts (PII-redacted)",
         "state": "connected" if info.kind == "sap_ai_core" else "adapter_ready",
         "detail": info.detail if info.kind == "sap_ai_core" else "SAPAIProvider implemented (orchestration + foundation-model modes). Set AICORE_* variables to activate."},
        {"service": "SAP UI5 Web Components", "use": "Fiori-style accessible user interface", "state": "in_use", "detail": "@ui5/webcomponents-react, SAP Horizon theme (light and dark)."},
        {"service": "SAP Learning Hub, student edition", "use": "Curated learning catalog, deep links, evidence-building milestones",
         "state": "curated_catalog", "detail": f"{len(get_learning_catalog().all())} curated assets with deep links. No private API, scraping or progress sync."},
        {"service": "SAP Build Process Automation", "use": "Final human review approval workflow",
         "state": "connected" if wf.live else "adapter_ready",
         "detail": "Review tasks are started in SAP Build Process Automation and decisions call back into EQUALPATH." if wf.live else "Adapter + process design in sap-build/. Set SBPA_* variables to activate; local review queue is used meanwhile."},
        {"service": "SAP Build Apps / SAP Build Work Zone", "use": "Counsellor mobile review app and launchpad tile", "state": "deployment_ready",
         "detail": "OpenAPI at /openapi.json for SAP Build Apps; Work Zone tile guide in sap-build/. Not connected in this demo."},
        {"service": "SAP HANA Cloud", "use": "Enterprise persistence adapter", "state": "connected" if repo.kind == "hana" else "adapter_ready",
         "detail": repository_note() if repo.kind == "hana" else f"HANARepository implemented (hdbcli). Active store: {repository_note()}."},
        {"service": "SAP BTP, Cloud Foundry runtime", "use": "Deployment target", "state": "running_on_btp" if running_on_btp() else "deployment_ready",
         "detail": "manifest.yml and mta.yaml included." + (" Running on SAP BTP now." if running_on_btp() else " Currently running locally.")},
        {"service": "XSUAA / SAP Cloud Identity Services", "use": "Role-based access", "state": "connected" if get_identity_provider().kind == "xsuaa" else "adapter_ready",
         "detail": "xs-security.json with Candidate, Counsellor, HR Reviewer, Auditor role templates. Local password sign-in is active." if get_identity_provider().kind != "xsuaa" else "JWT validated via XSUAA."},
    ]
    return {
        "provider": info.as_dict(),
        "repository": {"kind": repo.kind, "note": repository_note()},
        "review_workflow": {"kind": wf.kind, "live": wf.live},
        "identity": get_identity_provider().kind,
        "encryption": "production key" if production_key_configured() else "development key (set DATA_ENCRYPTION_KEY)",
        "sap_services": services,
        "data_labels": {"persona": "Fictional persona, locally seeded", "roles": "Local role catalog, illustrative",
                        "jobs": "Seeded job descriptions", "employer": "Simulated employer data", "monitoring": "Synthetic illustration"},
        "roles": ROLE_LABELS,
        "accepted_files": docs.ACCEPT,
        "max_upload_mb": docs.MAX_BYTES // (1024 * 1024),
    }


# ------------------------------------------------------------------ seed data

@app.get("/api/demo/persona")
def demo_persona(p: Principal = Depends(require_roles("candidate"))):
    """The fictional demo persona: only the (open) Candidate role may load it, because it includes her private note."""
    persona = load_persona()
    return {"profile": persona["profile"], "documents": [{k: d[k] for k in ("source_id", "title", "evidence_type", "date", "file")} for d in persona["documents"]]}


@app.get("/api/roles")
def list_roles():
    return {"roles": roles(), "data_label": load_json("roles.json")["_data_label"]}


@app.get("/api/jobs")
def list_jobs():
    d = jobs_data()
    return {"jobs": d["jobs"], "employers": d["employers"], "data_label": d["_data_label"]}


@app.get("/api/jobs/{job_id}/scan")
def scan_job(job_id: str):
    job = next((j for j in jobs_data()["jobs"] if j["job_id"] == job_id), None)
    if not job:
        raise HTTPException(404, "job not found")
    return assess_employer(job, employer_for(job))


@app.get("/api/learning/assets")
def learning_assets():
    return {"assets": get_learning_catalog().all(), "provider": get_learning_catalog().kind, "note": load_json("learning_assets.json")["_verification_process"]}


# ------------------------------------------------------------------ candidates and evidence

def _candidate_or_404(cid: str) -> dict:
    c = get_repository().get("candidates", cid)
    if not c:
        raise HTTPException(404, "candidate not found")
    return c


def _public_doc(d: dict) -> dict:
    return {k: d.get(k) for k in ("source_id", "title", "evidence_type", "date", "filename", "mime", "size", "kind", "seed", "added_at")} | {"text_chars": len(d.get("text", ""))}


def _store_file(cid: str, source_id: str, filename: str, mime: str, data: bytes) -> None:
    get_repository().put("files", f"{cid}:{source_id}", {"filename": filename, "mime": mime, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                                       "data_b64": base64.b64encode(data).decode()}, owner_id=cid)


def _load_file(cid: str, source_id: str) -> tuple[dict, bytes]:
    rec = get_repository().get("files", f"{cid}:{source_id}")
    if not rec:
        raise HTTPException(404, "file not found")
    return rec, base64.b64decode(rec["data_b64"])


def _clean_profile(profile: dict, cid: str) -> dict:
    """Move the private accommodation note out of the profile into encrypted storage."""
    profile = copy.deepcopy(profile)
    acc = profile.get("accommodations") or {}
    if "private_note" in acc:
        note = acc.pop("private_note")
        if note:
            get_repository().put("sensitive", cid, {"candidate_id": cid, "private_note_encrypted": encrypt(note),
                                                    "note": "Encrypted; never shared with employers or sent to an LLM."}, owner_id=cid)
        else:
            get_repository().put("sensitive", cid, {"candidate_id": cid, "private_note_encrypted": None}, owner_id=cid)
    return profile


def _candidate_view(c: dict, role: str) -> dict:
    out = {"candidate_id": c["candidate_id"], "profile": copy.deepcopy(c["profile"]), "consent": c["consent"], "documents": [_public_doc(d) for d in c["documents"]]}
    if role == "candidate":
        sens = get_repository().get("sensitive", c["candidate_id"]) or {}
        tok = sens.get("private_note_encrypted")
        out["profile"].setdefault("accommodations", {})["private_note"] = decrypt(tok) if tok else ""
    return out


@app.post("/api/candidates")
def create_candidate(body: CreateCandidateBody, p: Principal = Depends(require_roles("candidate"))):
    if not body.consent.process_profile:
        raise HTTPException(403, "Explicit consent to process the profile is required.")
    cid = f"cand-{uuid.uuid4().hex[:10]}"
    documents = []
    if body.seed_persona == "priya":
        for doc, data in seed_files():
            documents.append({**doc, "added_at": utcnow()})
            _store_file(cid, doc["source_id"], doc["filename"], doc["mime"], data)
    profile = _clean_profile(body.profile, cid)
    get_repository().put("candidates", cid, {"candidate_id": cid, "profile": profile, "documents": documents, "consent": body.consent.model_dump(), "created_at": utcnow()}, owner_id=cid)
    audit(event_type="consent_recorded", actor=_actor(p), run_id=None, candidate_id=cid, summary="Candidate consent recorded", details={"consent": body.consent.model_dump()})
    audit(event_type="profile_created", actor=_actor(p), run_id=None, candidate_id=cid, summary=f"Profile created with {len(documents)} evidence documents",
          details={"documents": [d["source_id"] for d in documents]})
    return {"candidate_id": cid}


@app.put("/api/candidates/{cid}")
def update_candidate(cid: str, body: UpdateCandidateBody, p: Principal = Depends(require_roles("candidate"))):
    c = _candidate_or_404(cid)
    if body.consent is not None:
        if not body.consent.process_profile:
            raise HTTPException(403, "Explicit consent to process the profile is required.")
        c["consent"] = body.consent.model_dump()
        audit(event_type="consent_update", actor=_actor(p), run_id=None, candidate_id=cid, summary="Candidate updated consent", details={"consent": c["consent"]})
    if body.profile is not None:
        c["profile"] = _clean_profile(body.profile, cid)
        audit(event_type="profile_updated", actor=_actor(p), run_id=None, candidate_id=cid, summary="Candidate updated their profile", details={})
    get_repository().put("candidates", cid, c, owner_id=cid)
    return {"ok": True}


@app.get("/api/candidates/{cid}")
def get_candidate(cid: str, p: Principal = Depends(require_roles("candidate", "counsellor"))):
    return _candidate_view(_candidate_or_404(cid), p.role)


@app.get("/api/candidates/{cid}/documents")
def list_documents(cid: str, p: Principal = Depends(require_roles(*EVIDENCE_ROLES))):
    return {"documents": [_public_doc(d) for d in _candidate_or_404(cid)["documents"]], "accepted": docs.ACCEPT, "max_mb": docs.MAX_BYTES // (1024 * 1024)}


def _new_source_id(existing: list[dict], name: str) -> str:
    taken = {d["source_id"] for d in existing}
    if name not in taken:
        return name
    stem, dot, ext = name.rpartition(".")
    for i in range(2, 50):
        cand = f"{stem}-{i}.{ext}" if dot else f"{name}-{i}"
        if cand not in taken:
            return cand
    return f"{uuid.uuid4().hex[:6]}-{name}"


@app.post("/api/candidates/{cid}/documents/upload")
async def upload_document(cid: str, file: UploadFile = File(...), title: str = Form(""), evidence_type: str = Form("work_sample"), description: str = Form(""),
                          p: Principal = Depends(require_roles("candidate"))):
    c = _candidate_or_404(cid)
    if evidence_type not in ("resume", "work_sample", "project", "certificate"):
        raise HTTPException(422, "Unknown evidence type.")
    data = await file.read(docs.MAX_BYTES + 1)
    try:
        name, mime, kind = docs.validate_upload(file.filename or "document", data)
        text, kind = docs.extract_text(name, data)
        if kind == "image":
            if len(description.strip()) < 10:
                raise docs.DocumentError("Images cannot be read automatically. Please describe what the image shows (at least 10 characters).")
            text = description.strip()
    except docs.DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc
    sid = _new_source_id(c["documents"], name)
    doc = {"source_id": sid, "title": (title or PurePathStem(name)).strip()[:120], "evidence_type": evidence_type, "date": datetime.now(timezone.utc).strftime("%Y-%m"),
           "filename": name, "mime": mime, "size": len(data), "kind": kind, "seed": False, "added_at": utcnow(), "text": text}
    _store_file(cid, sid, name, mime, data)
    c["documents"].append(doc)
    get_repository().put("candidates", cid, c, owner_id=cid)
    audit(event_type="evidence_added", actor=_actor(p), run_id=None, candidate_id=cid, summary=f"Evidence file added: {sid}", details={"source_id": sid, "kind": kind, "size": len(data)})
    return _public_doc(doc)


def PurePathStem(name: str) -> str:  # noqa: N802 - small helper kept next to its only use
    return name.rsplit(".", 1)[0]


@app.post("/api/candidates/{cid}/documents/text")
def add_text_document(cid: str, body: TextDocumentBody, p: Principal = Depends(require_roles("candidate"))):
    c = _candidate_or_404(cid)
    name = docs.safe_name(body.title.lower().replace(" ", "-")) + ".txt"
    sid = _new_source_id(c["documents"], name)
    data = body.text.encode("utf-8")
    doc = {"source_id": sid, "title": body.title.strip(), "evidence_type": body.evidence_type, "date": datetime.now(timezone.utc).strftime("%Y-%m"), "filename": sid,
           "mime": "text/plain", "size": len(data), "kind": "text", "seed": False, "added_at": utcnow(), "text": body.text[:docs.MAX_TEXT]}
    _store_file(cid, sid, sid, "text/plain", data)
    c["documents"].append(doc)
    get_repository().put("candidates", cid, c, owner_id=cid)
    audit(event_type="evidence_added", actor=_actor(p), run_id=None, candidate_id=cid, summary=f"Evidence text added: {sid}", details={"source_id": sid, "kind": "text"})
    return _public_doc(doc)


@app.delete("/api/candidates/{cid}/documents/{sid}")
def delete_document(cid: str, sid: str, p: Principal = Depends(require_roles("candidate"))):
    c = _candidate_or_404(cid)
    if not any(d["source_id"] == sid for d in c["documents"]):
        raise HTTPException(404, "document not found")
    c["documents"] = [d for d in c["documents"] if d["source_id"] != sid]
    get_repository().put("candidates", cid, c, owner_id=cid)
    get_repository().delete("files", f"{cid}:{sid}")
    audit(event_type="evidence_removed", actor=_actor(p), run_id=None, candidate_id=cid, summary=f"Evidence removed: {sid}", details={"source_id": sid})
    return {"ok": True}


@app.post("/api/candidates/{cid}/documents/{sid}/view-link")
def document_view_link(cid: str, sid: str, p: Principal = Depends(require_roles(*EVIDENCE_ROLES))):
    """A short-lived link so the file can open in a new browser tab (tabs cannot send the Authorization header)."""
    c = _candidate_or_404(cid)
    doc = next((d for d in c["documents"] if d["source_id"] == sid), None)
    if not doc:
        raise HTTPException(404, "document not found")
    audit(event_type="evidence_viewed", actor=_actor(p), run_id=None, candidate_id=cid, summary=f"{p.label} opened evidence '{sid}'", details={"source_id": sid})
    return {"url": "/api/view/" + tokens.sign({"typ": "view", "cid": cid, "sid": sid, "role": p.role}, 300), "expires_in": 300}


_HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"


@app.get("/api/view/{token}", include_in_schema=False)
def view_document(token: str, dl: int = 0):
    data = tokens.verify(token, "view")
    if not data or data.get("role") not in EVIDENCE_ROLES:
        return HTMLResponse("<h3 style='font-family:sans-serif'>This link has expired. Go back to EQUALPATH and click View again.</h3>", status_code=403)
    c = _candidate_or_404(data["cid"])
    doc = next((d for d in c["documents"] if d["source_id"] == data["sid"]), None)
    if not doc:
        raise HTTPException(404, "document not found")
    rec, blob = _load_file(data["cid"], data["sid"])
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
    if dl:
        return Response(blob, media_type=rec["mime"], headers={**headers, "Content-Disposition": f'attachment; filename="{rec["filename"]}"'})
    try:
        content, ctype = docs.render_view(rec["filename"], blob, doc["title"], download_url=f"/api/view/{token}?dl=1")
    except Exception:  # noqa: BLE001 - a broken file must not crash the server
        return HTMLResponse("<h3 style='font-family:sans-serif'>This file could not be displayed. You can still download it.</h3>", status_code=422)
    if ctype.startswith("text/html"):
        headers["Content-Security-Policy"] = _HTML_CSP
    else:
        headers["Content-Disposition"] = f'inline; filename="{rec["filename"]}"'
    return Response(content, media_type=ctype, headers=headers)


@app.get("/api/candidates/{cid}/export")
def export_candidate(cid: str, p: Principal = Depends(require_roles("candidate"))):
    repo = get_repository()
    c = _candidate_or_404(cid)
    out = {"candidate": _candidate_view(c, "candidate"), "documents_text": {d["source_id"]: d.get("text", "") for d in c["documents"]}, "runs": repo.list("runs", owner_id=cid),
           "passports": repo.list("passports", owner_id=cid), "evidence_submissions": repo.list("evidence_submissions", owner_id=cid),
           "employer_responses": repo.list("employer_decisions", owner_id=cid), "audit_events": repo.audit_events(candidate_id=cid), "exported_at": utcnow(), "note": "Original files are kept in EQUALPATH and can be downloaded from the Evidence screen."}
    audit(event_type="data_exported", actor=_actor(p), run_id=None, candidate_id=cid, summary="Candidate exported their data", details={})
    return JSONResponse(out, headers={"Content-Disposition": f"attachment; filename=equalpath-{cid}.json"})


@app.delete("/api/candidates/{cid}")
def delete_candidate(cid: str, p: Principal = Depends(require_roles("candidate"))):
    repo = get_repository()
    runs = repo.list("runs", owner_id=cid)
    for r in runs:
        try:
            get_graph().checkpointer.delete_thread(r["run_id"])
        except Exception:  # noqa: BLE001
            pass
    n = repo.delete_owner(cid)
    audit(event_type="data_deleted", actor=_actor(p), run_id=None, candidate_id=cid,
          summary=f"Candidate deleted their demo data ({n} records, {len(runs)} run checkpoints). Audit events are kept and contain no PII.", details={"records": n})
    return {"deleted_records": n, "deleted_runs": len(runs)}


# ------------------------------------------------------------------ standalone agents (functional core agent, callable directly)

@app.post("/api/agents/skills-discovery")
def run_skills_discovery(body: SkillsDiscoveryBody, p: Principal = Depends(current_principal)):
    result = discover_skills(body.documents, get_llm_provider(), [body.candidate_name] if body.candidate_name else [])
    audit(event_type="agent_execution", actor="Skills Discovery Agent", run_id=None, candidate_id=None,
          summary=f"Standalone Skills Discovery: {len(result['skills'])} skills, {len(result['rejected'])} rejected",
          details={"method": result["method"], "documents": result["documents_processed"]})
    return result


@app.post("/api/agents/employer-readiness/scan")
def run_employer_scan(body: ScanBody):
    return {"flags": scan_text(body.text)}


# ------------------------------------------------------------------ runs (LangGraph)

@app.post("/api/runs")
def start_run(body: StartRunBody, p: Principal = Depends(require_roles("candidate"))):
    c = _candidate_or_404(body.candidate_id)
    if not c["consent"].get("process_profile"):
        raise HTTPException(403, "consent required")
    if not c["documents"]:
        raise HTTPException(422, "Add at least one evidence document first.")
    run_id = runner.start_run(body.candidate_id, body.job_id, _actor(p))
    return {"run_id": run_id}


@app.get("/api/runs")
def list_runs(p: Principal = Depends(current_principal)):
    return {"runs": sorted(get_repository().list("runs"), key=lambda r: r.get("created_at", ""), reverse=True)}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, p: Principal = Depends(current_principal)):
    return scrub_run_view(_run_or_404(run_id), p.role)


@app.post("/api/runs/{run_id}/candidate-review")
def candidate_review(run_id: str, body: CandidateReviewBody, p: Principal = Depends(require_roles("candidate"))):
    _expect_checkpoint(run_id, "candidate_review")
    if not body.approve:
        raise HTTPException(400, "The workflow continues only after the candidate approves the profile.")
    for d in body.decisions:
        if d.action in ("edit", "remove") and not (d.reason or "").strip():
            raise HTTPException(422, f"A reason is required to {d.action} '{d.normalized_skill}'.")
    runner.resume_run(run_id, {"body": body.model_dump(), "actor": _actor(p)})
    return {"ok": True}


@app.post("/api/runs/{run_id}/role-selection")
def role_selection(run_id: str, body: RoleSelectionBody, p: Principal = Depends(require_roles("candidate"))):
    _expect_checkpoint(run_id, "role_selection")
    if not role_by_id(body.role_id):
        raise HTTPException(422, "unknown role")
    runner.resume_run(run_id, {"role_id": body.role_id, "reason": body.reason, "actor": _actor(p)})
    return {"ok": True}


def _resume_final_review(run_id: str, body: FinalReviewBody, actor: str, role: str, via: str) -> None:
    _expect_checkpoint(run_id, "final_review")
    if body.decision in ("edit", "reject", "request_evidence") and not (body.reason or "").strip():
        raise HTTPException(422, "A reason is required for every override (edit, reject, request evidence).")
    if body.decision == "edit" and not body.edits:
        raise HTTPException(422, "Decision 'edit' needs at least one edit.")
    runner.resume_run(run_id, {"body": body.model_dump(), "actor": actor, "role": role, "via": via})


@app.post("/api/runs/{run_id}/final-review")
def final_review(run_id: str, body: FinalReviewBody, p: Principal = Depends(require_roles("counsellor"))):
    _resume_final_review(run_id, body, _actor(p), p.label, "EQUALPATH review screen")
    return {"ok": True}


@app.post("/api/runs/{run_id}/evidence-response")
def evidence_response(run_id: str, body: EvidenceResponseBody, p: Principal = Depends(require_roles("candidate"))):
    _expect_checkpoint(run_id, "evidence_request")
    runner.resume_run(run_id, {"body": body.model_dump(), "actor": _actor(p)})
    return {"ok": True}


def _passport_for(run_id: str, audience: str, p: Principal) -> dict:
    view = _run_or_404(run_id)
    fr = view["values"].get("final_review")
    passport = view["values"].get("passport")
    if p.role == "auditor":
        raise HTTPException(403, "Auditors do not see individual passports.")
    if not passport or not fr or fr["decision"] not in ("approve", "edit"):
        raise HTTPException(409, "The passport cannot be produced before the final human review approves it.")
    # Recompose so later human-reviewed milestone evidence is reflected; identity and issue date are preserved.
    live = compose_passport({**view["values"], "timeline": []}, draft=False)
    passport = {**live, "passport_id": passport["passport_id"], "issued_at": passport["issued_at"], "recomposed_at": utcnow()}
    if p.role == "hr_reviewer" or audience == "employer":
        return employer_copy(passport)
    return passport


@app.get("/api/runs/{run_id}/passport")
def get_passport(run_id: str, audience: str = "candidate", p: Principal = Depends(current_principal)):
    return _passport_for(run_id, audience, p)


@app.get("/api/runs/{run_id}/passport.html", response_class=HTMLResponse)
def get_passport_html(run_id: str, audience: str = "candidate", p: Principal = Depends(current_principal)):
    passport = _passport_for(run_id, audience, p)
    return HTMLResponse(passport_html(passport), headers={"Content-Disposition": f"attachment; filename=passport-{run_id}-{passport.get('audience', audience)}.html"})


# ------------------------------------------------------------------ learning milestones + evidence review

class MilestoneStartBody(BaseModel):
    note: str | None = None


def _milestone(view: dict, mid: str) -> dict:
    m = next((m for m in (view["values"].get("pathway") or {}).get("milestones", []) if m["milestone_id"] == mid), None)
    if not m:
        raise HTTPException(404, "milestone not found")
    return m


@app.post("/api/runs/{run_id}/milestones/{mid}/start")
def start_milestone(run_id: str, mid: str, body: MilestoneStartBody | None = None, p: Principal = Depends(require_roles("candidate"))):
    view = _run_or_404(run_id)
    m = _milestone(view, mid)
    cid = view["run"]["candidate_id"]
    get_repository().put("milestone_progress", f"{run_id}:{mid}", {"run_id": run_id, "milestone_id": mid, "progress": "started", "at": utcnow()}, owner_id=cid)
    audit(event_type="milestone_started", actor=_actor(p), run_id=run_id, candidate_id=cid,
          summary=f"Candidate marked '{m['learning_asset_title']}' as started (self-reported; no progress sync)", details={"milestone": mid, "asset": m["learning_asset_id"]})
    return {"ok": True}


@app.post("/api/runs/{run_id}/milestones/{mid}/evidence")
def submit_milestone_evidence(run_id: str, mid: str, body: MilestoneEvidenceBody, p: Principal = Depends(require_roles("candidate"))):
    view = _run_or_404(run_id)
    m = _milestone(view, mid)
    cid = view["run"]["candidate_id"]
    sub_id = f"sub-{uuid.uuid4().hex[:8]}"
    repo = get_repository()
    repo.put("evidence_submissions", sub_id, {"submission_id": sub_id, "run_id": run_id, "candidate_id": cid, "milestone_id": mid,
                                              "capability": m["capability"], "gap": m["gap"], "evidence_kind": body.evidence_kind, "title": body.title,
                                              "content": body.content, "filename": body.filename, "status": "pending_review", "submitted_at": utcnow(),
                                              "required_evidence": m["required_evidence"], "completion_rule": m["completion_rule"]}, owner_id=cid)
    repo.put("milestone_progress", f"{run_id}:{mid}", {"run_id": run_id, "milestone_id": mid, "progress": "evidence_submitted", "at": utcnow()}, owner_id=cid)
    audit(event_type="evidence_submitted", actor=_actor(p), run_id=run_id, candidate_id=cid,
          summary=f"Milestone evidence submitted for '{m['gap']}' ({body.evidence_kind}); routed to human reviewer", details={"milestone": mid, "submission": sub_id})
    return {"submission_id": sub_id, "status": "pending_review"}


@app.post("/api/evidence-submissions/{sub_id}/decision")
def decide_evidence(sub_id: str, body: EvidenceDecisionBody, p: Principal = Depends(require_roles("counsellor"))):
    repo = get_repository()
    sub = repo.get("evidence_submissions", sub_id)
    if not sub:
        raise HTTPException(404, "submission not found")
    if sub["status"] != "pending_review":
        raise HTTPException(409, f"submission already {sub['status']}")
    sub["status"] = {"accept": "accepted", "reject": "rejected", "request_more": "request_more"}[body.decision]
    sub["review"] = {"actor": _actor(p), "decision": body.decision, "reason": body.reason, "at": utcnow()}
    repo.put("evidence_submissions", sub_id, sub, owner_id=sub["candidate_id"])
    audit(event_type="evidence_reviewed", actor=_actor(p), run_id=sub["run_id"], candidate_id=sub["candidate_id"],
          summary=f"Milestone evidence '{sub['gap']}' {sub['status']}" + (" - capability status now 'assessed'" if body.decision == "accept" else ""),
          details={"submission": sub_id, "decision": body.decision, "reason": body.reason})
    return sub


# ------------------------------------------------------------------ JD rewrite approval (HR)

@app.get("/api/runs/{run_id}/jd-rewrite")
def get_jd_rewrite(run_id: str, p: Principal = Depends(require_roles("candidate", "counsellor", "hr_reviewer"))):
    d = get_repository().get("jd_rewrites", run_id)
    if not d:
        raise HTTPException(404, "no rewrite for this run")
    return d


@app.post("/api/runs/{run_id}/jd-rewrite/decision")
def decide_jd_rewrite(run_id: str, body: JDRewriteDecisionBody, p: Principal = Depends(require_roles("hr_reviewer"))):
    repo = get_repository()
    d = repo.get("jd_rewrites", run_id)
    if not d:
        raise HTTPException(404, "no rewrite for this run")
    if body.decision == "edit":
        if not body.edited_text:
            raise HTTPException(422, "edited_text required")
        d["suggested"] = body.edited_text
    d["status"] = {"approve": "approved_by_hr", "edit": "approved_by_hr_with_edits", "reject": "rejected_by_hr"}[body.decision]
    d["history"].append({"actor": _actor(p), "decision": body.decision, "reason": body.reason, "at": utcnow()})
    if body.decision != "reject":
        job = _job_for(d["job_id"])
        rescan = assess_employer({**job, "text": d["suggested"]}, employer_for(job))
        d["rescan"] = rescan["summary"]
        d["rescan_flags"] = len(rescan["flags"])
    cid = (repo.get("runs", run_id) or {}).get("candidate_id")
    repo.put("jd_rewrites", run_id, d, owner_id=cid)
    audit(event_type="jd_rewrite_decision", actor=_actor(p), run_id=run_id, candidate_id=cid,
          summary={"approve": "HR reviewer approved the rewritten job ad", "edit": "HR reviewer approved the rewritten job ad with edits",
                   "reject": "HR reviewer rejected the rewritten job ad"}[body.decision], details={"decision": body.decision, "reason": body.reason})
    return d


def _job_for(job_id: str) -> dict:
    return next(j for j in jobs_data()["jobs"] if j["job_id"] == job_id)


# ------------------------------------------------------------------ employer side (HR Reviewer): claims and the response to the candidate

def _candidate_of(view: dict) -> dict:
    return get_repository().get("candidates", view["run"]["candidate_id"]) or {"profile": {}, "consent": {}}


def _shared_accommodations(cand: dict) -> list[str]:
    if not cand.get("consent", {}).get("share_accommodations"):
        return []
    return list((cand.get("profile", {}).get("accommodations") or {}).get("shareable_work_accommodations") or [])


def employer_state(run_id: str, view: dict | None = None) -> dict:
    """Everything the employer side has done for this run, and what is still open."""
    view = view or _run_or_404(run_id)
    repo = get_repository()
    scan = view["values"].get("employer_scan") or {}
    rewrite = repo.get("jd_rewrites", run_id)
    conflicts = scan.get("conflicts_requiring_review", [])
    responses = {c: repo.get("claim_responses", f"{run_id}:{c}") for c in conflicts}
    responses = {k: v for k, v in responses.items() if v}
    decision = repo.get("employer_decisions", run_id)
    cand = _candidate_of(view)
    passport_ready = bool(view["values"].get("passport"))
    shared = bool(cand.get("consent", {}).get("share_with_employer"))
    tasks = [
        {"id": "rewrite", "status": "none" if not rewrite else ("todo" if rewrite["status"] == "pending_hr_approval" else "done"),
         "detail": rewrite["status"] if rewrite else None},
        {"id": "claims", "status": "none" if not conflicts else ("done" if len(responses) == len(conflicts) else "todo"),
         "open": len(conflicts) - len(responses), "total": len(conflicts)},
        {"id": "candidate", "status": "done" if decision else ("todo" if passport_ready and shared else "locked"),
         "blocked_by": None if passport_ready and shared else ("passport" if not passport_ready else "consent")},
    ]
    return {"rewrite": rewrite, "claim_responses": responses, "decision": decision, "tasks": tasks,
            "can_decide": passport_ready and shared and not decision, "shared_accommodations": _shared_accommodations(cand)}


@app.get("/api/runs/{run_id}/employer-tasks")
def get_employer_tasks(run_id: str, p: Principal = Depends(require_roles("candidate", "counsellor", "hr_reviewer"))):
    return employer_state(run_id)


@app.post("/api/runs/{run_id}/claims/{claim_id}/response")
def respond_to_claim(run_id: str, claim_id: str, body: ClaimResponseBody, p: Principal = Depends(require_roles("hr_reviewer"))):
    view = _run_or_404(run_id)
    scan = view["values"].get("employer_scan") or {}
    claim = next((c for c in scan.get("claims", []) if c["claim_id"] == claim_id), None)
    if not claim:
        raise HTTPException(404, "claim not found")
    if not claim["requires_human_review"]:
        raise HTTPException(409, "This claim does not need a response.")
    rec = {"run_id": run_id, "claim_id": claim_id, "resolution": body.resolution, "note": body.note, "actor": _actor(p), "at": utcnow()}
    cid = view["run"]["candidate_id"]
    get_repository().put("claim_responses", f"{run_id}:{claim_id}", rec, owner_id=cid)
    audit(event_type="employer_claim_response", actor=_actor(p), run_id=run_id, candidate_id=cid,
          summary=f"HR reviewer answered the conflicting claim '{claim_id.replace('_', ' ')}': "
                  + ("the job ad will be fixed" if body.resolution == "fix_ad" else "the employer statement will be corrected"),
          details={"claim": claim_id, "resolution": body.resolution})
    return rec


@app.post("/api/runs/{run_id}/employer-decision")
def employer_decision(run_id: str, body: EmployerDecisionBody, p: Principal = Depends(require_roles("hr_reviewer"))):
    view = _run_or_404(run_id)
    state = employer_state(run_id, view)
    if not view["values"].get("passport"):
        raise HTTPException(409, "The passport has not been issued yet.")
    if not _candidate_of(view).get("consent", {}).get("share_with_employer"):
        raise HTTPException(409, "The candidate has not agreed to share the passport with employers.")
    if state["decision"]:
        raise HTTPException(409, "A response has already been recorded.")
    unknown = [a for a in body.adjustments if a not in state["shared_accommodations"]]
    if unknown:
        raise HTTPException(422, "Adjustments must come from what the candidate chose to share.")
    rec = {"run_id": run_id, "decision": body.decision, "reason": body.reason, "adjustments": body.adjustments if body.decision == "invite" else [],
           "actor": _actor(p), "at": utcnow(), "employer": (view["values"].get("employer_scan") or {}).get("employer")}
    cid = view["run"]["candidate_id"]
    get_repository().put("employer_decisions", run_id, rec, owner_id=cid)
    audit(event_type="employer_decision", actor=_actor(p), run_id=run_id, candidate_id=cid,
          summary=f"Employer response to the candidate: {body.decision.replace('_', ' ')}"
                  + (f" with {len(rec['adjustments'])} agreed interview adjustment(s)" if rec["adjustments"] else ""),
          details={"decision": body.decision, "adjustments": len(rec["adjustments"])})
    return rec


# ------------------------------------------------------------------ auditor: verify the log, sign off the fairness check

@app.post("/api/audit/verify")
def verify_audit(p: Principal = Depends(require_roles("auditor"))):
    chain = get_repository().verify_audit_chain()
    rec = {**chain, "checked_at": utcnow(), "actor": _actor(p)}
    audit(event_type="audit_verified", actor=_actor(p), run_id=None, candidate_id=None,
          summary=f"Auditor re-checked the audit log: {chain['events']} entries, chain {'intact' if chain['valid'] else 'BROKEN'}",
          details={"valid": chain["valid"], "events": chain["events"]})
    return rec


@app.post("/api/runs/{run_id}/fairness/try")
def fairness_try(run_id: str, body: FairnessTryBody, p: Principal = Depends(current_principal)):
    """Run a twin the viewer designs (one changed detail) through EQUALPATH's matching and through the simulated biased filter."""
    view = _run_or_404(run_id)
    v = view["values"]
    if not v.get("bias_audit") or not v.get("skills"):
        raise HTTPException(409, "The fairness check has not run yet.")
    cand = get_repository().get("candidates", view["run"]["candidate_id"])
    if not cand:
        raise HTTPException(404, "candidate not found")
    try:
        r = try_twin(cand["profile"], cand["documents"], v["skills"], v["selected_role_id"], body.field, body.value)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if p.role not in PERSONAL_VIEW_ROLES:  # the candidate's real value is never shown to staff without evidence access
        for d in r["diff"]:
            d["before"] = None
        if body.field != "name":
            r["twin_name"] = None
    return r


@app.get("/api/runs/{run_id}/fairness-review")
def get_fairness_review(run_id: str, p: Principal = Depends(current_principal)):
    _run_or_404(run_id)
    return {"review": get_repository().get("fairness_reviews", run_id)}


@app.post("/api/runs/{run_id}/fairness-review")
def post_fairness_review(run_id: str, body: FairnessReviewBody, p: Principal = Depends(require_roles("auditor"))):
    view = _run_or_404(run_id)
    if not view["values"].get("bias_audit"):
        raise HTTPException(409, "The fairness check has not run yet.")
    rec = {"run_id": run_id, "finding": body.finding, "note": body.note, "actor": _actor(p), "at": utcnow()}
    cid = view["run"]["candidate_id"]
    get_repository().put("fairness_reviews", run_id, rec, owner_id=cid)
    audit(event_type="fairness_reviewed", actor=_actor(p), run_id=run_id, candidate_id=cid,
          summary="Auditor reviewed the fairness check: " + ("no concerns" if body.finding == "no_concerns" else "raised a concern for the reviewers"),
          details={"finding": body.finding})
    return rec


# ------------------------------------------------------------------ review queue + audit

@app.get("/api/reviews")
def review_queue(p: Principal = Depends(require_roles("counsellor", "hr_reviewer"))):
    repo = get_repository()
    finals = [t for t in repo.list("review_tasks") if t["status"] == "open"]
    for t in finals:
        view = runner.run_view(t["run_id"])
        t["waiting"] = bool(view and view["interrupt"] and view["interrupt"]["checkpoint"] == "final_review")
    finals = [t for t in finals if t.get("waiting")]
    evidence = [s for s in repo.list("evidence_submissions") if s["status"] == "pending_review"] if p.role == "counsellor" else []
    rewrites = [r for r in repo.list("jd_rewrites") if r["status"] == "pending_hr_approval"]
    return {"final_reviews": finals, "evidence_reviews": evidence, "jd_rewrites": rewrites,
            "closed_final_reviews": [t for t in repo.list("review_tasks") if t["status"] != "open"]}


@app.get("/api/audit")
def audit_log(run_id: str | None = None, candidate_id: str | None = None, p: Principal = Depends(current_principal)):
    if p.role == "candidate" and not (run_id or candidate_id):
        raise HTTPException(403, "Candidates can only open the audit trail of their own run.")
    repo = get_repository()
    events = repo.audit_events(run_id=run_id, candidate_id=candidate_id)
    if p.role == "hr_reviewer":
        events = [{**e, "details": {}} for e in events]
    return {"events": events, "chain": repo.verify_audit_chain()}


@app.get("/api/bias/monitoring-prototype")
def bias_monitoring():
    return monitoring_prototype()


# ------------------------------------------------------------------ SAP Build Process Automation callback

class SAPBuildDecision(BaseModel):
    runId: str
    decision: str = Field(pattern="^(approve|edit|reject|request_evidence)$")
    reason: str | None = None
    reviewer: str = "SAP Build reviewer"
    reviewerRole: str = "counsellor"


@app.post("/api/integrations/sap-build/review-decision")
def sap_build_decision(body: SAPBuildDecision, request: Request):
    secret = get_settings().sbpa_callback_secret
    if not secret:
        raise HTTPException(503, "SAP Build Process Automation callback is not configured (SBPA_CALLBACK_SECRET).")
    if not hmac.compare_digest(request.headers.get("X-EqualPath-Callback-Secret", ""), secret):
        raise HTTPException(401, "invalid callback secret")
    fr = FinalReviewBody(decision=body.decision, reason=body.reason)
    _resume_final_review(body.runId, fr, f"{body.reviewer} (SAP Build Process Automation)", ROLE_LABELS.get(body.reviewerRole, body.reviewerRole),
                         "SAP Build Process Automation inbox")
    return {"ok": True}


# ------------------------------------------------------------------ practice targets for learning milestones

_orders: list[dict] = [{"id": 1, "item": "Notebook", "quantity": 2, "status": "PAID"}, {"id": 2, "item": "Pen set", "quantity": 1, "status": "SHIPPED"}]


class OrderIn(BaseModel):
    item: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=100)


@app.get("/api/practice/orders", tags=["practice"])
def practice_orders():
    return {"orders": _orders}


@app.post("/api/practice/orders", status_code=201, tags=["practice"])
def practice_create_order(order: OrderIn):
    o = {"id": len(_orders) + 1, "item": order.item, "quantity": order.quantity, "status": "NEW"}
    _orders.append(o)
    return o


# ------------------------------------------------------------------ static frontend (production build)

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        target = STATIC_DIR / full_path
        if full_path and target.is_file() and STATIC_DIR in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")
