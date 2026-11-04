"""Campaign names made from the brief ("DataLaunch · Sales · India"), so the campaigns page never
fills up with "Untitled Campaign". A name the user typed is never replaced."""

from __future__ import annotations

from typing import Optional

DEFAULT_NAME = "Untitled Campaign"
MAX_NAME_LENGTH = 80
EMPTY_DRAFT_HIDDEN_AFTER_DAYS = 1  # drafts never run (no brief saved) drop off the campaigns list

GOALS = {"awareness": "Awareness", "signups": "Signups", "sales": "Sales"}

# Names for the countries briefs use most; anything else shows its ISO code.
COUNTRY_NAMES = {
    "IN": "India", "US": "United States", "GB": "UK", "CA": "Canada", "AU": "Australia", "AE": "UAE",
    "SG": "Singapore", "DE": "Germany", "FR": "France", "ES": "Spain", "IT": "Italy", "NL": "Netherlands",
    "IE": "Ireland", "NZ": "New Zealand", "BR": "Brazil", "MX": "Mexico", "ID": "Indonesia", "PH": "Philippines",
    "MY": "Malaysia", "PK": "Pakistan", "BD": "Bangladesh", "NG": "Nigeria", "KE": "Kenya", "ZA": "South Africa",
    "EG": "Egypt", "SA": "Saudi Arabia", "JP": "Japan", "KR": "South Korea", "VN": "Vietnam", "TH": "Thailand",
    "TR": "Turkey", "PL": "Poland", "SE": "Sweden", "CH": "Switzerland", "LK": "Sri Lanka", "NP": "Nepal",
}


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
