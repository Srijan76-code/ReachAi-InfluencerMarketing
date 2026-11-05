"""Track (spec §7.6, roadmap F7.11): results for a campaign's agreed creators. Owner only, except the
public signup endpoint the founder's site calls (`POST /api/t/{key}`)."""

from __future__ import annotations

import csv
import io
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.deals import _campaign, _deal, _leads_by_id, app_url
from app.auth.user import get_db_user
from app.db.database import get_db
from app.deals import constants as DC
from app.deals.changes import apply_change
from app.models.campaign import Campaign
from app.models.deal import Conversion, CreatorDeal, DealEvent, DealPost, LinkClick, PostStat, TrackingLink
from app.models.user import User
from app.tracking import constants as T
from app.tracking import report as R

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _track(details) -> dict:
    return dict((details or {}).get("track") or {})


async def _rows(db: AsyncSession, camp, base: str) -> tuple[list[R.Row], dict, list]:
    """Every agreed creator with their posts, clicks and conversions, plus daily increments for the chart."""
    deals = list((await db.execute(select(CreatorDeal).where(CreatorDeal.campaign_id == camp.campaign_id,
                                                             CreatorDeal.stage.in_(DC.COMMITTED_STAGES))
                                   .order_by(CreatorDeal.created_at))).scalars())
    leads = _leads_by_id(camp.campaign_leads)
    ids = [d.deal_id for d in deals]
    since = date.today() - timedelta(days=30)
    series: dict = {"views": {}, "clicks": {}, "results": {}}
    if not ids:
        return [], series, []
    posts = list((await db.execute(select(DealPost).where(DealPost.deal_id.in_(ids)).order_by(DealPost.due_on.nulls_last(), DealPost.position))).scalars())
    links = {l.deal_id: l for l in (await db.execute(select(TrackingLink).where(TrackingLink.deal_id.in_(ids)))).scalars()}
    slug_deal = {l.slug: l.deal_id for l in links.values()}
    clicks: dict = {}
    if slug_deal:
        for slug, day, n in (await db.execute(select(LinkClick.slug, func.date(LinkClick.created_at), func.count())
                                              .where(LinkClick.slug.in_(list(slug_deal))).group_by(LinkClick.slug, func.date(LinkClick.created_at)))).all():
            clicks[slug_deal[slug]] = clicks.get(slug_deal[slug], 0) + n
            if day and day >= since:
                series["clicks"][day] = series["clicks"].get(day, 0) + n
    conv: dict = {}
    goal_kind = _track(camp.campaign_details).get("goal_kind") or "signups"
    goal_conv = T.GOAL_TO_CONVERSION.get(goal_kind)
    for deal_id, kind, day, n in (await db.execute(select(Conversion.deal_id, Conversion.kind, Conversion.day, func.sum(Conversion.count))
                                                   .where(Conversion.campaign_id == camp.campaign_id)
                                                   .group_by(Conversion.deal_id, Conversion.kind, Conversion.day))).all():
        if deal_id:
            c = conv.setdefault(deal_id, {})
            c[kind] = c.get(kind, 0) + int(n)
        if day >= since and (kind == goal_conv or (goal_kind == "sales" and kind == "code_use")):
            series["results"][day] = series["results"].get(day, 0) + int(n)
    # views per day: the increase from the day before (the first day counts everything so far)
    stats = (await db.execute(select(PostStat.post_id, PostStat.day, PostStat.views).where(PostStat.post_id.in_([p.post_id for p in posts]))
                              .order_by(PostStat.post_id, PostStat.day))).all() if posts else []
    prev: dict = {}
    spark: dict = {}
    for post_id, day, views in stats:
        inc = max(0, views - prev.get(post_id, 0))
        prev[post_id] = views
        spark.setdefault(post_id, []).append({"day": day.isoformat(), "views": views})
        if day >= since:
            series["views"][day] = series["views"].get(day, 0) + inc
    if goal_kind == "views":
        series["results"] = dict(series["views"])
    elif goal_kind == "clicks":
        series["results"] = dict(series["clicks"])
    by_deal: dict = {}
    for p in posts:
        by_deal.setdefault(p.deal_id, []).append({
            "id": p.post_id, "deliverable": p.deliverable, "due_on": p.due_on, "video_id": p.video_id, "title": p.title,
            "thumbnail_url": p.thumbnail_url, "url": p.post_url, "live_at": p.live_at, "found_by": p.found_by,
            "views": p.views, "likes": p.likes, "comments": p.comments, "comment_summary": p.comment_summary,
            "spark": spark.get(p.post_id, [])[-14:]})
    rows = []
    for d in deals:
        lead = leads.get(d.creator_id) or {}
        l = links.get(d.deal_id)
        rows.append(R.Row(deal_id=d.deal_id, name=lead.get("title") or d.creator_name or "", avatar_url=lead.get("avatar_url"),
                          cost=float(d.agreed_rate or 0), stage=d.stage, pay_when=d.pay_when, paid_amount=d.paid_amount,
                          paid_at=d.paid_at, pay_method=d.pay_method, typical_views=d.typical_views, code=d.tracking_code,
                          link={"url": f"{base}/r/{l.slug}", "target": l.target_url} if l else None,
                          posts=by_deal.get(d.deal_id, []), clicks=clicks.get(d.deal_id, 0), conversions=conv.get(d.deal_id, {}),
                          fair_low=d.fair_low, fair_high=d.fair_high, engagement_usual=_usual_engagement(lead)))
    return rows, series, deals


