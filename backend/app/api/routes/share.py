"""Share links (roadmap F1.18): the owner manages links to a campaign's shortlist; anyone holding a
live link can read it, view-only, through the allowlist in app/sharing/view.py.

Personal links can also be:
- reviewer links: 👍/👎 and a comment per creator (F1.18b), shown to the owner;
- contact links: contact details only after the browser proves it can read the invited inbox
  (a one-time email code). Off until email is set up (app/notify/email.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import get_db_user
from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.share_link import ShareFeedback, ShareLink, ShareSession
from app.models.user import User
from app.notify import email as mail
from app.sharing import view as V

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(d: Optional[datetime]) -> Optional[datetime]:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


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


def _check_permissions(kind: str, role: str, show_contacts: bool) -> None:
    if role not in V.ROLES:
        raise HTTPException(422, "Role must be viewer or reviewer.")
    if kind == "anyone" and role != "viewer":
        raise HTTPException(422, "Links for anyone are view-only. Add the person by email to let them review.")
    if show_contacts and kind != "person":
        raise HTTPException(422, "Contact details can only be shared with a specific person.")
    if show_contacts and not mail.email_enabled():
        raise HTTPException(422, "Sharing contact details needs email verification, which isn't set up yet.")


# --- owner ------------------------------------------------------------------------------------

@router.get("/api/campaigns/{campaign_id}/shares")
async def list_shares(campaign_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    await _own_campaign(db, campaign_id, user)
    links = (await db.execute(
        select(ShareLink).where(ShareLink.campaign_id == campaign_id, ShareLink.revoked_at.is_(None))
        .order_by(ShareLink.created_at)
    )).scalars().all()
    now = _now()
    return {"links": [_link_out(l) for l in links if V.is_live(l, now)], "email_enabled": mail.email_enabled()}


class NewShare(BaseModel):
    kind: Literal["person", "anyone"]
    email: Optional[str] = None
    role: str = "viewer"
    show_prices: bool = False
    show_contacts: bool = False
    creator_ids: Optional[list[str]] = None  # None = the whole shortlist


@router.post("/api/campaigns/{campaign_id}/shares")
async def create_share(campaign_id: str, body: NewShare, user: User = Depends(get_db_user),
                       db: AsyncSession = Depends(get_db)):
    camp = await _own_campaign(db, campaign_id, user)
    _check_permissions(body.kind, body.role, body.show_contacts)
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
            l.show_prices, l.role, l.show_contacts = body.show_prices, body.role, body.show_contacts
            await db.commit()
            return _link_out(l)
    link = ShareLink(
        campaign_id=campaign_id, created_by=user.user_id, token=V.new_token(), kind=body.kind, email=email,
        role=body.role, show_prices=body.show_prices, show_contacts=body.show_contacts, creator_ids=creator_ids,
        expires_at=V.anyone_link_expiry() if body.kind == "anyone" else None, view_count=0,
        code_attempts=0, codes_window_count=0,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _link_out(link)


class ShareChange(BaseModel):
    show_prices: Optional[bool] = None
    role: Optional[str] = None
    show_contacts: Optional[bool] = None


@router.patch("/api/shares/{link_id}")
async def change_share(link_id: str, body: ShareChange, user: User = Depends(get_db_user),
                       db: AsyncSession = Depends(get_db)):
    link = await _own_link(db, link_id, user)
    role = body.role if body.role is not None else link.role
    contacts = body.show_contacts if body.show_contacts is not None else link.show_contacts
    # turning contacts off never needs email; turning them on does
    _check_permissions(link.kind, role, contacts and (body.show_contacts is True or not link.show_contacts))
    if body.show_prices is not None:
        link.show_prices = body.show_prices
    link.role = role
    if contacts != link.show_contacts:
        link.show_contacts = contacts
        if not contacts:  # sign every verified browser out of the contacts
            await db.execute(ShareSession.__table__.delete().where(ShareSession.link_id == link.link_id))
    await db.commit()
    return _link_out(link)


@router.delete("/api/shares/{link_id}")
async def revoke_share(link_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Turns the link off at once. The row stays, so its view count and feedback are kept."""
    link = await _own_link(db, link_id, user)
    link.revoked_at = _now()
    await db.execute(ShareSession.__table__.delete().where(ShareSession.link_id == link.link_id))
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


async def _verified(db: AsyncSession, link: ShareLink, session: Optional[str]) -> bool:
    if not (session and link.show_contacts and mail.email_enabled()):
        return False
    row = (await db.execute(select(ShareSession).where(
        ShareSession.session_hash == V.session_hash(session), ShareSession.link_id == link.link_id))).scalar_one_or_none()
    return row is not None and _aware(row.expires_at) > _now()


