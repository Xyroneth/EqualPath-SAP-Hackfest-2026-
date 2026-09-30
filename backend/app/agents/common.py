"""Shared helpers for agents: taxonomy, catalog access and small scoring utilities."""
from __future__ import annotations

import re
from functools import lru_cache

from app.config import load_json
from app.schemas import PROFICIENCY_ORDER, VERIFICATION_ORDER

EVIDENCE_WEIGHT = {"self_declared": 0.25, "source_supported": 0.7, "assessed": 0.9, "externally_verified": 1.0}


@lru_cache
def taxonomy() -> dict[str, dict]:
    return {s["normalized_skill"]: s for s in load_json("skills_taxonomy.json")["skills"]}


@lru_cache
def roles() -> list[dict]:
    return load_json("roles.json")["roles"]


def role_by_id(role_id: str) -> dict | None:
    return next((r for r in roles() if r["role_id"] == role_id), None)


@lru_cache
def jobs_data() -> dict:
    return load_json("jobs.json")


def job_by_id(job_id: str) -> dict | None:
    return next((j for j in jobs_data()["jobs"] if j["job_id"] == job_id), None)


def employer_for(job: dict) -> dict:
    return jobs_data()["employers"][job["employer_id"]]


def improved_job_for(job: dict) -> dict | None:
    """The version of the same ad the employer published after fixing it (seeded)."""
    return next((j for j in jobs_data()["jobs"] if j["role_id"] == job["role_id"] and j.get("version") == "improved"), None)


def capability_name(capability: str) -> str:
    t = taxonomy().get(capability)
    if t:
        return t["skill_name"]
    return capability.split(".")[-1].replace("_", " ").capitalize()


def level_meets(have: str | None, need: str) -> bool:
    return have is not None and PROFICIENCY_ORDER.get(have, -1) >= PROFICIENCY_ORDER[need]


def is_evidence_backed(status: str) -> bool:
    return VERIFICATION_ORDER.get(status, 0) >= VERIFICATION_ORDER["source_supported"]


def normalise_text(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def active_skills(skills: list[dict]) -> list[dict]:
    return [s for s in skills if s.get("candidate_action") != "removed"]
