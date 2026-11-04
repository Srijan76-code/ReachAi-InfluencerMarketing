"""Nightly YouTube data refresh (spec §4.4, roadmap F1.11).

YouTube API policy: stored API data must be refreshed or deleted after 30 days. Each night:
1. Creators whose data expires within REFRESH_AHEAD and that are *useful* (scored in a run, or in a
   campaign's results or saved leads) are fetched again; that renews their 30 days. Creators in
   results over 30 days old that aren't stored yet (the old engine didn't store them) are fetched too.
2. Everyone else is deleted once their data has expired, as are channels YouTube no longer returns.
3. Snapshots older than 30 days are deleted, and run records lose their copied metrics.
4. Campaign results and saved leads older than 30 days are updated from the refreshed data; leads
   whose creator wasn't refreshed keep only name, link and our own scores, marked `data_expired`.
5. LangGraph checkpoint threads untouched for 30 days are deleted (`purge_old_checkpoints`): they hold
   copies of creator data and are only needed to resume a run in progress.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import delete, select, update

from app.creators import constants as C
from app.creators import repository as repo
from app.metrics.compute import BriefContext, compute_metrics
from app.models.campaign import Campaign
from app.models.creator import Creator, CreatorSnapshot
from app.models.discovery_run import RunCandidate
from app.models.saved_lead import SavedLead
from app.platforms.base import CandidateRef

logger = logging.getLogger(__name__)

PLATFORM = "youtube"
TTL = C.DATA_TTL[PLATFORM]

# Lead fields that come from YouTube (refreshed or removed). Scores, labels and reasons are ours.
API_FIELDS = ("title", "description", "country", "uploads_id", "subscribers", "video_count", "estimated_cpm",
              "lifetime_health", "metrics", "socials", "valuation", "recent_videos", "url", "avatar_url", "rising", "momentum",
              "posts", "signals", "trend", "verified",
              "anomaly_score", "fair_low", "fair_high")
KEEP_WHEN_EXPIRED = ("id", "title", "url", "platform", "creator_id", "final_score", "deal_status", "relevance_score",
                     "semantic_score", "score_breakdown", "llm_reasoning", "flags", "found_via", "niche", "risk",
                     "score_parts", "match_terms", "person_id")
STATS_FIELDS = ("video_count", "uploads_id", "lifetime_health")  # only known right after a fetch


@dataclass
class RefreshReport:
    due: int = 0
    refreshed: int = 0
    deleted: int = 0
    gone_on_youtube: int = 0
    skipped_over_cap: int = 0
    snapshots_deleted: int = 0
    run_records_cleared: int = 0
    leads_updated: int = 0
    leads_expired: int = 0
    avatars_added: int = 0
    checkpoint_threads_deleted: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _factory(session_factory):
    if session_factory is not None:
        return session_factory
    from app.db.database import AsyncSessionLocal

    return AsyncSessionLocal


def _is_youtube_lead(lead: Any) -> bool:
    return isinstance(lead, dict) and (lead.get("platform") in (None, PLATFORM)) and str(lead.get("id") or "").startswith("UC")


async def _useful_ids(sf) -> set[str]:
    """YouTube channel ids worth refreshing: scored in a run, in a campaign's results, or saved."""
    ids: set[str] = set()
    async with sf() as s:
        scored = (await s.execute(
            select(Creator.platform_id).join(RunCandidate, RunCandidate.creator_id == Creator.creator_id)
            .where(Creator.platform == PLATFORM, RunCandidate.stage == "scored")
        )).scalars().all()
        ids.update(scored)
        for leads in (await s.execute(select(Campaign.campaign_leads).where(Campaign.campaign_leads.is_not(None)))).scalars():
            ids.update(l["id"] for l in (leads or []) if _is_youtube_lead(l))
        for data in (await s.execute(select(SavedLead.lead_data))).scalars():
            if _is_youtube_lead(data):
                ids.add(data["id"])
    return ids


