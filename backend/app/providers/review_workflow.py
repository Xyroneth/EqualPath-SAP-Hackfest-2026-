"""ReviewWorkflowProvider: where the final human review task lives.

- LocalReviewQueue (default): the EQUALPATH Human Review screen.
- SAPBuildProcessAutomation: also starts an approval process in SAP Build Process Automation so the
  counsellor / HR reviewer can decide from the SAP Build inbox. The process calls back
  POST /api/integrations/sap-build/review-decision, which resumes the paused LangGraph run.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from app.config import Settings, get_settings


class ReviewWorkflowProvider(ABC):
    kind = "abstract"
    live = False

    @abstractmethod
    def submit(self, task: dict) -> dict:
        """Register a review task. Returns {"provider": ..., "external_id": ..., "status": ...}."""


class LocalReviewQueue(ReviewWorkflowProvider):
    kind = "local_queue"

    def submit(self, task: dict) -> dict:
        return {"provider": "EQUALPATH local review queue", "external_id": None, "status": "queued_locally"}


class SAPBuildProcessAutomation(ReviewWorkflowProvider):
    kind = "sap_build_process_automation"
    live = True

    def __init__(self, s: Settings):
        self.s = s

    def _token(self) -> str:
        r = httpx.post(self.s.sbpa_token_url, data={"grant_type": "client_credentials"},
                       auth=(self.s.sbpa_client_id, self.s.sbpa_client_secret), timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]

    def submit(self, task: dict) -> dict:
        # Data minimisation: the SAP Build context carries IDs, statuses and summaries, never names or contact data.
        context = {
            "runId": task["run_id"],
            "candidateRef": task["candidate_id"],
            "roleTitle": task.get("role_title", ""),
            "proposedOutcomes": ", ".join(task.get("proposed_outcomes", [])),
            "gapSummary": task.get("gap_summary", ""),
            "employerFlags": int(task.get("employer_flag_count", 0)),
            "biasAuditResult": task.get("bias_result", ""),
            "reviewUrl": task.get("review_url", ""),
        }
        try:
            r = httpx.post(
                f"{self.s.sbpa_api_url.rstrip('/')}/workflow/rest/v1/workflow-instances",
                headers={"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"},
                json={"definitionId": self.s.sbpa_definition_id, "context": context},
                timeout=30,
            )
            r.raise_for_status()
            body = r.json()
            return {"provider": "SAP Build Process Automation", "external_id": body.get("id"), "status": body.get("status", "RUNNING")}
        except httpx.HTTPError as exc:
            return {"provider": "SAP Build Process Automation", "external_id": None,
                    "status": f"failed ({type(exc).__name__}); task kept in local queue"}


def get_review_workflow() -> ReviewWorkflowProvider:
    s = get_settings()
    return SAPBuildProcessAutomation(s) if s.sbpa_configured() else LocalReviewQueue()
