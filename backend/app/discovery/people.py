"""The "people" step (spec §4.9 identity, roadmap F1.17b): after ranking, one person = one result.

1. Link accounts we already measured: each top creator's own links (bio, description, websites) are looked up
   in the creator database; code decides (app/creators/identity.decide): a link both ways, or one way plus a
   matching name → linked; anything weaker → Jev "same person?" (≥ 0.85) → shown as "Probably also".
2. Same name across platforms in this run, no link: also only via Jev, also only "Probably also".
3. For the top ENRICH_TOP_PEOPLE people, the accounts they link to that we haven't measured are measured now
   (same adapters, same metrics; part of the search's credits), then linked by the same rules.

Cheap first: steps 1-2 are free database lookups; Jev only sees the few pairs code couldn't decide; step 3 only
touches ten people. Any failure here is logged and the search finishes without the extra accounts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.creators import constants as CC
from app.creators import identity as I
from app.creators import repository as repo
from app.metrics.compute import compute_metrics
from app.platforms.base import CandidateRef

logger = logging.getLogger(__name__)


async def _same_person(judge, a: dict, b: dict) -> bool:
    from app.judge import constants as K
    from app.judge.questions import same_person_questions, same_person_state

    try:
        j = await judge(same_person_state(a, b), same_person_questions())
    except Exception as exc:  # noqa: BLE001 - no Jev: don't link
        logger.warning("same-person check failed: %s", exc)
        return False
    return j.noul("same_person") >= CC.NAME_MATCH_MERGE_FROM and j.noul("injection") <= K.DROP_INJECTION_ABOVE


async def _resolve(adapter, platform: str, key: str) -> Optional[str]:
    """The platform id to fetch for a link key: Instagram and LinkedIn use the handle itself; X and YouTube
    handles are looked up (1 provider call / 1 quota unit)."""
    if platform in ("instagram", "linkedin"):
        return key.lstrip("@")
    if platform == "youtube":
        if key.startswith("UC"):
            return key
        page = await adapter.api.channels(part="id", forHandle=key.lstrip("@"))
        items = (page or {}).get("items") or []
        return items[0]["id"] if items else None
    if platform == "x":
        data = await adapter.api.user_info(key.lstrip("@"))
        user = (data or {}).get("data") if isinstance((data or {}).get("data"), dict) else None
        return str(user["id"]) if user and user.get("id") else None
    return None


async def _measure(adapters: dict, platform: str, key: str, metrics_ctx, session_factory, now) -> Optional[str]:
    """Fetches and measures one linked account (no cheap filter: they're already chosen). → creator_id"""
    if platform not in adapters:
        return None
    adapter = adapters[platform]()
    pid = await _resolve(adapter, platform, key)
    if not pid:
        return None
    profiles = await adapter.fetch_profiles([CandidateRef(platform, pid, "cross_link")], None, max_deep=1)
    if not profiles:
        return None
    p = profiles[0]
    m = compute_metrics(p, metrics_ctx, now=now)
    cid = await repo.upsert_profile(p, session_factory=session_factory)
    await repo.save_snapshot(cid, p, m.to_dict(), session_factory=session_factory)
    return cid


async def link_people(ranked: list[dict], *, adapters: dict, judge, metrics_ctx, session_factory, now,
                      enrich: int = CC.ENRICH_TOP_PEOPLE) -> dict:
    """`ranked`: this run's scored creators, best first ({creator_id, platform, display_name, ...}).
    → {"linked": n, "suggested": n, "measured": n} (the links themselves are stored in the database)."""
    stats = {"linked": 0, "suggested": 0, "measured": 0}
    ids = [r["creator_id"] for r in ranked]
    profiles = await repo.get_creators(ids, session_factory=session_factory)
    checks: list[tuple[str, str]] = []
    done: set[frozenset] = set()

    async def consider(a_id: str, b_id: str, a: dict, b: dict) -> None:
        pair = frozenset((a_id, b_id))
        if a_id == b_id or pair in done:
            return
        done.add(pair)
        verdict = I.decide(a, b)
        if verdict == "link":
            await repo.link_accounts(a_id, b_id, source=CC.LINK_SELF, session_factory=session_factory)
            stats["linked"] += 1
        elif verdict == "check" and len(checks) < CC.MAX_SAME_PERSON_CHECKS:
            checks.append((a_id, b_id))

    # 1. links to accounts we've measured before
    wanted = {cid: I.links_of(p) for cid, p in profiles.items()}
    found = await repo.find_by_keys([k for links in wanted.values() for k in links.values()], session_factory=session_factory)
    others = await repo.get_creators(list(set(found.values()) - set(profiles)), session_factory=session_factory)
    every = {**others, **profiles}
    for cid, links in wanted.items():
        for key in links.values():
            other = found.get(key)
            if other and other in every:
                await consider(cid, other, every[cid], every[other])

    # 2. the same name on two platforms in this run, no link either way
    by_platform: dict[str, list[str]] = {}
    for cid in ids:
        if cid in profiles:
            by_platform.setdefault(profiles[cid].get("platform"), []).append(cid)
    plats = list(by_platform)
    for i, pa in enumerate(plats):
        for pb in plats[i + 1:]:
            for a_id in by_platform[pa]:
                for b_id in by_platform[pb]:
                    if I.similarity(profiles[a_id], profiles[b_id]) >= CC.NAME_SIMILAR_FROM:
                        await consider(a_id, b_id, profiles[a_id], profiles[b_id])

    # 3. measure the accounts the top people link to (once per person)
    people = await repo.people_of(ids, session_factory=session_factory)
    seen_people, todo = set(), []
    for cid in ids:
        if len(seen_people) >= enrich:
            break
        person = people.get(cid, {}).get("person_id") or cid
        if person in seen_people or cid not in profiles:
            continue
        seen_people.add(person)
        have = {every.get(a["creator_id"], {}).get("platform") for a in people.get(cid, {}).get("accounts", [])}
        have.add(profiles[cid].get("platform"))
        todo += [(cid, k) for k in wanted.get(cid, {}).values() if k[0] not in have and k not in found]

    async def measure(cid, key):
        try:
            new = await _measure(adapters, key[0], key[1], metrics_ctx, session_factory, now)
        except Exception as exc:  # noqa: BLE001 - one account failing never fails the search
            logger.warning("measuring %s %s failed: %s", key[0], key[1], exc)
            return cid, None
        return cid, new

    for cid, new in await asyncio.gather(*(measure(c, k) for c, k in todo)):
        if not new:
            continue
        stats["measured"] += 1
        fresh = (await repo.get_creators([new], session_factory=session_factory)).get(new)
        if fresh:
            every[new] = fresh
            await consider(cid, new, profiles[cid], fresh)

    # 4. Jev for the pairs code couldn't decide (one request each, in parallel)
    async def check(a_id, b_id):
        return a_id, b_id, await _same_person(judge, every[a_id], every[b_id])

    for a_id, b_id, same in await asyncio.gather(*(check(a, b) for a, b in checks if a in every and b in every)):
        if same:
            await repo.link_accounts(a_id, b_id, source=CC.LINK_NAME_MATCH, confidence=CC.NAME_MATCH_MERGE_FROM,
                                     suggest_only=True, session_factory=session_factory)
            stats["suggested"] += 1
    return stats