async def _stale_result_ids(sf, now: datetime) -> list[str]:
    """Channel ids in campaign results or saved leads whose YouTube numbers are over 30 days old."""
    cutoff = now - TTL
    ids: dict[str, None] = {}
    async with sf() as s:
        for leads, updated, created in (await s.execute(
            select(Campaign.campaign_leads, Campaign.updated_at, Campaign.created_at).where(Campaign.campaign_leads.is_not(None))
        )).all():
            for l in leads or []:
                if _is_youtube_lead(l) and not l.get("data_expired"):
                    as_of = _lead_as_of(l, updated or created)
                    if as_of is None or as_of <= cutoff:
                        ids[l["id"]] = None
        for data, created in (await s.execute(select(SavedLead.lead_data, SavedLead.created_at))).all():
            if _is_youtube_lead(data) and not data.get("data_expired"):
                as_of = _lead_as_of(data, created)
                if as_of is None or as_of <= cutoff:
                    ids[data["id"]] = None
    return list(ids)


async def _due(sf, now: datetime) -> list[tuple[str, str, Optional[datetime]]]:
    async with sf() as s:
        rows = (await s.execute(
            select(Creator.creator_id, Creator.platform_id, Creator.data_expires_at)
            .where(Creator.platform == PLATFORM, Creator.data_expires_at.is_not(None),
                   Creator.data_expires_at <= now + C.REFRESH_AHEAD)
            .order_by(Creator.data_expires_at)
            .limit(C.REFRESH_SCAN_LIMIT)
        )).all()
    return [(r[0], r[1], _aware(r[2])) for r in rows]


async def _purge_old_copies(sf, now: datetime, report: RefreshReport) -> None:
    cutoff = now - TTL
    async with sf() as s:
        res = await s.execute(delete(CreatorSnapshot).where(CreatorSnapshot.captured_at < cutoff))
        report.snapshots_deleted = res.rowcount or 0
        res = await s.execute(
            update(RunCandidate).where(RunCandidate.platform == PLATFORM, RunCandidate.created_at < cutoff,
                                       RunCandidate.metrics.is_not(None)).values(metrics=None)
        )
        report.run_records_cleared = res.rowcount or 0
        await s.commit()


def _expired_lead(lead: dict) -> dict:
    out = {k: lead[k] for k in KEEP_WHEN_EXPIRED if k in lead}
    out.update(data_expired=True, subscribers=0, recent_videos=[], posts=[], description="", country="", valuation=0,
               socials={"email": None, "instagram": None, "twitter": None, "linkedin": None},
               metrics={"avg_views": 0, "volatility": 0, "reliability": "Medium", "engagement_rate": 0,
                        "raw_engagement": 0, "trust_score": 0, "forecast": "n/a"})
    return out


def _refreshed_lead(lead: dict, profile: dict, industry: str, ctx: BriefContext, now: datetime) -> dict:
    from app.discovery.legacy import to_legacy_lead

    metrics = compute_metrics(profile, ctx, now=now).to_dict()
    # Jev's country judgment is ours, not YouTube's: keep it while the channel still lists no country
    judged = lead.get("country") if lead.get("country_source") == "jev" else None
    fresh = to_legacy_lead(profile, metrics, {"country_judged": judged}, None, industry, topics=lead.get("match_terms") or [])
    out = dict(lead)
    for k in (*API_FIELDS, "country_source"):
        if k in STATS_FIELDS and not (profile.get("platform_stats") or {}) and k in lead:
            continue  # stored profiles don't keep these; keep the last known value
        if k in fresh:
            out[k] = fresh[k]
    out.pop("data_expired", None)
    out["data_as_of"] = now.isoformat()
    return out


def _lead_as_of(lead: dict, fallback: Optional[datetime]) -> Optional[datetime]:
    raw = lead.get("data_as_of")
    if raw:
        try:
            return _aware(datetime.fromisoformat(str(raw)))
        except ValueError:
            pass
    return _aware(fallback)


