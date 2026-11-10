"""Checks an agent-written first message before it is saved (spec §15.5).

The agent writes the words. These checks keep the parts that must come from code: the message may not
quote a price above the creator's fair-high figure, expose internal scoring fields or package details,
or ship with placeholders. It reuses the banned patterns of the app's own pitch validator, so an agent
draft is held to the same house rules as one written by ReachAI.
"""

import re

from app.outreach.nodes.validate_creator_pitch import FORMULAIC_OPENERS, INTERNAL_TERMS, PACKAGE_DETAIL_PATTERNS

MIN_CHARS = 40
MAX_CHARS = 2700  # same cap the approve route applies to a message
MAX_SUBJECT_CHARS = 200
MAX_QUESTIONS = 2
MAX_LINKS = 2

_PLACEHOLDER = re.compile(r"\[[^\]\n]{1,40}\]|\{\{.*?\}\}|<[A-Z][A-Z _]{2,30}>|lorem ipsum|\b(?:insert|your name|company name)\b[^.\n]{0,20}\bhere\b", re.I)
_LINK = re.compile(r"https?://\S+|www\.\S+", re.I)
_SYMBOL_AMOUNT = re.compile(r"(?:[$€£₹]|\b(?:usd|inr|eur|gbp|rs\.?)\s?)\s?(\d[\d,]*(?:\.\d+)?)\s?(k|m)?\b", re.I)
_WORD_AMOUNT = re.compile(r"\b(\d[\d,]*(?:\.\d+)?)\s?(k|m)?\s?(?:usd|dollars?|inr|rupees?|eur|euros?|gbp|pounds?)\b", re.I)
_FIRST_NAME_MIN = 3


def amounts_in(text: str) -> list[float]:
    """Every money amount the text states, as numbers (1.5k -> 1500)."""
    found = []
    for pattern in (_SYMBOL_AMOUNT, _WORD_AMOUNT):
        for number, suffix in pattern.findall(text):
            try:
                value = float(number.replace(",", ""))
            except ValueError:
                continue
            found.append(value * {"k": 1_000, "m": 1_000_000}.get(suffix.lower(), 1))
    return found


def _mentions_name(text_lower: str, name: str) -> bool:
    name = name.strip().lower()
    if not name or name == "unknown creator":
        return True
    if name in text_lower:
        return True
    first = name.split()[0]
    return len(first) >= _FIRST_NAME_MIN and re.search(rf"\b{re.escape(first)}\b", text_lower) is not None


def check_first_message(
    body: str,
    *,
    subject: str | None = None,
    brand_name: str = "",
    creator_name: str = "",
    fair_high: float | None = None,
) -> list[str]:
    """Returns what must change (empty list = fine). Messages are written for the agent to act on."""
    errors: list[str] = []
    text = (body or "").strip()
    lower = text.lower()

    if len(text) < MIN_CHARS:
        errors.append(f"The message is too short (at least {MIN_CHARS} characters).")
    if len(text) > MAX_CHARS:
        errors.append(f"The message is too long (at most {MAX_CHARS} characters).")
    if subject is not None and len(subject.strip()) > MAX_SUBJECT_CHARS:
        errors.append(f"The subject is too long (at most {MAX_SUBJECT_CHARS} characters).")
    if _PLACEHOLDER.search(text) or (subject and _PLACEHOLDER.search(subject)):
        errors.append("Remove placeholder text such as [Name] or {{brand}}: write the real values.")
    if brand_name and brand_name.strip().lower() not in lower:
        errors.append(f"Name the brand ({brand_name.strip()}) in the message.")
    if creator_name and not _mentions_name(lower, creator_name):
        errors.append(f"Address the creator by name ({creator_name.strip()}).")

    for term in INTERNAL_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            errors.append(f"Do not mention internal scoring fields ({term}).")
    for pattern, description in PACKAGE_DETAIL_PATTERNS:
        if re.search(pattern, lower):
            errors.append(f"Do not spell out package details in a first message ({description}).")
    for opener in FORMULAIC_OPENERS:
        if opener in lower:
            errors.append(f'Do not use the stock opener "{opener}".')
    for raw in ("sponsored_video", "dedicated_video", "product_placement", "shoutout_mention"):
        if raw in lower:
            errors.append(f"Do not use the internal term {raw}.")
    if text.count("?") > MAX_QUESTIONS:
        errors.append(f"Ask at most {MAX_QUESTIONS} questions.")
    if len(_LINK.findall(text)) > MAX_LINKS:
        errors.append(f"Include at most {MAX_LINKS} links.")

    stated = amounts_in(text)
    if stated:
        if fair_high is None or fair_high <= 0:
            errors.append("Do not state a price: ReachAI has no fair price for this creator yet. Ask the founder to set one in the app.")
        elif max(stated) > fair_high:
            errors.append(
                f"The message states ${max(stated):,.0f}, above this creator's fair-high price of ${fair_high:,.2f}. "
                "Prices come from ReachAI: lower it, or leave the price out of a first message."
            )
    return errors
