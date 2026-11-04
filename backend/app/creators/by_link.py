"""Add a creator the founder already knows, by their channel link (roadmap F1.23). Same measurements as a
search (metrics, fair price, posts), with no Jev or LLM call: the founder chose them, so there's no fit
score. Costs about 3 YouTube quota units."""

from __future__ import annotations

import re
from typing import Optional

from app.platforms.base import CandidateRef

_CHANNEL = re.compile(r"(?:youtube\.com/channel/)?(UC[\w-]{22})\b")
_HANDLE = re.compile(r"(?:youtube\.com/)?@([\w.\-]{3,30})")


def parse_youtube(link: str) -> tuple[Optional[str], Optional[str]]:
    """(channel_id, handle) from a channel link, an @handle or a bare channel id."""
    link = (link or "").strip()
    m = _CHANNEL.search(link)
    if m:
        return m.group(1), None
    m = _HANDLE.search(link)
    return (None, m.group(1)) if m else (None, None)


async def lead_from_link(link: str, details: dict, *, api, email: Optional[str] = None,
                         topics: Optional[list] = None) -> Optional[dict]:
    """A results-list lead for the channel at `link`, or None if YouTube doesn't know it."""
    from app.discovery.brief import parse_brief
    from app.discovery.legacy import to_legacy_lead
    from app.metrics.compute import compute_metrics
    from app.platforms.youtube import YouTubeAdapter

    channel_id, handle = parse_youtube(link)
    if handle and not channel_id:
        page = await api.channels(part="id", forHandle=f"@{handle}")
        items = (page or {}).get("items") or []
        channel_id = items[0]["id"] if items else None
    if not channel_id:
        return None
    adapter = YouTubeAdapter(api)
    profiles = await adapter.fetch_profiles([CandidateRef("youtube", channel_id, "added_by_you")])
    if not profiles:
        return None
    p = profiles[0]
    brief = parse_brief(details or {})
    m = compute_metrics(p, brief.metrics_context()).to_dict()
    record = {"creator_id": f"youtube:{channel_id}", "found_via": "added_by_you", "flags": ["added_by_you"],
              "final_score": None, "deal_status": "Added by you"}
    lead = to_legacy_lead(p, m, record, "You added this creator.", brief.industry, topics=topics or [])
    if email:
        lead["socials"] = {**(lead.get("socials") or {}), "email": email}
    lead["added_by_you"] = True
    return lead
