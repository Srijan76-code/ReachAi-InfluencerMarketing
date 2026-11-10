"""Share links (roadmap F1.18): the owner manages links to a campaign's shortlist; anyone holding a
live link can read it, view-only, through the allowlist in app/sharing/view.py.

Personal links can also be reviewer links: 👍/👎 and a comment per creator (F1.18b), shown to the owner.
Contact details are never shared through a link.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import get_db_user
from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.share_link import ShareEvent, ShareFeedback, ShareLink
from app.models.user import User
from app.sharing import view as V

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _link_out(l: ShareLink) -> dict:
    return {
        "id": l.link_id, "kind": l.kind, "email": l.email, "role": l.role,
        "show_prices": l.show_prices,
        "creator_ids": l.creator_ids, "path": f"/s/{l.token}",
        "expires_at": l.expires_at.isoformat() if l.expires_at else None,
        "view_count": l.view_count or 0,
        "last_viewed_at": l.last_viewed_at.isoformat() if l.last_viewed_at else None,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


async def _own_campaign(db: AsyncSession, campaign_id: str, user: User):
    row = (await db.execute(
        select(Campaign.campaign_id, Campaign.campaign_leads)
        .where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Campaign not found")
    return row


async def _own_link(db: AsyncSession, link_id: str, user: User) -> ShareLink:
    link = (await db.execute(
        select(ShareLink).join(Campaign, Campaign.campaign_id == ShareLink.campaign_id)
        .where(ShareLink.link_id == link_id, Campaign.user_id == user.user_id)
    )).scalar_one_or_none()
    if link is None or link.revoked_at is not None:
        raise HTTPException(404, "Link not found")
    return link


def _check_role(kind: str, role: str) -> None:
    if role not in V.ROLES:
        raise HTTPException(422, "Role must be viewer or reviewer.")
    if kind == "anyone" and role != "viewer":
        raise HTTPException(422, "Links for anyone are view-only. Add the person by email to let them review.")


# --- owner ------------------------------------------------------------------------------------

@router.get("/api/campaigns/{campaign_id}/shares")
async def list_shares(campaign_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    await _own_campaign(db, campaign_id, user)
    links = (await db.execute(
        select(ShareLink).where(ShareLink.campaign_id == campaign_id, ShareLink.revoked_at.is_(None))
        .order_by(ShareLink.created_at)
    )).scalars().all()
    now = _now()
    return {"links": [_link_out(l) for l in links if V.is_live(l, now)]}


class NewShare(BaseModel):
    kind: Literal["person", "anyone"]
    email: Optional[str] = None
    role: str = "viewer"
    show_prices: bool = False
    creator_ids: Optional[list[str]] = None  # None = the whole shortlist


@router.post("/api/campaigns/{campaign_id}/shares")
async def create_share(campaign_id: str, body: NewShare, user: User = Depends(get_db_user),
                       db: AsyncSession = Depends(get_db)):
    camp = await _own_campaign(db, campaign_id, user)
    _check_role(body.kind, body.role)
    lead_ids = {l.get("id") for l in (camp.campaign_leads or []) if isinstance(l, dict)}
    if not lead_ids:
        raise HTTPException(422, "Run the search first: there are no creators to share yet.")
    creator_ids = None
    if body.creator_ids is not None:
        creator_ids = [c for c in dict.fromkeys(body.creator_ids) if c in lead_ids]
        if not creator_ids:
            raise HTTPException(422, "Pick at least one creator from this campaign.")
    email = None
    if body.kind == "person":
        email = V.clean_email(body.email or "")
        if not email:
            raise HTTPException(422, "Enter a valid email address.")
    live = [l for l in (await db.execute(
        select(ShareLink).where(ShareLink.campaign_id == campaign_id, ShareLink.revoked_at.is_(None))
    )).scalars().all() if V.is_live(l)]
    if len(live) >= V.MAX_PEOPLE_PER_CAMPAIGN:
        raise HTTPException(422, f"A campaign can have at most {V.MAX_PEOPLE_PER_CAMPAIGN} links. Remove one first.")
    # the same person (or the public link) for the same creators: reuse it, with the new settings
    for l in live:
        if l.kind == body.kind and l.email == email and (l.creator_ids or None) == creator_ids:
            l.show_prices, l.role = body.show_prices, body.role
            await db.commit()
            return _link_out(l)
    link = ShareLink(
        campaign_id=campaign_id, created_by=user.user_id, token=V.new_token(), kind=body.kind, email=email,
        role=body.role, show_prices=body.show_prices, creator_ids=creator_ids,
        expires_at=V.anyone_link_expiry() if body.kind == "anyone" else None, view_count=0,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _link_out(link)


class ShareChange(BaseModel):
    show_prices: Optional[bool] = None
    role: Optional[str] = None


@router.patch("/api/shares/{link_id}")
async def change_share(link_id: str, body: ShareChange, user: User = Depends(get_db_user),
                       db: AsyncSession = Depends(get_db)):
    link = await _own_link(db, link_id, user)
    role = body.role if body.role is not None else link.role
    _check_role(link.kind, role)
    if body.show_prices is not None:
        link.show_prices = body.show_prices
    link.role = role
    await db.commit()
    return _link_out(link)


@router.delete("/api/shares/{link_id}")
async def revoke_share(link_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Turns the link off at once. The row stays, so its view count and feedback are kept."""
    link = await _own_link(db, link_id, user)
    link.revoked_at = _now()
    await db.commit()
    return {"revoked": link_id}


