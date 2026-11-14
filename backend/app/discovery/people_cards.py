"""Each result's other platforms (roadmap F1.17b): what the results row (platform icons, total audience) and the
creator panel's switcher show. Every number comes from code: metrics measured on that platform's own posts."""

from __future__ import annotations

from typing import Optional

from app.creators import identity as I
from app.creators import repository as repo

PLATFORM_ORDER = ("youtube", "x", "instagram", "linkedin")


def account_card(p: dict, *, status: str, main: bool = False, scored: Optional[dict] = None) -> dict:
    m = p.get("metrics") or {}
    er = m.get("engagement_rate")
    return {
        "creator_id": p.get("creator_id"), "platform": p.get("platform"), "handle": p.get("handle"),
        "name": p.get("display_name"), "url": p.get("url"), "avatar_url": p.get("avatar_url"),
        "followers": p.get("followers") or 0,
        "avg_views": int(m["median_views"]) if m.get("median_views") else None,
        "engagement_rate": round(er * 100, 2) if er is not None else None,
        "fair_low": m.get("fair_low"), "fair_high": m.get("fair_high"), "valuation": m.get("valuation"),
        "posts_per_week": round(7 / m["posting_interval_days"], 1) if m.get("posting_interval_days") else None,
        "score": (scored or {}).get("final_score"),
        "status": status,  # main | linked | suggested | unmeasured
        "measured": True, "main": main,
    }


def unmeasured_card(platform: str, key: str, url: Optional[str]) -> dict:
    handle = key.lstrip("@") if not key.startswith("UC") else None
    return {"creator_id": None, "platform": platform, "handle": handle, "url": url, "status": "unmeasured",
            "measured": False, "main": False, "key": key}


async def accounts_for(main: dict, *, scored: dict, session_factory=None) -> list[dict]:
    """[main account, other linked accounts, "probably also" suggestions, links not measured yet], one per
    platform, in PLATFORM_ORDER after the main one."""
    cid = main.get("creator_id")
    found = (await repo.people_of([cid], session_factory=session_factory)).get(cid) or {"accounts": []}
    others = await repo.get_creators([a["creator_id"] for a in found["accounts"]], session_factory=session_factory)
    cards = {main.get("platform"): account_card(main, status="main", main=True, scored=scored.get(cid))}
    for a in sorted(found["accounts"], key=lambda a: a["status"] != "linked"):  # linked before suggested
        p = others.get(a["creator_id"])
        if p and p.get("platform") not in cards:
            p.setdefault("creator_id", a["creator_id"])
            cards[p["platform"]] = account_card(p, status=a["status"], scored=scored.get(a["creator_id"]))
    links = I.links_of(main)
    urls = {I.parse_link(str(u)): u for u in list((main.get("cross_links") or {}).values()) + list(main.get("external_links") or [])}
    # measured before and not linked: we checked, it's someone else (a sponsor, a friend): don't offer it again
    checked = await repo.find_by_keys([k for p, k in links.items() if p not in cards], session_factory=session_factory)
    for platform, key in links.items():
        if platform not in cards and key not in checked:
            cards[platform] = unmeasured_card(platform, key[1], urls.get(key))
    first = cards.pop(main.get("platform"))
    return [first] + [cards[p] for p in PLATFORM_ORDER if p in cards]


async def attach_accounts(leads: list[dict], profiles: dict, scored: dict, *, session_factory=None) -> None:
    """Adds "accounts" and "reach_total" (followers on the main account plus linked ones; suggestions don't
    count until confirmed) to each lead, in place."""
    by_platform_id = {(p.get("platform"), p.get("platform_id")): (cid, p) for cid, p in profiles.items()}
    for lead in leads:
        hit = by_platform_id.get((lead.get("platform"), lead.get("id")))
        if not hit:
            continue
        cid, p = hit
        p = {**p, "creator_id": cid}
        cards = await accounts_for(p, scored=scored, session_factory=session_factory)
        lead["accounts"] = cards
        lead["reach_total"] = sum(c.get("followers") or 0 for c in cards if c["status"] in ("main", "linked"))
