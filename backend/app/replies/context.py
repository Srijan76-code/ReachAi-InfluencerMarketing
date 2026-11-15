"""Everything the reply writer may use, gathered (not decided) in code (spec §8.6c):

- `facts`: what may be said about the brand, campaign and terms, each with an id (from the brief, and from the
  founder's own answers in memory). The only brand information the writer may state.
- `founder_voice`: the founder's own messages (sent by hand, or edited before sending) plus style rules.
- `conversation`: the whole conversation, oldest first. `creator_message`: their latest message (untrusted).
- `creator` + `latest_posts`: who they are and what they posted recently.
- `deal`: fair price range, budget left, offers so far and the hard limit (private: never shown to the creator).
- `lessons`: checks this founder's drafts failed before."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deals import negotiation as N
from app.replies import constants as R

GOALS = {"signups": "app or product signups", "sales": "sales", "awareness": "awareness", "traffic": "website visits"}


@dataclass
class Limits:
    """Hard limits, checked in code after every draft (never left to a model)."""
    ceiling: Optional[int]  # never offer more than this fee
    floor: Optional[int]  # never offer less than our last offer (we don't go back down)
    max_commission: float = R.MAX_COMMISSION_PCT
    agreed: Optional[tuple] = None  # (fee, commission_pct) once a price is agreed: never changed by the agent


@dataclass
class ReplyContext:
    facts: list[dict]  # [{"id", "text"}]
    founder_voice: dict  # {"examples": [...], "style_rules": [...]}
    conversation: list[dict]  # [{"from": "you"|"creator", "text"}]
    creator_message: str
    creator: dict
    latest_posts: list[dict]
    deal: dict
    lessons: list[str]
    limits: Limits
    mode: str = "reply"  # reply | follow_up
    founder_answers: list[dict] = field(default_factory=list)  # answers the founder just gave for this creator

    def for_writer(self) -> dict:
        return {"facts": self.facts, "founder_voice": self.founder_voice, "conversation": self.conversation,
                "creator_message": self.creator_message, "creator": self.creator, "latest_posts": self.latest_posts,
                "deal": self.deal, "lessons": self.lessons, "mode": self.mode}

    def sources(self) -> dict:
        """What a draft may draw on (for Jev's grounding check)."""
        return {"facts": [f["text"] for f in self.facts], "conversation": self.conversation,
                "creator": {k: v for k, v in self.creator.items() if k in ("name", "first_name", "platform")},
                "latest_posts": [p.get("title") for p in self.latest_posts]}


def brief_facts(details: dict) -> list[dict]:
    """What the founder told ReachAI in the brief that may be said to a creator. Budget and the creator size
    filters are private and never become facts."""
    details = details or {}
    brand, camp, aud = details.get("brand") or {}, details.get("campaign") or {}, details.get("audience") or {}
    out = []

    def add(key, text):
        if text:
            out.append({"id": key, "text": text})

    name = (brand.get("name") or "").strip()
    add("brand", f"The brand is {name}." if name else None)
    add("product", f"{name or 'The product'}: {brand.get('core_outcome').strip()}" if brand.get("core_outcome") else None)
    add("industry", f"Industry: {brand['industry']}." if brand.get("industry") and brand["industry"] != "other" else None)
    add("website", f"Website: {brand['website']}" if brand.get("website") else None)
    add("audience", f"Who it's for: {aud['target_persona']}." if aud.get("target_persona") else None)
    add("goal", f"What the campaign is for: {GOALS.get(camp.get('goal'), camp.get('goal'))}." if camp.get("goal") else None)
    return out


def _clip(text, n=R.MAX_TURN_CHARS) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


async def founder_voice(db: AsyncSession, user_id: str, style_rules: list[str]) -> dict:
    """The founder's own words: messages they wrote or edited before sending, newest first."""
    from app.models.campaign import Campaign
    from app.models.deal import CreatorDeal, DealEvent

    rows = (await db.execute(
        select(DealEvent.payload).join(CreatorDeal, CreatorDeal.deal_id == DealEvent.deal_id)
        .join(Campaign, Campaign.campaign_id == CreatorDeal.campaign_id)
        .where(Campaign.user_id == user_id, DealEvent.type == "message_sent")
        .order_by(DealEvent.created_at.desc()).limit(60))).scalars().all()
    examples = []
    for p in rows:
        p = p or {}
        if p.get("text") and (p.get("kind") == "manual" or p.get("edited")) and not p.get("auto"):
            examples.append(_clip(p["text"], 900))
        if len(examples) >= R.MAX_EXAMPLES:
            break
    return {"examples": examples, "style_rules": style_rules[: R.MAX_STYLE_RULES]}


def conversation(events) -> list[dict]:
    out = []
    for e in sorted(events, key=lambda e: e.created_at or 0):
        p = e.payload or {}
        if e.type == "message_sent" and p.get("text"):
            out.append({"from": "you", "text": _clip(p["text"])})
        elif e.type == "creator_reply" and p.get("text"):
            out.append({"from": "creator", "text": _clip(p["text"])})
    return out[-R.MAX_HISTORY_TURNS:]


def latest_posts(lead: dict) -> list[dict]:
    posts = []
    for v in (lead or {}).get("recent_videos") or (lead or {}).get("posts") or []:
        if isinstance(v, dict) and (v.get("title") or v.get("text")):
            posts.append({"title": _clip(v.get("title") or v.get("text"), 200), "published_at": v.get("published_at")})
    return posts[: R.MAX_POSTS]


def deal_facts(d, f, *, budget_left: Optional[float]) -> tuple[dict, Limits]:
    """`f`: app.negotiation.context.Facts (fair range from code, offers so far)."""
    ceiling = None
    if f.fair_high:
        ceiling = int(f.fair_high * R.CEILING_OVER_FAIR)
        if budget_left is not None:
            ceiling = min(ceiling, int(budget_left))
        ceiling = max(R.MIN_FEE, ceiling)
    floor = f.last_offer.fee if f.last_offer and f.last_offer.fee else None
    if floor is not None and ceiling is not None and floor > ceiling:
        ceiling = floor  # we already offered more: keep to it, never go back on it
    info = {
        "deliverable": N.DELIVERABLE_WORDS.get(d.deliverable, d.deliverable),
        "fair_price_range": f"${f.fair_low:,}–${f.fair_high:,}" if f.fair_high else "unknown",
        "hard_limit": f"${ceiling:,} (never offer more)" if ceiling is not None else "unknown: don't offer a price",
        "budget_left": f"${max(0.0, budget_left):,.0f}" if budget_left is not None else "not set",
        "our_offers_so_far": [o.words() for o in f.our_offers],
        "their_asks_so_far": [o.words() for o in f.their_asks],
        "already_agreed": d.stage in ("agreed", "content", "live", "paid"),
        "agreed_price": f"${d.agreed_rate:,.0f}" if d.agreed_rate else None,
        "usual_views": int(d.typical_views) if d.typical_views else None,
    }
    return info, Limits(ceiling=ceiling, floor=floor)


async def build(db: AsyncSession, d, lead: dict, details: dict, *, user_id: str, creator_message: str, events: list,
                budget_left: Optional[float], mode: str = "reply") -> ReplyContext:
    """Gathers everything for one conversation: brief + remembered facts, the founder's voice, the whole
    conversation, the creator and their latest posts, and the deal's numbers and hard limits."""
    from app.deals import constants as DC
    from app.negotiation import context as X
    from app.replies import memory as M

    mem = await M.load(db, user_id, d.campaign_id)
    f = X.facts(d, events, budget_left=budget_left)
    info, limits = deal_facts(d, f, budget_left=budget_left)
    if d.stage in DC.COMMITTED_STAGES and d.agreed_rate is not None:
        limits.agreed = (int(d.agreed_rate), float(d.commission_pct or 0))
    lead = lead or {}
    creator = {"name": lead.get("title") or d.creator_name, "first_name": lead.get("first_name"),
               "platform": d.platform}
    return ReplyContext(
        facts=brief_facts(details) + mem.facts,
        founder_voice=await founder_voice(db, user_id, mem.style_rules),
        conversation=conversation(events), creator_message=_clip(creator_message, R.MAX_TURN_CHARS),
        creator=creator, latest_posts=latest_posts(lead), deal=info, lessons=mem.lessons, limits=limits, mode=mode)
