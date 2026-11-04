"""The counter-offer message (spec §8.7): code sets every number and writes an instant template; Jev reads
the creator's pasted reply to pick the angle; the LLM (route "counter") may reword it, and code checks the
wording keeps exactly our numbers, else the template is used.

The creator's reply is untrusted (rule 7): only Jev reads it, and only to answer yes/no questions. It's
never shown to the LLM, and nothing it says can change a price or trigger an action.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.billing.costs import CostContext
from app.deals import constants as C
from app.deals import negotiation as N

logger = logging.getLogger(__name__)

_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
MAX_MESSAGE_CHARS = 900


async def read_reply(text: str, context: CostContext, thread: Optional[dict] = None) -> dict:
    """Jev's yes/no reading of the creator's reply → {signal: probability}. {} if Jev is unavailable.
    `thread` (optional) is the negotiation so far in words written by code (our last offer, their last ask,
    which round), so "sounds good" is read against what was actually offered."""
    from app.judge.client import judge
    from app.judge.questions import creator_reply_questions

    text = (text or "").strip()[: C.MAX_REPLY_CHARS]
    if not text:
        return {}
    try:
        state = {"reply": {"text": text}}
        if thread:
            state["thread"] = thread
        j = await judge(state, creator_reply_questions(), context=context)
    except Exception as exc:  # the template still works without it
        logger.warning("reading the creator's reply failed: %s", type(exc).__name__)
        return {}
    from app.judge import constants as K

    signals = {q: round(j.noul(q), 3) for q in j.answers}
    if signals.get("injection", 0) > K.REPLY_INJECTION_ABOVE:
        return {"ignored": True}
    return signals


def allowed(text: str, amounts: dict) -> bool:
    """The wording may only contain our money figures and percentages, and must contain the main one."""
    money = {int(round(float(m.replace(",", "")))) for m in _MONEY.findall(text)}
    # only the amounts the message offers: a base + commission offer may not also quote the full counter
    # (that's how "lower than the $65 we discussed" got through)
    allowed_money = {int(v) for k, v in amounts.items() if k != "commission_pct" and not (k == "counter" and "base" in amounts)}
    if not money or not money <= allowed_money:
        return False
    pcts = {float(p) for p in _PERCENT.findall(text)}
    if pcts and pcts != {float(amounts.get("commission_pct", -1))}:
        return False
    main = amounts.get("price") or amounts.get("base") or amounts.get("counter")
    return int(main) in money and len(text) <= MAX_MESSAGE_CHARS


def _prompt(facts: dict) -> list:
    from langchain_core.messages import HumanMessage, SystemMessage

    return [
        SystemMessage(content=(
            "You write short, friendly negotiation messages from a startup founder to a content creator. "
            "Rules: use ONLY the dollar amounts and percentages given in `amounts`, written exactly as given, "
            "and no other prices or numbers of money; don't invent facts, dates or promises; plain text, no "
            "subject line, 50-90 words, start with 'Hi {first name},'; warm, respectful, specific; end with a "
            "simple question."
        )),
        HumanMessage(content=f"Write the message for these facts (JSON):\n{facts}"),
    ]


async def rewrite(*, name: str, angle: str, amounts: dict, deliverable: str, usage_rights: str,
                  exclusivity_days: int, post_by: Optional[str], typical_views: Optional[float],
                  goal: Optional[str], fallback: str, context: CostContext) -> tuple[str, str]:
    """(message, source). source = "ai" when the LLM's wording passed the checks, else "template"."""
    from app.llm.client import LLMUnavailableError, achat

    facts = {
        "creator_first_name": N.greeting_name(name),
        "angle": {"accept": "accept their price", "budget": "counter with our budget",
                  "performance": "offer a lower fee plus commission on sales",
                  "scope": "keep their price but drop paid-ads use and exclusivity, or pay the counter for the full package"}[angle],
        "amounts": {k: (f"${v:,}" if k != "commission_pct" else f"{v}%") for k, v in amounts.items()},
        "deliverable": N.DELIVERABLE_WORDS.get(deliverable, deliverable),
        "usage": N.USAGE_WORDS.get(usage_rights, "").strip(" ()") or "creator's own channel only",
        "exclusivity_days": exclusivity_days or None,
        "post_by": post_by,
        "their_typical_views": N._views(typical_views) if typical_views else None,
        "campaign_goal": goal,
    }
    try:
        text = await achat("counter", _prompt(facts), context=context, temperature=0.5)
    except LLMUnavailableError:
        return fallback, "template"
    text = (text or "").strip() if isinstance(text, str) else ""
    if not allowed(text, amounts):
        logger.info("counter rewrite rejected (numbers or length); using the template")
        return fallback, "template"
    return text, "ai"
