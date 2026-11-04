"""Share links (roadmap F1.18): the owner manages links to a campaign's shortlist; anyone holding a
live link can read it, view-only, through the allowlist in app/sharing/view.py."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import get_db_user
from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.share_link import ShareLink
from app.models.user import User
from app.sharing import view as V

router = APIRouter()


def _link_out(l: ShareLink) -> dict:
    return {
        "id": l.link_id, "kind": l.kind, "email": l.email, "role": l.role,
        "show_prices": l.show_prices, "show_contacts": l.show_contacts,
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


# --- owner ------------------------------------------------------------------------------------

@router.get("/api/campaigns/{campaign_id}/shares")
async def list_shares(campaign_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    await _own_campaign(db, campaign_id, user)
    links = (await db.execute(
        select(ShareLink).where(ShareLink.campaign_id == campaign_id, ShareLink.revoked_at.is_(None))
        .order_by(ShareLink.created_at)
    )).scalars().all()
    now = datetime.now(timezone.utc)
    return [_link_out(l) for l in links if V.is_live(l, now)]


class NewShare(BaseModel):
    kind: Literal["person", "anyone"]
    email: Optional[str] = None
    show_prices: bool = False
    creator_ids: Optional[list[str]] = None  # None = the whole shortlist


@router.post("/api/campaigns/{campaign_id}/shares")
async def create_share(campaign_id: str, body: NewShare, user: User = Depends(get_db_user),
                       db: AsyncSession = Depends(get_db)):
    camp = await _own_campaign(db, campaign_id, user)
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
    # the same person (or the public link) for the same creators: reuse it, with the new price setting
    for l in live:
        if l.kind == body.kind and l.email == email and (l.creator_ids or None) == creator_ids:
            l.show_prices = body.show_prices
            await db.commit()
            return _link_out(l)
    link = ShareLink(
        campaign_id=campaign_id, created_by=user.user_id, token=V.new_token(), kind=body.kind, email=email,
        role="viewer", show_prices=body.show_prices, show_contacts=False, creator_ids=creator_ids,
        expires_at=V.anyone_link_expiry() if body.kind == "anyone" else None, view_count=0,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _link_out(link)


class ShareChange(BaseModel):
    show_prices: Optional[bool] = None


@router.patch("/api/shares/{link_id}")
async def change_share(link_id: str, body: ShareChange, user: User = Depends(get_db_user),
                       db: AsyncSession = Depends(get_db)):
    link = await _own_link(db, link_id, user)
    if body.show_prices is not None:
        link.show_prices = body.show_prices
    await db.commit()
    return _link_out(link)


@router.delete("/api/shares/{link_id}")
async def revoke_share(link_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Turns the link off at once. The row stays, so its view count is kept."""
    link = await _own_link(db, link_id, user)
    link.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"revoked": link_id}


# --- public -----------------------------------------------------------------------------------

PRIVATE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"}


@router.get("/api/share/{token}")
async def open_share(token: str, db: AsyncSession = Depends(get_db)):
    """No sign-in: the token is the permission. Unknown → 404; turned off or expired → 410."""
    link = (await db.execute(select(ShareLink).where(ShareLink.token == token))).scalar_one_or_none()
    if link is None:
        return JSONResponse({"detail": "This link doesn't exist."}, status_code=404, headers=PRIVATE)
    if not V.is_live(link):
        return JSONResponse({"detail": "This link has expired or was turned off by its owner."}, status_code=410,
                            headers=PRIVATE)
    camp = (await db.execute(
        select(Campaign.name, Campaign.campaign_details, Campaign.campaign_leads)
        .where(Campaign.campaign_id == link.campaign_id)
    )).one()
    await db.execute(update(ShareLink).where(ShareLink.link_id == link.link_id).values(
        view_count=ShareLink.view_count + 1, last_viewed_at=datetime.now(timezone.utc)))
    await db.commit()
    from app.api.campaign_names import DEFAULT_NAME, is_default, name_from_brief

    name = (name_from_brief(camp.campaign_details) if is_default(camp.name) else camp.name) or DEFAULT_NAME
    return JSONResponse(V.shared_view(name, camp.campaign_details, camp.campaign_leads, link), headers=PRIVATE)