@router.get("/api/campaigns/{campaign_id}/feedback")
async def campaign_feedback(campaign_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """What reviewers said, newest first. Feedback from links that were removed later is kept."""
    await _own_campaign(db, campaign_id, user)
    rows = (await db.execute(
        select(ShareFeedback, ShareLink.email)
        .join(ShareLink, ShareLink.link_id == ShareFeedback.link_id)
        .where(ShareFeedback.campaign_id == campaign_id)
        .order_by(ShareFeedback.updated_at.desc())
    )).all()
    return [
        {"creator_id": f.creator_id, "by": email, "verdict": f.verdict, "comment": f.comment,
         "updated_at": f.updated_at.isoformat() if f.updated_at else None}
        for f, email in rows if f.verdict or f.comment
    ]


@router.get("/api/campaigns/{campaign_id}/share-activity")
async def share_activity(campaign_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Everything for the Sharing panel in one call: who has access and what they did (people), what happened
    when (events, newest first) and what was said about each creator (by_creator)."""
    camp = await _own_campaign(db, campaign_id, user)
    leads = {l.get("id"): l for l in (camp.campaign_leads or []) if isinstance(l, dict)}
    links = {l.link_id: l for l in (await db.execute(select(ShareLink).where(ShareLink.campaign_id == campaign_id))).scalars().all()}
    feedback = (await db.execute(
        select(ShareFeedback).where(ShareFeedback.campaign_id == campaign_id).order_by(ShareFeedback.updated_at.desc())
    )).scalars().all()
    events = (await db.execute(
        select(ShareEvent).where(ShareEvent.campaign_id == campaign_id).order_by(ShareEvent.created_at.desc()).limit(V.ACTIVITY_LIMIT)
    )).scalars().all()

    def who(link_id: str) -> str:
        l = links.get(link_id)
        return (l.email if l and l.email else "Someone with the public link") if l else "Someone"

    def creator(cid: Optional[str]) -> dict:
        lead = leads.get(cid) or {}
        return {"creator_id": cid, "name": lead.get("title") or cid, "avatar_url": lead.get("avatar_url")}

    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    now = _now()
    people = []
    for l in links.values():
        if l.revoked_at is not None or not V.is_live(l, now):
            continue
        mine = [f for f in feedback if f.link_id == l.link_id and (f.verdict or f.comment)]
        scope = len(l.creator_ids) if l.creator_ids else len(leads)
        people.append({
            "link_id": l.link_id, "kind": l.kind, "email": l.email, "role": l.role, "view_count": l.view_count or 0,
            "last_viewed_at": iso(l.last_viewed_at), "creators": scope, "reviewed": len([f for f in mine if f.verdict]),
            "yes": sum(1 for f in mine if f.verdict == "yes"), "no": sum(1 for f in mine if f.verdict == "no"),
        })
    by_creator: dict[str, dict] = {}
    for f in feedback:
        if not (f.verdict or f.comment):
            continue
        row = by_creator.setdefault(f.creator_id, {**creator(f.creator_id), "yes": 0, "no": 0, "notes": []})
        row["yes"] += f.verdict == "yes"
        row["no"] += f.verdict == "no"
        row["notes"].append({"by": who(f.link_id), "verdict": f.verdict, "comment": f.comment, "at": iso(f.updated_at)})
    return {
        "people": sorted(people, key=lambda p: p["last_viewed_at"] or "", reverse=True),
        "events": [{"type": e.type, "by": who(e.link_id), **({} if e.type == "opened" else creator(e.creator_id)),
                    "verdict": e.verdict, "comment": e.comment, "at": iso(e.created_at)} for e in events],
        "by_creator": sorted(by_creator.values(), key=lambda r: (r["no"] - r["yes"], r["name"] or "")),
        "latest_at": iso(events[0].created_at) if events else None,
    }


# --- public -----------------------------------------------------------------------------------

PRIVATE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"}


def _private(body: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=PRIVATE)


async def _live_link(db: AsyncSession, token: str) -> ShareLink | JSONResponse:
    link = (await db.execute(select(ShareLink).where(ShareLink.token == token))).scalar_one_or_none()
    if link is None:
        return _private({"detail": "This link doesn't exist."}, 404)
    if not V.is_live(link):
        return _private({"detail": "This link has expired or was turned off by its owner."}, 410)
    return link


@router.get("/api/share/{token}")
async def open_share(token: str, db: AsyncSession = Depends(get_db)):
    """No sign-in: the token is the permission. Unknown → 404; turned off or expired → 410."""
    link = await _live_link(db, token)
    if isinstance(link, JSONResponse):
        return link
    camp = (await db.execute(
        select(Campaign.name, Campaign.campaign_details, Campaign.campaign_leads)
        .where(Campaign.campaign_id == link.campaign_id)
    )).one()
    now = _now()
    last = link.last_viewed_at
    if last is None or (last if last.tzinfo else last.replace(tzinfo=timezone.utc)) < now - timedelta(minutes=V.OPEN_EVENT_GAP_MINUTES):
        db.add(ShareEvent(link_id=link.link_id, campaign_id=link.campaign_id, type="opened"))
    await db.execute(update(ShareLink).where(ShareLink.link_id == link.link_id).values(
        view_count=ShareLink.view_count + 1, last_viewed_at=now))
    my_feedback = {}
    if link.role == "reviewer":
        my_feedback = {f.creator_id: {"verdict": f.verdict, "comment": f.comment} for f in (await db.execute(
            select(ShareFeedback).where(ShareFeedback.link_id == link.link_id))).scalars().all()}
    await db.commit()
    from app.api.campaign_names import DEFAULT_NAME, is_default, name_from_brief

    name = (name_from_brief(camp.campaign_details) if is_default(camp.name) else camp.name) or DEFAULT_NAME
    out = V.shared_view(name, camp.campaign_details, camp.campaign_leads, link)
    out.update({"can_review": link.role == "reviewer", "my_feedback": my_feedback})
    return _private(out)


class FeedbackIn(BaseModel):
    verdict: Optional[Literal["yes", "no"]] = None
    comment: Optional[str] = None


@router.put("/api/share/{token}/feedback/{creator_id}")
async def give_feedback(token: str, creator_id: str, body: FeedbackIn, db: AsyncSession = Depends(get_db)):
    """A reviewer's 👍/👎 and comment on one creator in their link (the latest answer wins)."""
    link = await _live_link(db, token)
    if isinstance(link, JSONResponse):
        return link
    if link.role != "reviewer":
        return _private({"detail": "This link is view-only."}, 403)
    leads = (await db.execute(select(Campaign.campaign_leads).where(Campaign.campaign_id == link.campaign_id))).scalar_one()
    in_scope = {l.get("id") for l in (leads or []) if isinstance(l, dict)}
    if link.creator_ids:
        in_scope &= set(link.creator_ids)
    if creator_id not in in_scope:
        return _private({"detail": "That creator isn't in this shortlist."}, 404)
    comment = (body.comment or "").strip()[: V.MAX_COMMENT_CHARS] or None
    row = (await db.execute(select(ShareFeedback).where(
        ShareFeedback.link_id == link.link_id, ShareFeedback.creator_id == creator_id))).scalar_one_or_none()
    if row is None:
        row = ShareFeedback(link_id=link.link_id, campaign_id=link.campaign_id, creator_id=creator_id)
        db.add(row)
    row.verdict, row.comment = body.verdict, comment
    row.updated_at = _now()
    db.add(ShareEvent(link_id=link.link_id, campaign_id=link.campaign_id, type="feedback", creator_id=creator_id,
                      verdict=body.verdict, comment=comment))
    await db.commit()
    return _private({"creator_id": creator_id, "verdict": row.verdict, "comment": row.comment})
