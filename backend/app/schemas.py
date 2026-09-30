"""Pydantic schemas shared by agents, the workflow and the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

VerificationStatus = Literal["self_declared", "source_supported", "assessed", "externally_verified"]
EvidenceType = Literal["resume", "work_sample", "project", "certificate", "assessment", "candidate_added", "learning_evidence"]
Proficiency = Literal["awareness", "basic", "intermediate", "advanced"]
GapStatus = Literal["verified", "developing", "missing"]
EmployerEvidenceLevel = Literal["declared", "document_verified", "experience_validated", "conflicting_evidence"]
PassportOutcome = Literal["Ready to Proceed", "Ready with Learning Milestone", "Employer Action Required", "Human Review Required"]

PROFICIENCY_ORDER = {"awareness": 0, "basic": 1, "intermediate": 2, "advanced": 3}
VERIFICATION_ORDER = {"self_declared": 0, "source_supported": 1, "assessed": 2, "externally_verified": 3}
# Evidence types whose content was authored by the candidate about themselves.
SELF_AUTHORED_TYPES = {"resume", "candidate_added"}


class EvidenceDocument(BaseModel):
    source_id: str
    title: str
    evidence_type: EvidenceType
    date: str | None = None
    text: str


class SkillRecord(BaseModel):
    """One evidence-backed capability. The schema required by the master prompt."""

    skill_name: str = Field(min_length=2, max_length=120)
    normalized_skill: str = Field(min_length=2, max_length=120)
    category: Literal["technical", "domain", "professional", "learning"] = "technical"
    proficiency: Proficiency = "basic"
    evidence_type: EvidenceType
    evidence_quote: str = Field(min_length=8, max_length=400)
    source_id: str
    recency: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    verification_status: VerificationStatus
    adjacent_skills: list[str] = Field(default_factory=list)
    # Provenance and review bookkeeping (not produced by the LLM).
    additional_sources: list[str] = Field(default_factory=list)
    claimed_proficiency: Proficiency | None = None
    extraction_method: str = "deterministic"
    candidate_action: Literal["pending", "accepted", "edited", "removed", "added"] = "pending"
    notes: list[str] = Field(default_factory=list)

    @field_validator("normalized_skill")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")


class LLMSkillCandidate(BaseModel):
    """What the LLM is allowed to propose. Verification status is recomputed by code."""

    skill_name: str
    normalized_skill: str
    category: Literal["technical", "domain", "professional", "learning"] = "technical"
    proficiency: Proficiency = "basic"
    evidence_quote: str
    source_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    verification_status: str | None = None  # ignored except for audit of attempted upgrades
    adjacent_skills: list[str] = Field(default_factory=list)


class LLMSkillResponse(BaseModel):
    skills: list[LLMSkillCandidate]


class Milestone(BaseModel):
    milestone_id: str
    gap: str
    capability: str
    status: Literal["developing", "missing"]
    learning_asset_id: str
    learning_asset_title: str
    learning_asset_url: str
    learning_asset_provider: str
    estimated_hours: float = Field(gt=0, le=40)
    practice_task: str = Field(min_length=10)
    required_evidence: list[str] = Field(min_length=1)
    completion_rule: str = "Human reviewer accepts the submitted evidence"
    why_it_matters: str = Field(min_length=10)
    importance: Literal["essential", "preferred"] = "essential"
    progress: Literal["not_started", "started", "evidence_submitted", "accepted", "needs_more_evidence"] = "not_started"
    generated_by: str = "deterministic"


class LLMMilestoneDraft(BaseModel):
    capability: str
    learning_asset_id: str
    estimated_hours: float
    practice_task: str
    required_evidence: list[str]
    why_it_matters: str


class LLMPathwayResponse(BaseModel):
    milestones: list[LLMMilestoneDraft]


# ---------- API request bodies ----------

class ConsentBody(BaseModel):
    process_profile: bool
    use_llm_with_redaction: bool = True
    share_with_employer: bool = False
    share_accommodations: bool = False


class CreateCandidateBody(BaseModel):
    profile: dict[str, Any]
    consent: ConsentBody
    seed_persona: Literal["priya"] | None = None  # load the demo persona's real evidence files


class UpdateCandidateBody(BaseModel):
    profile: dict[str, Any] | None = None
    consent: ConsentBody | None = None


class LoginBody(BaseModel):
    role: Literal["candidate", "counsellor", "hr_reviewer", "auditor"]
    password: str | None = Field(default=None, max_length=200)


UserEvidenceType = Literal["resume", "work_sample", "project", "certificate"]


class TextDocumentBody(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    evidence_type: UserEvidenceType = "work_sample"
    text: str = Field(min_length=20, max_length=60000)


class StartRunBody(BaseModel):
    candidate_id: str
    job_id: str = "northstar-qa-automation-v1"


class SkillDecision(BaseModel):
    normalized_skill: str
    action: Literal["accept", "edit", "remove"]
    skill_name: str | None = None
    proficiency: Proficiency | None = None
    reason: str | None = None


class AddedSkill(BaseModel):
    skill_name: str
    normalized_skill: str
    evidence_quote: str
    source_id: str = "candidate-correction"
    proficiency: Proficiency = "basic"


class CandidateReviewBody(BaseModel):
    decisions: list[SkillDecision] = Field(default_factory=list)
    added_skills: list[AddedSkill] = Field(default_factory=list)
    work_conditions: dict[str, Any] | None = None
    sharing: dict[str, bool] = Field(default_factory=dict)
    approve: bool = True


class RoleSelectionBody(BaseModel):
    role_id: str
    reason: str | None = None


class ReviewEdit(BaseModel):
    target: str  # e.g. "milestone:ms-2.estimated_hours" or "recommendation.next_action"
    new_value: Any
    reason: str = Field(min_length=5)


class FinalReviewBody(BaseModel):
    decision: Literal["approve", "edit", "reject", "request_evidence"]
    reason: str | None = None
    edits: list[ReviewEdit] = Field(default_factory=list)
    reviewer_note: str | None = None


class EvidenceResponseBody(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


class MilestoneEvidenceBody(BaseModel):
    evidence_kind: Literal["project", "screenshot", "assessment_result", "reflection"]
    title: str
    content: str = Field(min_length=10)
    filename: str | None = None


class EvidenceDecisionBody(BaseModel):
    decision: Literal["accept", "reject", "request_more"]
    reason: str = Field(min_length=5)


class JDRewriteDecisionBody(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    reason: str = Field(min_length=5)
    edited_text: str | None = None


class ClaimResponseBody(BaseModel):
    resolution: Literal["fix_ad", "update_statement"]
    note: str = Field(min_length=5, max_length=600)


class EmployerDecisionBody(BaseModel):
    decision: Literal["invite", "talent_pool", "decline"]
    reason: str = Field(min_length=5, max_length=800)
    adjustments: list[str] = Field(default_factory=list, max_length=10)


class FairnessTryBody(BaseModel):
    field: str = Field(max_length=40)
    value: str = Field(max_length=80)


class FairnessReviewBody(BaseModel):
    finding: Literal["no_concerns", "concern"]
    note: str = Field(min_length=5, max_length=800)


class ScanBody(BaseModel):
    text: str = Field(min_length=20)


class SkillsDiscoveryBody(BaseModel):
    documents: list[EvidenceDocument]
    candidate_name: str | None = None
