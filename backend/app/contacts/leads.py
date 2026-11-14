"""Finding contacts for a campaign's chosen creators, when outreach starts (spec §7.1). Results are saved on the
lead (`contact`, `first_name`, `socials`), on the creator (reused for 30 days, across campaigns and users) and on
the creator's deal (`contact_email`, unless the founder typed one)."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.contacts.find import find_many, fresh
from app.contacts.ledger import contacted_recently, suppressed

logger = logging.getLogger(__name__)

SOCIAL_KEYS = {"instagram": "instagram", "x": "twitter", "linkedin": "linkedin"}


def _profile_ids(lead: dict) -> list[str]:
    ids = [lead.get("creator_id")]
    ids += [a.get("creator_id") for a in lead.get("accounts") or [] if a.get("status") in ("main", "linked")]
    return [i for i in dict.fromkeys(ids) if i]


def _fallback_profile(lead: dict) -> dict:
    """Old leads with no creator row: what the lead itself says."""
    email = (lead.get("socials") or {}).get("email")
    return {"platform": (lead.get("platform") or "youtube").lower(), "display_name": lead.get("title"),
            "bio": lead.get("description") or "", "external_links": [], "contacts": {"emails": [email] if email else []}}


async def _count_shared(session_factory, email: str, own_ids: set) -> int:
    """How many other people list this address (agency and sponsor inboxes show up on many creators)."""
    from app.models.creator import Creator

    async with session_factory() as s:
        rows = (await s.execute(select(Creator.creator_id, Creator.person_id, Creator.contacts)
                                .where(cast(Creator.contacts, String).like(f"%{email}%")).limit(50))).all()
    people = set()
    for cid, pid, contacts in rows:
        if cid in own_ids:
            continue
        emails = {str(e).lower() for e in (contacts or {}).get("emails") or []}
        found = ((contacts or {}).get("found") or {}).get("email")
        if email in emails or found == email:
            people.add(pid or cid)
    return len(people)


def apply_contact(lead: dict, found: dict) -> dict:
    """The lead with the search result on it. The found address replaces the one copied from the bio at
    search time (that was just the first match, sometimes a sponsor's)."""
    socials = dict(lead.get("socials") or {})
    socials["email"] = found.get("email")
    for src, key in SOCIAL_KEYS.items():
        if not socials.get(key) and (found.get("socials") or {}).get(src):
            socials[key] = found["socials"][src]
    return {**lead, "socials": socials, "contact": found, "first_name": found.get("first_name")}


async def find_for_leads(db: AsyncSession, campaign, creator_ids: list[str], *, user_id: Optional[str],
                         judge=None, session_factory=None) -> dict[str, dict]:
    """Finds and saves contacts for these leads. Returns {lead id: contact}. Never raises."""
    from app.billing.costs import CostContext
    from app.creators.repository import _factory, get_creators
    from app.judge.client import judge as jev
    from app.models.creator import Creator
    from app.models.deal import CreatorDeal

    factory = _factory(session_factory)
    leads = {str(l.get("id")): l for l in campaign.campaign_leads or []}
    wanted = [i for i in dict.fromkeys(creator_ids) if i in leads]
    if not wanted:
        return {}
    try:
        all_ids = [i for cid in wanted for i in _profile_ids(leads[cid])]
        profiles = await get_creators(all_ids, session_factory=session_factory) if all_ids else {}
        cached: dict[str, dict] = {}
        todo: list[tuple[str, list[dict]]] = []
        for cid in wanted:
            lead = leads[cid]
            ps = [profiles[i] for i in _profile_ids(lead) if i in profiles] or [_fallback_profile(lead)]
            saved = ((ps[0].get("contacts") or {}).get("found")) if ps[0].get("creator_id") else None
            if fresh(saved):
                cached[cid] = saved
            else:
                todo.append((cid, ps))
        ctx = CostContext(user_id=user_id, campaign_id=campaign.campaign_id)

        async def ask(state, questions):
            return await (judge or jev)(state, questions, **({} if judge else {"context": ctx}))

        found = await find_many(todo, judge=ask, count_shared=lambda e, own: _count_shared(factory, e, own)) if todo else {}
    except Exception as exc:  # noqa: BLE001 - outreach goes on without found contacts
        logger.warning("contact search failed for campaign %s: %s", campaign.campaign_id, exc)
        return {}

    results = {**cached, **found}
    # an address someone opted out from, or that bounced, is never used
    for cid, f in results.items():
        if f.get("email") and await suppressed(db, f["email"]):
            results[cid] = {**f, "email": None, "email_source": None, "suppressed": True}
    if user_id:
        seen = await contacted_recently(db, user_id, [f["email"] for f in results.values() if f.get("email")],
                                        not_campaign=campaign.campaign_id)
        for cid, f in results.items():
            if f.get("email") in seen:
                results[cid] = {**f, "contacted_before": seen[f["email"]].isoformat()}

    old_email = {cid: (leads[cid].get("socials") or {}).get("email") for cid in results}
    campaign.campaign_leads = [apply_contact(l, results[str(l.get("id"))]) if str(l.get("id")) in results else l
                               for l in campaign.campaign_leads or []]
    flag_modified(campaign, "campaign_leads")

    # the creator row keeps the result for 30 days (main account only)
    for cid, f in found.items():
        main = leads[cid].get("creator_id")
        row = await db.get(Creator, main) if main else None
        if row is not None:
            row.contacts = {**(row.contacts or {}), "found": {k: v for k, v in f.items() if k not in ("contacted_before", "suppressed")}}
            flag_modified(row, "contacts")

    deals = (await db.execute(select(CreatorDeal).where(CreatorDeal.campaign_id == campaign.campaign_id,
                                                        CreatorDeal.creator_id.in_(list(results))))).scalars().all()
    for d in deals:
        # the founder's own edit wins: only fill an empty address or replace the one we copied earlier
        if not d.contact_email or d.contact_email == old_email.get(d.creator_id):
            d.contact_email = results[d.creator_id].get("email")
    return results
