"""Candidate profile: one validated shape for anyone's details (not only the sample persona).

The profile arrives as free JSON from the form. This module checks it, fills safe defaults and returns the shape the
agents rely on. Personal details (age, gender, career break, college) are optional: they are never matching inputs and
are kept only so the fairness check can test that they make no difference.
"""
from __future__ import annotations

import copy

WORK_MODES = ("remote", "hybrid", "onsite")
GENDERS = ("female", "male", "non_binary", "other", "prefer_not_to_say")
BREAK_REASONS = ("caregiving", "health", "study", "relocation", "other")


class ProfileError(ValueError):
    """The profile cannot be used as given; the message is safe to show to the person filling the form."""


def _text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _number(value, low: float, high: float, what: str, optional: bool = False):
    if value in (None, ""):
        if optional:
            return None
        raise ProfileError(f"{what} is required.")
    try:
        n = float(value)
    except (TypeError, ValueError) as exc:
        raise ProfileError(f"{what} must be a number.") from exc
    if not low <= n <= high:
        raise ProfileError(f"{what} must be between {low:g} and {high:g}.")
    return n


def blank_profile() -> dict:
    """An empty profile for someone entering their own (or another person's) details."""
    return normalise_profile({"display_name": "", "location_city": "", "languages": [], "work_conditions": {"work_modes": []}}, strict=False)


def normalise_profile(raw: dict, strict: bool = True) -> dict:
    """Validate and complete a profile. With strict=False missing required fields are left empty instead of raising."""
    p = copy.deepcopy(raw or {})
    name = _text(p.get("display_name"), 80)
    city = _text(p.get("location_city"), 60)
    if strict and len(name) < 2:
        raise ProfileError("Please enter a name (at least 2 characters).")
    if strict and len(city) < 2:
        raise ProfileError("Please enter the city you live in.")
    state = _text(p.get("location_state"), 60)
    p["display_name"], p["location_city"], p["location_state"] = name, city, state

    wording = _text(p.get("location_wording"), 120)
    if not wording or city.lower() not in wording.lower():
        wording = ", ".join(x for x in (city, state) if x)
    p["location_wording"] = wording

    langs = p.get("languages") or []
    if isinstance(langs, str):
        langs = langs.split(",")
    p["languages"] = [x for x in dict.fromkeys(_text(l, 30).title() for l in langs) if x][:8]
    if strict and not p["languages"]:
        raise ProfileError("Please add at least one language.")

    age = _number(p.get("age"), 16, 80, "Age", optional=True)
    p["age"] = int(age) if age is not None else None
    gender = (p.get("gender") or "").strip().lower().replace("-", "_").replace(" ", "_") or None
    if gender and gender not in GENDERS:
        raise ProfileError("Unknown gender value.")
    p["gender"] = None if gender == "prefer_not_to_say" else gender
    p["college"] = _text(p.get("college"), 80) or None
    p["relevant_experience_years"] = _number(p.get("relevant_experience_years") or 0, 0, 50, "Years of experience")

    cb = p.get("career_break") or {}
    months = int(_number(cb.get("months") or 0, 0, 480, "Career break"))
    reason = (cb.get("reason") or "").strip().lower() or None
    if reason and reason not in BREAK_REASONS:
        reason = "other"
    p["career_break"] = {"months": months, "reason": reason if months else None, "wording": _text(cb.get("wording"), 200) if months else ""}

    p["goal"] = _text(p.get("goal"), 200)
    p["background"] = _text(p.get("background"), 300)

    wc = p.get("work_conditions") or {}
    modes = [m for m in WORK_MODES if m in (wc.get("work_modes") or [])]
    if strict and not modes:
        raise ProfileError("Please choose at least one work mode.")
    p["work_conditions"] = {
        **wc,
        "work_modes": modes,
        "can_relocate": bool(wc.get("can_relocate", False)),
        "commute_city": _text(wc.get("commute_city"), 60) or city,
        "schedule_needs": _text(wc.get("schedule_needs"), 300),
        "weekly_learning_hours": _number(wc.get("weekly_learning_hours") or 6, 1, 60, "Learning hours per week"),
        "learning_pattern": _text(wc.get("learning_pattern"), 200),
    }

    acc = p.get("accommodations") or {}
    shared = acc.get("shareable_work_accommodations") or []
    if isinstance(shared, str):
        shared = shared.split("\n")
    p["accommodations"] = {**acc, "shareable_work_accommodations": [x for x in (_text(s, 160) for s in shared) if x][:10]}
    return p
