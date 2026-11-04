"""Connect Gmail (spec §7.5, roadmap F6.5): the founder signs in with Google once; approved messages then go
out from their own address and creators' replies come back into their deals. Owner only, except the Google
callback, which is tied to the founder by a signed, short-lived state."""

from __future__ import annotations

import os
from datetime import date
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import get_db_user
from app.db.database import get_db
from app.gmail import client as GC
from app.gmail import constants as G
from app.gmail import crypto, service
from app.models.campaign import Campaign
from app.models.deal import ConnectedAccount, CreatorDeal, DealEvent
from app.models.user import User

router = APIRouter()


def _origin(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{host}"


def _redirect_uri(request: Request) -> str:
    return os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or f"{_origin(request)}{G.CALLBACK_PATH}"


def _safe_path(path: Optional[str]) -> str:
    return path if path and path.startswith("/") and not path.startswith("//") else "/campaign"


@router.get("/api/gmail")
async def gmail_status(user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    a = await service.account_for(db, user.user_id)
    return {"configured": GC.configured(), "connected": bool(a), "email": a.email if a else None,
            "needs_reconnect": bool(a and a.status != "active"),
            "sent_today": (a.sent_today if a and a.sent_day == date.today() else 0), "daily_cap": G.DAILY_SEND_CAP}


class ConnectIn(BaseModel):
    return_to: Optional[str] = None  # the page to come back to after signing in with Google


@router.post("/api/gmail/connect")
async def gmail_connect(body: ConnectIn, request: Request, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    if not GC.configured():
        raise HTTPException(503, "Gmail isn't set up on this server yet.")
    a = await service.account_for(db, user.user_id)
    state = crypto.sign_state(user.user_id, _safe_path(body.return_to))
    return {"url": GC.auth_url(_redirect_uri(request), state, login_hint=a.email if a else None)}


@router.get("/api/gmail/callback")
async def gmail_callback(request: Request, state: str = "", code: Optional[str] = None, error: Optional[str] = None,
                         db: AsyncSession = Depends(get_db)):
    """Google sends the founder back here. Errors go back to the page as ?gmail=<reason>; tokens never do."""
    data = crypto.verify_state(state) if state else None
    back = _safe_path((data or {}).get("r"))

    def done(result: str) -> RedirectResponse:
        sep = "&" if "?" in back else "?"
        return RedirectResponse(f"{back}{sep}{urlencode({'gmail': result})}", status_code=302)

    if not data:
        return done("expired")
    if error or not code:
        return done("cancelled")
    try:
        tokens = await GC.exchange_code(code, _redirect_uri(request))
        granted = set((tokens.get("scope") or "").split())
        if not set(G.SCOPES) <= granted:
            return done("missing_permission")  # they unticked "send" or "read" on Google's screen
        if not tokens.get("refresh_token"):
            return done("failed")
        email = (await GC.profile(tokens["access_token"])).get("emailAddress", "").lower()
    except GC.GmailError:
        return done("failed")
    a = await service.account_for(db, data["u"])
    if a is None:
        a = ConnectedAccount(user_id=data["u"], provider="gmail", email=email, refresh_token="", status="active", sent_today=0)
        db.add(a)
    a.email, a.refresh_token, a.status = email, crypto.encrypt(tokens["refresh_token"]), "active"
    await db.commit()
    return done("connected")


@router.delete("/api/gmail")
async def gmail_disconnect(user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    a = await service.account_for(db, user.user_id)
    if a:
        refresh = crypto.decrypt(a.refresh_token)
        if refresh:
            await GC.revoke(refresh)
        await db.delete(a)
        await db.commit()
    return {"connected": False}


@router.post("/api/campaigns/{campaign_id}/gmail/sync")
async def gmail_sync(campaign_id: str, force: bool = False, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Checks this campaign's email threads for new replies (the Deals tab calls it when it opens)."""
    owned = (await db.execute(select(Campaign.campaign_id).where(Campaign.campaign_id == campaign_id,
                                                                  Campaign.user_id == user.user_id))).scalar_one_or_none()
    if owned is None:
        raise HTTPException(404, "Campaign not found")
    a = await service.account_for(db, user.user_id)
    if not service.usable(a):
        return {"new": 0, "connected": bool(a)}
    deals = list((await db.execute(select(CreatorDeal).where(CreatorDeal.campaign_id == campaign_id))).scalars())
    return {"new": await service.sync_deals(db, a, deals, user_id=user.user_id, force=force), "connected": True}


class FirstMessage(BaseModel):
    creator_id: str
    subject: str
    body: str
    to: Optional[str] = None  # their email, when the results don't have it or it should change


@router.post("/api/campaigns/{campaign_id}/outreach/send")
async def send_first_message(campaign_id: str, body: FirstMessage, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Sends an approved pitch from the founder's Gmail and starts (or continues) the creator's deal."""
    from app.api.routes.deals import _campaign, _leads_by_id, _out, new_deal
    from app.deals.changes import validate

    camp = await _campaign(db, campaign_id, user)
    lead = _leads_by_id(camp.campaign_leads).get(body.creator_id)
    if lead is None:
        raise HTTPException(422, "Pick a creator from this campaign.")
    if not body.body.strip():
        raise HTTPException(422, "The message is empty.")
    a = await service.account_for(db, user.user_id)
    if not service.usable(a):
        raise HTTPException(409, "Connect Gmail first.")
    d = (await db.execute(select(CreatorDeal).where(CreatorDeal.campaign_id == campaign_id,
                                                    CreatorDeal.creator_id == body.creator_id))).scalar_one_or_none()
    if d is None:
        top = (await db.execute(select(func.max(CreatorDeal.position)).where(CreatorDeal.campaign_id == campaign_id))).scalar() or 0
        d = new_deal(camp, lead, campaign_id, position=top + 1)
        db.add(d)
        await db.flush()
        db.add(DealEvent(deal_id=d.deal_id, type="created", payload={"stage": "contacted", "from": "outreach"}))
    if body.to:
        ch = {"contact_email": body.to}
        validate(d, ch)
        d.contact_email = ch["contact_email"]
    if d.gmail_thread_id:
        raise HTTPException(409, "You've already emailed them. Continue in their deal.")
    via = await service.send_for_deal(db, a, d, body.body.strip(), subject=body.subject)
    db.add(DealEvent(deal_id=d.deal_id, type="message_sent",
                     payload={"kind": "first_message", "text": body.body.strip(), "subject": body.subject.strip(),
                              "amounts": None, "edited": False, "via": "gmail", **via}))
    await db.commit()
    await db.refresh(d)
    return {"deal": _out(d, lead, date.today())}