async def _update_results(sf, now: datetime, refreshed: dict[str, dict], report: RefreshReport) -> None:
    """Results older than 30 days: refresh from new data, or keep only name, link and our scores."""
    from app.discovery.brief import parse_brief

    cutoff = now - TTL
    fresh_in_db = await _fresh_profiles(sf, now)

    def fix(lead: dict, as_of_fallback, industry: str, ctx: BriefContext):
        if not _is_youtube_lead(lead) or lead.get("data_expired"):
            return lead, None
        as_of = _lead_as_of(lead, as_of_fallback)
        if as_of is not None and as_of > cutoff:
            return lead, None
        profile = refreshed.get(lead["id"]) or fresh_in_db.get(lead["id"])
        if profile is not None:
            return _refreshed_lead(lead, profile, industry, ctx, now), "updated"
        return _expired_lead(lead), "expired"

    async with sf() as s:
        campaigns = (await s.execute(select(Campaign).where(Campaign.campaign_leads.is_not(None)))).scalars().all()
        for c in campaigns:
            try:
                brief = parse_brief(c.campaign_details or {})
                industry, ctx = brief.industry, brief.metrics_context()
            except Exception:
                industry, ctx = "other", BriefContext()
            changed, new = False, []
            for lead in c.campaign_leads or []:
                fixed, what = fix(lead, c.updated_at or c.created_at, industry, ctx)
                if what:
                    changed = True
                    report.leads_updated += what == "updated"
                    report.leads_expired += what == "expired"
                new.append(fixed)
            if changed:
                c.campaign_leads = new  # reassign so the JSON change is saved
        saved = (await s.execute(select(SavedLead))).scalars().all()
        for sl in saved:
            fixed, what = fix(sl.lead_data or {}, sl.created_at, "other", BriefContext())
            if what:
                sl.lead_data = fixed
                report.leads_updated += what == "updated"
                report.leads_expired += what == "expired"
        await s.commit()


async def _backfill_avatars(sf, adapter_factory, report: RefreshReport) -> None:
    """Results saved before photos were stored get them added: one cheap lookup per 50 channels."""
    def missing(lead) -> bool:
        return _is_youtube_lead(lead) and not lead.get("avatar_url") and not lead.get("data_expired")

    async with sf() as s:
        campaigns = (await s.execute(select(Campaign).where(Campaign.campaign_leads.is_not(None)))).scalars().all()
        saved = (await s.execute(select(SavedLead))).scalars().all()
        ids = [l["id"] for c in campaigns for l in (c.campaign_leads or []) if missing(l)]
        ids += [sl.lead_data["id"] for sl in saved if missing(sl.lead_data or {})]
        ids = list(dict.fromkeys(ids))[: C.AVATAR_BACKFILL_MAX]
        if not ids:
            return
        adapter = adapter_factory()
        fetch = getattr(adapter, "fetch_avatars", None)
        if fetch is None:
            return
        try:
            photos = await fetch(ids)
        except Exception as exc:
            report.warnings.append(f"photo lookup failed: {type(exc).__name__}")
            return
        for c in campaigns:
            new, changed = [], False
            for l in c.campaign_leads or []:
                if missing(l) and l["id"] in photos:
                    l = {**l, "avatar_url": photos[l["id"]]}
                    changed = True
                    report.avatars_added += 1
                new.append(l)
            if changed:
                c.campaign_leads = new
        for sl in saved:
            d = sl.lead_data or {}
            if missing(d) and d["id"] in photos:
                sl.lead_data = {**d, "avatar_url": photos[d["id"]]}
                report.avatars_added += 1
        await s.commit()


async def _fresh_profiles(sf, now: datetime) -> dict[str, dict]:
    """platform_id -> stored profile, for YouTube creators whose data is still within 30 days."""
    async with sf() as s:
        ids = (await s.execute(
            select(Creator.creator_id).where(Creator.platform == PLATFORM, Creator.data_expires_at > now)
        )).scalars().all()
    profiles = await repo.get_creators(list(ids), session_factory=sf)
    return {p["platform_id"]: p for p in profiles.values()}