def _usual_engagement(lead: dict) -> Optional[float]:
    """The creator's usual (likes + comments) per view, as a fraction (older results stored it as a %)."""
    er = (lead.get("metrics") or {}).get("engagement_rate")
    if not er:
        return None
    return float(er) / 100 if er > 1 else float(er)


async def _ensure_key(db: AsyncSession, camp) -> str:
    """The campaign's public key for the signup snippet (not a secret: it only lets a site add signups)."""
    track = _track(camp.campaign_details)
    if not track.get("key"):
        track["key"] = secrets.token_urlsafe(9)
        await db.execute(update(Campaign).where(Campaign.campaign_id == camp.campaign_id)
                         .values(campaign_details={**(camp.campaign_details or {}), "track": track}))
        await db.commit()
    return track["key"]


@router.get("/api/campaigns/{campaign_id}/track")
async def get_track(campaign_id: str, request: Request, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    camp = await _campaign(db, campaign_id, user)
    key = await _ensure_key(db, camp)
    camp = await _campaign(db, campaign_id, user)
    base = app_url(request)
    rows, series, _ = await _rows(db, camp, base)
    t = _track(camp.campaign_details)
    goal_kind = t.get("goal_kind") or ("sales" if ((camp.campaign_details or {}).get("campaign") or {}).get("goal") == "sales" else "signups")
    out = R.build(rows, {"kind": goal_kind, "count": t.get("goal_count"), "value_each": t.get("value_each")}, series)
    out.update({"snippet": {"key": key, "src": f"{base}/t.js", "endpoint": f"{base}/api/t/{key}", "seen_at": t.get("snippet_seen_at"),
                            "last_conversion_at": t.get("last_conversion_at"),
                            "site": ((camp.campaign_details or {}).get("brand") or {}).get("website")},
                "refreshed_at": t.get("refreshed_at"),
                "budget": ((camp.campaign_details or {}).get("campaign") or {}).get("budget_total")})
    return out


class GoalIn(BaseModel):
    goal_kind: Optional[str] = None
    goal_count: Optional[int] = None
    value_each: Optional[float] = None


@router.patch("/api/campaigns/{campaign_id}/track")
async def set_goal(campaign_id: str, body: GoalIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    camp = await _campaign(db, campaign_id, user)
    ch = body.model_dump(exclude_unset=True)
    if ch.get("goal_kind") is not None and ch["goal_kind"] not in T.GOAL_KINDS:
        raise HTTPException(422, "Unknown goal.")
    if ch.get("goal_count") is not None and not (0 < ch["goal_count"] <= 100_000_000):
        raise HTTPException(422, "Set a goal above zero.")
    if ch.get("value_each") is not None and not (0 <= ch["value_each"] <= 1_000_000):
        raise HTTPException(422, "That value doesn't look right.")
    details = dict(camp.campaign_details or {})
    details["track"] = {**_track(details), **ch}
    await db.execute(update(Campaign).where(Campaign.campaign_id == campaign_id).values(campaign_details=details))
    await db.commit()
    return {"track": {k: details["track"].get(k) for k in ("goal_kind", "goal_count", "value_each")}}


@router.post("/api/campaigns/{campaign_id}/track/refresh")
async def refresh(campaign_id: str, force: bool = False, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Looks for new posts and fresh numbers now (at most every few minutes per campaign)."""
    from app.billing.costs import CostContext
    from app.platforms.youtube_api import HttpYouTubeAPI, YouTubeAPIError
    from app.tracking.find import refresh_campaign

    await _campaign(db, campaign_id, user)
    try:
        api = HttpYouTubeAPI(context=CostContext(user_id=user.user_id, campaign_id=campaign_id))
    except YouTubeAPIError:
        raise HTTPException(503, "YouTube isn't set up on this server.")
    try:
        return await refresh_campaign(db, campaign_id, api, user_id=user.user_id, force=force)
    finally:
        await api.aclose()


class PostLinkIn(BaseModel):
    url: str


@router.post("/api/posts/{post_id}/link")
async def set_post_link(post_id: str, body: PostLinkIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """The founder pastes a post's link (when ReachAI didn't find it). Its numbers come with the next check."""
    from app.tracking.find import video_id_from

    p = await db.get(DealPost, post_id)
    if p is None:
        raise HTTPException(404, "Post not found")
    d, _ = await _deal(db, p.deal_id, user)
    vid = video_id_from(body.url)
    if not vid:
        raise HTTPException(422, "Paste a YouTube video link.")
    p.video_id, p.post_url, p.found_by, p.live_at = vid, f"https://www.youtube.com/watch?v={vid}", "you", p.live_at or _now()
    p.comment_summary = None
    if d.stage in ("agreed", "content"):
        apply_change(db, d, {"stage": "live"})
    # numbers on the next check: let it run right away
    camp = (await db.execute(select(Campaign).where(Campaign.campaign_id == d.campaign_id))).scalar_one()
    details = dict(camp.campaign_details or {})
    details["track"] = {**_track(details), "refreshed_at": None}
    await db.execute(update(Campaign).where(Campaign.campaign_id == d.campaign_id).values(campaign_details=details))
    await db.commit()
    return {"post": post_id, "video_id": vid}


class ConversionIn(BaseModel):
    kind: str  # signup | sale | code_use
    count: int
    day: Optional[date] = None


@router.post("/api/deals/{deal_id}/conversions")
async def add_conversions(deal_id: str, body: ConversionIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Signups, sales or code uses the founder counted for this creator (from their store or dashboard)."""
    d, _ = await _deal(db, deal_id, user)
    if body.kind not in T.CONVERSION_KINDS:
        raise HTTPException(422, "Unknown kind.")
    if not (-100_000 <= body.count <= 100_000) or body.count == 0:
        raise HTTPException(422, "Enter a number.")
    db.add(Conversion(campaign_id=d.campaign_id, deal_id=d.deal_id, kind=body.kind, source="you", count=body.count,
                      day=body.day or date.today()))
    await db.commit()
    return {"added": body.count}


class CsvIn(BaseModel):
    text: str  # "code,count" per line (a header row is fine)
    kind: str = "code_use"


@router.post("/api/campaigns/{campaign_id}/conversions/csv")
async def import_conversions(campaign_id: str, body: CsvIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Code uses from a store export: each row's code is matched to the creator who has it."""
    await _campaign(db, campaign_id, user)
    if body.kind not in T.CONVERSION_KINDS or len(body.text) > 500_000:
        raise HTTPException(422, "Upload a CSV with a code and a count on each row.")
    codes = {c.upper(): i for i, c in (await db.execute(select(CreatorDeal.deal_id, CreatorDeal.tracking_code).where(
        CreatorDeal.campaign_id == campaign_id, CreatorDeal.tracking_code.is_not(None)))).all()}
    added, unknown = 0, set()
    for row in csv.reader(io.StringIO(body.text)):
        if len(row) < 2:
            continue
        code, n = row[0].strip().upper(), row[1].strip()
        if not n.lstrip("-").isdigit():
            continue  # the header row
        if code not in codes:
            unknown.add(code)
            continue
        db.add(Conversion(campaign_id=campaign_id, deal_id=codes[code], kind=body.kind, source="csv", count=int(n), day=date.today()))
        added += int(n)
    await db.commit()
    return {"added": added, "unknown_codes": sorted(unknown)[:20]}


class PaidIn(BaseModel):
    amount: float
    paid_on: Optional[date] = None
    method: Optional[str] = None
    note: Optional[str] = None


@router.post("/api/deals/{deal_id}/paid")
async def mark_paid(deal_id: str, body: PaidIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Records a payment the founder made (ReachAI never moves money)."""
    d, _ = await _deal(db, deal_id, user)
    if body.method is not None and body.method not in T.PAY_METHODS:
        raise HTTPException(422, "Unknown payment method.")
    when = datetime.combine(body.paid_on or date.today(), datetime.min.time(), tzinfo=timezone.utc)
    apply_change(db, d, {"stage": "paid", "paid_amount": body.amount, "paid_at": when, "payment_ref": (body.note or "").strip()[:300] or None})
    d.pay_method = body.method
    await db.commit()
    return {"paid": deal_id}


@router.post("/api/deals/{deal_id}/unpaid")
async def undo_paid(deal_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    d, _ = await _deal(db, deal_id, user)
    if d.stage == "paid":
        apply_change(db, d, {"stage": "live" if d.live_at else "agreed", "paid_amount": None, "paid_at": None})
        d.pay_method = None
        await db.commit()
    return {"unpaid": deal_id}


@router.get("/api/campaigns/{campaign_id}/track.csv")
async def results_csv(campaign_id: str, request: Request, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """One row per agreed creator: what they cost, what they posted, and what it brought."""
    camp = await _campaign(db, campaign_id, user)
    rows, series, _ = await _rows(db, camp, app_url(request))
    t = _track(camp.campaign_details)
    rep = R.build(rows, {"kind": t.get("goal_kind") or "signups", "count": t.get("goal_count"), "value_each": t.get("value_each")}, series)
    by = {r.deal_id: r for r in rows}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Creator", "Price", "Posts", "Post links", "Views", "Clicks", "Signups", "Code uses", f"Goal ({rep['goal']['kind']})",
                "Cost per 1,000 views", f"Cost per {rep['goal']['kind'][:-1]}", "Verdict", "Code", "Link", "Paid", "Paid on", "Method"])
    for c in rep["creators"]:
        r = by[c["deal_id"]]
        safe = lambda v: ("'" + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v  # noqa: E731  (no formulas in Excel)
        w.writerow([safe(c["name"]), c["cost"], len(r.posts), " ".join(p["url"] for p in r.posts if p.get("url")), c["views"], c["clicks"],
                    r.conversions.get("signup", 0), r.conversions.get("code_use", 0), c["results"], c["cost_per_1k_views"] or "",
                    c["cost_per_result"] or "", c["verdict"].replace("_", " "), r.code or "", (r.link or {}).get("url", ""),
                    r.paid_amount if r.stage == "paid" else "", r.paid_at.date().isoformat() if r.paid_at else "", r.pay_method or ""])
    name = "".join(ch for ch in (camp.campaign_details or {}).get("brand", {}).get("name", "campaign") if ch.isalnum() or ch in " -_")[:40] or "campaign"
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name} results.csv"'})


@router.post("/api/t/{key}")
async def snippet_signup(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Public: the founder's thank-you page reports a signup (or sale) for the creator who sent the visitor.
    Sent with sendBeacon as text, so no CORS preflight. Only counts codes in this campaign."""
    try:
        body = json.loads((await request.body())[:2000] or b"{}")
    except ValueError:
        body = {}
    ref = str(body.get("ref") or "").strip().upper()[:32]
    kind = body.get("kind") if body.get("kind") in ("signup", "sale", "ping") else "signup"
    camp = (await db.execute(select(Campaign.campaign_id, Campaign.campaign_details).where(
        Campaign.campaign_details["track"]["key"].astext == key))).one_or_none()
    headers = {"Access-Control-Allow-Origin": "*"}
    if camp is None:
        return Response(status_code=204, headers=headers)
    track = _track(camp.campaign_details)
    now = _now().isoformat()
    if kind == "ping":  # "Test it": the snippet is on the founder's site
        track["snippet_seen_at"] = now
    elif ref:
        deal_id = (await db.execute(select(CreatorDeal.deal_id).where(CreatorDeal.campaign_id == camp.campaign_id,
                                                                      func.upper(CreatorDeal.tracking_code) == ref))).scalar_one_or_none()
        if deal_id is None:
            return Response(status_code=204, headers=headers)
        db.add(Conversion(campaign_id=camp.campaign_id, deal_id=deal_id, kind=kind, source="snippet", count=1, day=date.today()))
        track["snippet_seen_at"] = track.get("snippet_seen_at") or now
        track["last_conversion_at"] = now
    else:
        return Response(status_code=204, headers=headers)
    await db.execute(update(Campaign).where(Campaign.campaign_id == camp.campaign_id)
                     .values(campaign_details={**(camp.campaign_details or {}), "track": track}))
    await db.commit()
    return Response(status_code=204, headers=headers)