@router.get("/api/share/{token}")
async def open_share(token: str, db: AsyncSession = Depends(get_db),
                     x_share_session: Optional[str] = Header(default=None)):
    """No sign-in: the token is the permission. Unknown → 404; turned off or expired → 410.
    Contact details only with a verified session (X-Share-Session) on a link that shares them."""
    link = await _live_link(db, token)
    if isinstance(link, JSONResponse):
        return link
    camp = (await db.execute(
        select(Campaign.name, Campaign.campaign_details, Campaign.campaign_leads)
        .where(Campaign.campaign_id == link.campaign_id)
    )).one()
    verified = await _verified(db, link, x_share_session)
    await db.execute(update(ShareLink).where(ShareLink.link_id == link.link_id).values(
        view_count=ShareLink.view_count + 1, last_viewed_at=_now()))
    my_feedback = {}
    if link.role == "reviewer":
        my_feedback = {f.creator_id: {"verdict": f.verdict, "comment": f.comment} for f in (await db.execute(
            select(ShareFeedback).where(ShareFeedback.link_id == link.link_id))).scalars().all()}
    await db.commit()
    from app.api.campaign_names import DEFAULT_NAME, is_default, name_from_brief

    name = (name_from_brief(camp.campaign_details) if is_default(camp.name) else camp.name) or DEFAULT_NAME
    out = V.shared_view(name, camp.campaign_details, camp.campaign_leads, link, contacts=verified)
    contacts_offered = bool(link.show_contacts and mail.email_enabled())
    out.update({
        "can_review": link.role == "reviewer",
        "my_feedback": my_feedback,
        "contacts": {"offered": contacts_offered, "verified": verified,
                     "email_hint": V.email_hint(link.email) if contacts_offered else None},
    })
    return _private(out)


@router.post("/api/share/{token}/code")
async def send_code(token: str, db: AsyncSession = Depends(get_db)):
    """Emails a one-time code to the invited address. At most one a minute and a few an hour."""
    link = await _live_link(db, token)
    if isinstance(link, JSONResponse):
        return link
    if not (link.kind == "person" and link.show_contacts and link.email and mail.email_enabled()):
        return _private({"detail": "This link doesn't share contact details."}, 400)
    now = _now()
    if link.code_sent_at and (now - _aware(link.code_sent_at)).total_seconds() < V.CODE_RESEND_SECONDS:
        return _private({"detail": "A code was just sent. Check your inbox, or try again in a minute."}, 429)
    window = _aware(link.codes_window_start)
    if window is None or now - window > timedelta(hours=1):
        link.codes_window_start, link.codes_window_count = now, 0
    if link.codes_window_count >= V.CODES_PER_HOUR:
        return _private({"detail": "Too many codes were sent. Try again in an hour."}, 429)
    code = V.new_code()
    camp = (await db.execute(select(Campaign.campaign_details).where(Campaign.campaign_id == link.campaign_id))).scalar_one()
    brand = ((camp or {}).get("brand") or {}).get("name") or "Someone"
    try:
        await mail.send_email(
            link.email,
            f"ReachAI: your code to see contact details ({code})",
            f"{brand} shared a creator shortlist with you on ReachAI.\n\n"
            f"Your code: {code}\n\n"
            f"Enter it on the shortlist page to see the creators' contact details. It works for "
            f"{V.CODE_TTL_MINUTES} minutes.\n\nIf you weren't expecting this, you can ignore this email.\n",
        )
    except mail.EmailSendError:
        return _private({"detail": "We couldn't send the email. Try again in a minute."}, 502)
    link.code_hash = V.code_hash(link.link_id, code)
    link.code_expires_at = now + timedelta(minutes=V.CODE_TTL_MINUTES)
    link.code_attempts = 0
    link.code_sent_at = now
    link.codes_window_count = (link.codes_window_count or 0) + 1
    await db.commit()
    return _private({"sent": True, "email_hint": V.email_hint(link.email), "expires_in_minutes": V.CODE_TTL_MINUTES})


class CodeIn(BaseModel):
    code: str


@router.post("/api/share/{token}/verify")
async def verify_code(token: str, body: CodeIn, db: AsyncSession = Depends(get_db)):
    """Right code → a session token this browser sends back (X-Share-Session) to see contacts."""
    link = await _live_link(db, token)
    if isinstance(link, JSONResponse):
        return link
    now = _now()
    if not link.code_hash or not link.code_expires_at or _aware(link.code_expires_at) < now:
        return _private({"detail": "That code has expired. Ask for a new one."}, 400)
    if (link.code_attempts or 0) >= V.CODE_MAX_ATTEMPTS:
        return _private({"detail": "Too many wrong tries. Ask for a new code."}, 429)
    if V.code_hash(link.link_id, body.code) != link.code_hash:
        link.code_attempts = (link.code_attempts or 0) + 1
        await db.commit()
        left = V.CODE_MAX_ATTEMPTS - link.code_attempts
        return _private({"detail": f"That code isn't right. {left} {'try' if left == 1 else 'tries'} left." if left
                         else "Too many wrong tries. Ask for a new code."}, 400 if left else 429)
    token_out, stored = V.new_session()
    db.add(ShareSession(session_hash=stored, link_id=link.link_id, expires_at=now + timedelta(days=V.SESSION_DAYS)))
    link.code_hash, link.code_expires_at, link.code_attempts = None, None, 0  # one use
    await db.commit()
    return _private({"session": token_out, "expires_in_days": V.SESSION_DAYS})


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
    await db.commit()
    return _private({"creator_id": creator_id, "verdict": row.verdict, "comment": row.comment})
