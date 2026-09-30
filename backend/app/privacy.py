"""PII redaction and data minimisation applied before any external LLM call."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("PHONE", re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}\b")),
    ("AADHAAR", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("PROFILE_URL", re.compile(r"(?:https?://)?(?:www\.)?(?:github|linkedin)\.com/(?:in/)?[\w-]+", re.I)),
    ("PINCODE", re.compile(r"\b\d{6}\b")),
    ("DOB", re.compile(r"\b(?:DOB|Date of birth)[:\s]+[\w/ -]{6,12}", re.I)),
]

# Demographic wording that is unnecessary for skill extraction (data minimisation).
_DEMOGRAPHIC = re.compile(r"\b(?:age[d]?\s*\d{2}|\d{2}\s*(?:years old|yrs old)|marital status[:\s]+\w+|gender[:\s]+\w+)\b", re.I)


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def redact(text: str, names: list[str] | None = None) -> RedactionResult:
    counts: dict[str, int] = {}
    out = text
    # Structured identifiers first, so an e-mail or profile URL containing the name is removed whole.
    for label, pattern in _PATTERNS:
        out, n = pattern.subn(f"[{label}]", out)
        if n:
            counts[label] = counts.get(label, 0) + n
    for name in sorted({n for n in (names or []) if n and len(n) > 1}, key=len, reverse=True):
        parts = [name] + [p for p in name.split() if len(p) > 2]
        for part in parts:
            pattern = re.compile(rf"\b{re.escape(part)}\b", re.I)
            out, n = pattern.subn("[NAME]", out)
            if n:
                counts["NAME"] = counts.get("NAME", 0) + n
    out, n = _DEMOGRAPHIC.subn("[DEMOGRAPHIC]", out)
    if n:
        counts["DEMOGRAPHIC"] = n
    out = re.sub(r"(\[NAME\]\s*){2,}", "[NAME] ", out)
    return RedactionResult(out, counts)


def minimise_profile_for_matching(profile: dict) -> dict:
    """Return only the fields the matching agents are allowed to use.

    Protected attributes (name, gender, age, disability, career-break duration, college) are
    deliberately absent. The Bias Audit Agent checks this allow-list at runtime.
    """
    wc = profile.get("work_conditions", {})
    return {
        "languages": list(profile.get("languages", [])),
        "commute_city": _normalise_city(wc.get("commute_city") or profile.get("location_city", "")),
        "work_modes": list(wc.get("work_modes", [])),
        "can_relocate": bool(wc.get("can_relocate", False)),
        "weekly_learning_hours": float(wc.get("weekly_learning_hours", 5) or 5),
        "relevant_experience_years": float(profile.get("relevant_experience_years", 0) or 0),
        "schedule_needs": wc.get("schedule_needs", ""),
    }


MATCHING_FEATURE_ALLOWLIST = frozenset(
    ["languages", "commute_city", "work_modes", "can_relocate", "weekly_learning_hours", "relevant_experience_years", "schedule_needs"]
)
PROTECTED_ATTRIBUTES = ("display_name", "gender", "age", "disability", "career_break", "college", "marital_status", "religion", "caste")

_CITY_ALIASES = {
    "lucknow": "lucknow", "lakhnau": "lucknow", "lko": "lucknow",
    "noida": "noida", "bengaluru": "bengaluru", "bangalore": "bengaluru",
}


def _normalise_city(value: str) -> str:
    v = value.lower()
    for alias, city in _CITY_ALIASES.items():
        if alias in v:
            return city
    return v.split(",")[0].strip()
