"""Keeping Track up to date (spec §7.6, roadmap F7.11), daily and when the founder opens Track:

1. Find each agreed creator's sponsored post among their new uploads: their ReachAI link or code in the
   description (free); else Jev reads the new uploads' titles and descriptions (one request per upload,
   each upload asked once).
2. Fetch every found post's views, likes and comments (1 YouTube unit per 50 posts), one row per day.
3. A few days after a post is live, Jev reads its comments once (what the audience said).

All numbers come from YouTube or from counting (rule 2); Jev only answers yes/no and scales (rule 3)."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.costs import CostContext
from app.deals import constants as DC
from app.judge import constants as K
from app.models.campaign import Campaign
from app.models.deal import CreatorDeal, DealEvent, DealPost, PostStat, TrackingLink
from app.tracking import constants as T

logger = logging.getLogger(__name__)

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def video_id_from(url: str) -> Optional[str]:
    """The YouTube video id in a watch, short, shorts or live link."""
    u = urlparse((url or "").strip())
    host = (u.hostname or "").lower()
    if host.endswith("youtu.be"):
        vid = u.path.strip("/").split("/")[0]
    elif host.endswith("youtube.com"):
        vid = parse_qs(u.query).get("v", [""])[0]
        if not vid:
            parts = [p for p in u.path.split("/") if p]
            vid = parts[1] if len(parts) >= 2 and parts[0] in ("shorts", "live", "embed") else ""
    else:
        return None
    return vid if _VIDEO_ID.match(vid or "") else None


def uploads_playlist(channel_id: str) -> Optional[str]:
    return "UU" + channel_id[2:] if channel_id and channel_id.startswith("UC") else None


def matched_by(description: str, slug: Optional[str], code: Optional[str]) -> Optional[str]:
    """Their link or code in a video's description: that's the sponsored post (free, no model)."""
    text = (description or "").lower()
    if slug and f"/r/{slug.lower()}" in text:
        return "link"
    if code and re.search(rf"\b{re.escape(code.lower())}\b", text):
        return "code"
    return None


async def _uploads(api, channel_id: str) -> list[dict]:
    pl = uploads_playlist(channel_id)
    if not pl:
        return []
    r = await api.playlist_items(part="snippet,contentDetails", playlistId=pl, maxResults=T.UPLOADS_TO_CHECK)
    out = []
    for it in r.get("items") or []:
        sn = it.get("snippet") or {}
        vid = (it.get("contentDetails") or {}).get("videoId") or (sn.get("resourceId") or {}).get("videoId")
        if not vid:
            continue
        thumbs = sn.get("thumbnails") or {}
        thumb = next((thumbs[k]["url"] for k in ("medium", "high", "default") if thumbs.get(k, {}).get("url")), None)
        out.append({"id": vid, "title": sn.get("title") or "", "description": sn.get("description") or "",
                    "published": (it.get("contentDetails") or {}).get("videoPublishedAt") or sn.get("publishedAt"), "thumb": thumb})
    return out


def _published(v: dict) -> Optional[datetime]:
    try:
        return datetime.fromisoformat((v.get("published") or "").replace("Z", "+00:00"))
    except ValueError:
        return None


async def _jev_says_sponsored(brand: dict, video: dict, context: CostContext) -> bool:
    from app.judge.client import judge
    from app.judge.questions import sponsored_post_questions

    j = await judge({"brand": {"name": brand.get("name"), "product": brand.get("product") or brand.get("description")},
                     "video": {"title": video["title"], "description": video["description"][:1500]}},
                    sponsored_post_questions(), context=context)
    return j.noul("is_sponsored_post") >= T.JEV_MATCH_FROM


def _set_found(db: AsyncSession, d: CreatorDeal, post: DealPost, video: dict, how: str) -> None:
    post.video_id, post.title, post.thumbnail_url, post.found_by = video["id"], video["title"][:300], video.get("thumb"), how
    post.post_url = f"https://www.youtube.com/watch?v={video['id']}"
    post.live_at = _published(video) or _now()
    if d.stage in ("agreed", "content"):
        db.add(DealEvent(deal_id=d.deal_id, type="stage", payload={"from": d.stage, "to": "live"}))
        d.stage = "live"
        d.live_at = d.live_at or post.live_at
    d.post_url = d.post_url or post.post_url
    db.add(DealEvent(deal_id=d.deal_id, type="post_found", payload={"video_id": video["id"], "title": video["title"][:300], "by": how}))


async def find_posts(db: AsyncSession, camp, deals: list[CreatorDeal], posts: dict, api, context: CostContext) -> int:
    """Matches new uploads to planned posts. `posts`: {deal_id: [DealPost]}. → posts found"""
    brand = (camp.campaign_details or {}).get("brand") or {}
    track = dict((camp.campaign_details or {}).get("track") or {})
    checked = set(track.get("checked") or [])
    links = {l.deal_id: l.slug for l in (await db.execute(select(TrackingLink).where(
        TrackingLink.deal_id.in_([d.deal_id for d in deals])))).scalars()} if deals else {}
    found = 0
    for d in deals:
        waiting = [p for p in posts.get(d.deal_id, []) if not p.video_id]
        if not waiting or d.platform != "youtube":
            continue
        try:
            uploads = await _uploads(api, d.creator_id)
        except Exception as e:  # one creator's channel failing shouldn't stop the others
            logger.warning("uploads failed for a deal: %s", type(e).__name__)
            continue
        since = min((p.created_at for p in posts[d.deal_id] if p.created_at), default=None)
        taken = {p.video_id for p in posts[d.deal_id] if p.video_id}
        fresh = [v for v in uploads if v["id"] not in taken
                 and (since is None or (_published(v) or _now()) >= since - timedelta(days=1))]
        fresh.sort(key=lambda v: v.get("published") or "")
        # free first: uploads with their link or code
        for v in list(fresh):
            how = matched_by(v["description"], links.get(d.deal_id), d.tracking_code)
            if how and waiting:
                _set_found(db, d, waiting.pop(0), v, how)
                fresh.remove(v)
                found += 1
        # then Jev, only while a post is still missing, each upload asked once
        for v in fresh:
            if not waiting:
                break
            if v["id"] in checked:
                continue
            checked.add(v["id"])
            try:
                if await _jev_says_sponsored(brand, v, context):
                    _set_found(db, d, waiting.pop(0), v, "jev")
                    found += 1
            except Exception as e:
                logger.warning("jev post match failed: %s", type(e).__name__)
    track["checked"] = sorted(checked)[-2000:]
    camp_details = {**(camp.campaign_details or {}), "track": track}
    await db.execute(update(Campaign).where(Campaign.campaign_id == camp.campaign_id).values(campaign_details=camp_details))
    return found


async def update_stats(db: AsyncSession, live: list[DealPost], api, today: date) -> None:
    """Views, likes and comments for every found post, and today's row for the charts."""
    by_id = {p.video_id: p for p in live if p.video_id}
    ids = list(by_id)
    for i in range(0, len(ids), 50):
        r = await api.videos(part="statistics", id=",".join(ids[i:i + 50]))
        for it in r.get("items") or []:
            p = by_id.get(it.get("id"))
            st = it.get("statistics") or {}
            if p is None:
                continue
            p.views = int(st.get("viewCount") or 0)
            p.likes = int(st["likeCount"]) if st.get("likeCount") is not None else None
            p.comments = int(st["commentCount"]) if st.get("commentCount") is not None else None
            p.stats_at = _now()
            await db.execute(pg_insert(PostStat).values(post_id=p.post_id, day=today, views=p.views, likes=p.likes, comments=p.comments)
                             .on_conflict_do_update(constraint="uq_post_stats_post_day",
                                                    set_={"views": p.views, "likes": p.likes, "comments": p.comments}))