async def run_refresh(*, adapter_factory: Callable[[], Any], now: Optional[datetime] = None,
                      session_factory=None) -> RefreshReport:
    sf = _factory(session_factory)
    now = _aware(now) or _now()
    report = RefreshReport()

    due = await _due(sf, now)
    report.due = len(due)
    useful = await _useful_ids(sf)
    wanted: list[tuple[Optional[str], str]] = [(cid, pid) for cid, pid, _ in due if pid in useful]
    # Creators in old results that aren't stored (the old engine didn't store them) or are already
    # expired: fetch them too, so those results can be updated instead of emptied.
    queued = {pid for _, pid in wanted}
    fresh = set((await _fresh_profiles(sf, now)).keys())
    stale = await _stale_result_ids(sf, now)
    stored = await repo.creator_ids_for(PLATFORM, stale, session_factory=sf)
    for pid in stale:
        if pid not in queued and pid not in fresh:
            wanted.append((stored.get(pid), pid))
            queued.add(pid)
    to_refresh, report.skipped_over_cap = wanted[: C.REFRESH_MAX_CREATORS], max(0, len(wanted) - C.REFRESH_MAX_CREATORS)

    refreshed: dict[str, dict] = {}
    deleted: set[str] = set()
    if to_refresh:
        adapter = adapter_factory()
        try:
            profiles = await adapter.fetch_profiles([CandidateRef(PLATFORM, pid, "refresh") for _, pid in to_refresh])
        except Exception as exc:  # keep going: expired data must still be deleted
            logger.exception("refresh fetch failed")
            profiles, report.warnings = [], [f"refresh failed: {type(exc).__name__}"]
        report.warnings += list(getattr(adapter, "warnings", []))
        quota_hit = bool(getattr(adapter, "_quota_exhausted", False))
        for p in profiles:
            cid = await repo.upsert_profile(p, session_factory=sf)  # renews data_expires_at
            metrics = compute_metrics(p, BriefContext(), now=now).to_dict()
            await repo.save_snapshot(cid, p, metrics, session_factory=sf)
            refreshed[p["platform_id"]] = p
        report.refreshed = len(refreshed)
        if not quota_hit and not report.warnings:
            # YouTube answered and didn't return these: deleted or private channels.
            gone = [cid for cid, pid in to_refresh if pid not in refreshed and cid]
            for cid in gone:
                await repo.delete_creator(cid, session_factory=sf)
                deleted.add(cid)
            report.gone_on_youtube = len(gone)

    for cid, pid, expires in due:
        if pid not in refreshed and cid not in deleted and expires is not None and expires <= now:
            await repo.delete_creator(cid, session_factory=sf)
            deleted.add(cid)
    report.deleted = len(deleted)

    await _purge_old_copies(sf, now, report)
    await _update_results(sf, now, refreshed, report)
    await _backfill_avatars(sf, adapter_factory, report)
    logger.info("youtube refresh: %s", report.to_dict())
    return report


async def purge_old_checkpoints(saver, *, now: Optional[datetime] = None, limit: int = 1000) -> int:
    """Delete LangGraph threads whose newest checkpoint is older than 30 days (any graph: discovery,
    outreach, or the removed old pipeline). Uses the saver's own delete, so all checkpoint tables stay
    consistent. Returns how many threads were deleted."""
    now = _aware(now) or _now()
    cutoff = (now - TTL).isoformat()
    async with saver.conn.cursor() as cur:
        await cur.execute(
            "SELECT thread_id FROM checkpoints GROUP BY thread_id "
            "HAVING max(checkpoint->>'ts') < %s LIMIT %s",
            (cutoff, limit),
        )
        threads = [row["thread_id"] if isinstance(row, dict) else row[0] for row in await cur.fetchall()]
    for thread_id in threads:
        await saver.adelete_thread(thread_id)
    return len(threads)
