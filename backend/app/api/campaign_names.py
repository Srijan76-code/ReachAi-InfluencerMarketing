"""Campaign names made from the brief ("DataLaunch · Sales · India"), so the campaigns page never
fills up with "Untitled Campaign". A name the user typed is never replaced."""

from __future__ import annotations

from typing import Optional

from app.core.countries import COUNTRY_NAMES

DEFAULT_NAME = "Untitled Campaign"
MAX_NAME_LENGTH = 80
EMPTY_DRAFT_HIDDEN_AFTER_DAYS = 1  # drafts never run (no brief saved) drop off the campaigns list

GOALS = {"awareness": "Awareness", "signups": "Signups", "sales": "Sales"}



def is_default(name: Optional[str]) -> bool:
    return not (name or "").strip() or name.strip() == DEFAULT_NAME


def name_from_brief(details: Optional[dict]) -> Optional[str]:
    """"{brand} · {goal} · {countries}", or None when the brief has no brand yet."""
    d = details or {}
    brand = str((d.get("brand") or {}).get("name") or "").strip()
    if not brand:
        return None
    parts = [brand]
    goal = GOALS.get(str((d.get("campaign") or {}).get("goal") or "").lower())
    if goal:
        parts.append(goal)
    codes = (d.get("constraints") or {}).get("target_countries") or (d.get("audience") or {}).get("locations") or []
    codes = [str(c).strip().upper() for c in codes if str(c).strip()]
    if codes:
        first = COUNTRY_NAMES.get(codes[0], codes[0])
        parts.append(first if len(codes) == 1 else f"{first} +{len(codes) - 1}")
    return clean_name(" · ".join(parts))


def clean_name(name: str) -> str:
    """One line, trimmed, at most MAX_NAME_LENGTH characters."""
    one_line = " ".join(str(name).split())
    return one_line[:MAX_NAME_LENGTH].rstrip()