async def read_comments(post: DealPost, brand: dict, api, context: CostContext) -> dict:
    """Jev's read of what the audience said, plus the three most liked comments (as written)."""
    from app.judge.client import judge
    from app.judge.questions import comment_questions

    try:
        r = await api.comment_threads(part="snippet", videoId=post.video_id, order="relevance",
                                      maxResults=T.COMMENTS_TO_READ, textFormat="plainText")
    except Exception as e:
        if getattr(e, "status", None) == 403:  # comments turned off
            return {"disabled": True, "read_at": _now().isoformat()}
        raise
    items = []
    for it in r.get("items") or []:
        c = ((it.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
        if c.get("textDisplay"):
            items.append({"text": c["textDisplay"][:400], "likes": int(c.get("likeCount") or 0)})
    if not items:
        return {"count": 0, "read_at": _now().isoformat()}
    items.sort(key=lambda c: -c["likes"])
    j = await judge({"brand": {"name": brand.get("name"), "product": brand.get("product")}, "comments": [c["text"] for c in items]},
                    comment_questions(), context=context)
    level = int(round(j.score("sentiment") or 2))
    yes = lambda q: j.noul(q) >= K.COMMENT_SIGNAL_FROM  # noqa: E731
    return {"count": len(items), "sentiment": K.COMMENT_SENTIMENT_LEVELS[max(0, min(level, 4))],
            "product_interest": yes("product_interest"), "product_questions": yes("product_questions"),
            "ad_backlash": yes("ad_backlash"), "top": [c["text"][:200] for c in items[:3]], "read_at": _now().isoformat()}


async def refresh_campaign(db: AsyncSession, campaign_id: str, api, *, user_id: Optional[str], today: Optional[date] = None,
                           force: bool = False) -> dict:
    """Finds posts, updates numbers, reads comments that are due. Commits. → {"found", "skipped"?}"""
    today = today or date.today()
    camp = (await db.execute(select(Campaign).where(Campaign.campaign_id == campaign_id))).scalar_one_or_none()
    if camp is None:
        raise HTTPException(404, "Campaign not found")
    track = (camp.campaign_details or {}).get("track") or {}
    last = track.get("refreshed_at")
    if not force and last and _now() - datetime.fromisoformat(last) < timedelta(minutes=T.REFRESH_EVERY_MINUTES):
        return {"found": 0, "skipped": True}
    deals = list((await db.execute(select(CreatorDeal).where(CreatorDeal.campaign_id == campaign_id,
                                                             CreatorDeal.stage.in_(DC.COMMITTED_STAGES)))).scalars())
    posts: dict = {}
    if deals:
        for p in (await db.execute(select(DealPost).where(DealPost.deal_id.in_([d.deal_id for d in deals]))
                                   .order_by(DealPost.due_on.nulls_last(), DealPost.position))).scalars():
            posts.setdefault(p.deal_id, []).append(p)
    context = CostContext(user_id=user_id, campaign_id=campaign_id)
    found = await find_posts(db, camp, deals, posts, api, context)
    live = [p for ps in posts.values() for p in ps if p.video_id]
    if live:
        await update_stats(db, live, api, today)
    brand = (camp.campaign_details or {}).get("brand") or {}
    for p in live:
        if p.comment_summary is None and p.live_at and (_now() - p.live_at).days >= T.COMMENT_SUMMARY_AFTER_DAYS:
            try:
                p.comment_summary = await read_comments(p, brand, api, context)
            except Exception as e:
                logger.warning("comment read failed: %s", type(e).__name__)
    details = dict((await db.execute(select(Campaign.campaign_details).where(Campaign.campaign_id == campaign_id))).scalar() or {})
    details["track"] = {**(details.get("track") or {}), "refreshed_at": _now().isoformat()}
    await db.execute(update(Campaign).where(Campaign.campaign_id == campaign_id).values(campaign_details=details))
    await db.commit()
    return {"found": found}
