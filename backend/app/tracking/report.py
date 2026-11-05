"""What Track shows (spec §7.6): totals against the goal, the last 30 days, a forecast, each post, creators
ranked with Rebook / OK / Skip, and who's left to pay. Pure arithmetic over stored rows (rule 2)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.tracking import constants as T


@dataclass
class Row:
    """One agreed creator, everything Track needs about them."""
    deal_id: str
    name: str
    avatar_url: Optional[str]
    cost: float
    stage: str
    pay_when: Optional[str]
    paid_amount: Optional[float]
    paid_at: Optional[datetime]
    pay_method: Optional[str]
    typical_views: Optional[float]
    code: Optional[str]
    link: Optional[dict]
    posts: list = field(default_factory=list)  # [dict]: id, deliverable, due_on, video_id, title, thumb, url, live_at, views…
    clicks: int = 0
    conversions: dict = field(default_factory=dict)  # kind → count


def curve_share(age_days: float) -> float:
    """Share of 30-day views a post has after `age_days` (interpolated from VIEW_CURVE)."""
    pts = T.VIEW_CURVE
    if age_days >= pts[-1][0]:
        return 1.0
    for (d0, s0), (d1, s1) in zip(pts, pts[1:]):
        if d0 <= age_days <= d1:
            return s0 + (s1 - s0) * (age_days - d0) / (d1 - d0)
    return pts[-1][1]


def _age(live_at: Optional[datetime], now: datetime) -> Optional[float]:
    return (now - live_at).total_seconds() / 86400 if live_at else None


def results_of(r: Row, goal_kind: str) -> int:
    if goal_kind == "views":
        return sum(p.get("views") or 0 for p in r.posts)
    if goal_kind == "clicks":
        return r.clicks
    kind = T.GOAL_TO_CONVERSION.get(goal_kind, "signup")
    return r.conversions.get(kind, 0) + (r.conversions.get("code_use", 0) if kind == "sale" else 0)


def verdict(r: Row, avg_cost_per: Optional[float], goal_kind: str, now: datetime) -> tuple[str, str]:
    """("rebook" | "ok" | "skip" | "too_early", why). Code only: views against what we expected, and cost per
    result against the campaign's typical (median) cost per result."""
    live = [p for p in r.posts if p.get("live_at")]
    if not live or all((_age(p["live_at"], now) or 0) < T.TOO_EARLY_DAYS for p in live):
        return "too_early", "Wait a few days after the post is live."
    views = sum(p.get("views") or 0 for p in live)
    expected = (r.typical_views or 0) * len(live)
    ratio = views / expected if expected else None
    res = results_of(r, goal_kind)
    cost_per = r.cost / res if res else None
    if (ratio is not None and ratio >= T.REBOOK_VIEWS_RATIO) or (cost_per and avg_cost_per and cost_per <= T.REBOOK_COST_RATIO * avg_cost_per):
        why = f"{ratio:.1f}× the views we expected" if ratio and ratio >= T.REBOOK_VIEWS_RATIO else "cheaper per result than your typical creator"
        return "rebook", why[0].upper() + why[1:] + "."
    if (ratio is not None and ratio < T.SKIP_VIEWS_RATIO) or (cost_per and avg_cost_per and cost_per >= T.SKIP_COST_RATIO * avg_cost_per):
        why = f"only {ratio:.0%} of the views we expected" if ratio is not None and ratio < T.SKIP_VIEWS_RATIO else "costly per result next to your typical creator"
        return "skip", why[0].upper() + why[1:] + "."
    return "ok", "About what we expected."


def build(rows: list[Row], goal: dict, series_rows: dict, now: Optional[datetime] = None) -> dict:
    """`series_rows`: {"views": {date: n}, "clicks": {date: n}, "results": {date: n}} (daily increments)."""
    now = now or datetime.now(timezone.utc)
    kind = goal.get("kind") or "signups"
    value_each = goal.get("value_each")
    spent = sum(r.cost for r in rows)
    paid = sum((r.paid_amount if r.paid_amount is not None else r.cost) for r in rows if r.stage == "paid")
    views = sum(p.get("views") or 0 for r in rows for p in r.posts)
    clicks = sum(r.clicks for r in rows)
    results = sum(results_of(r, kind) for r in rows)
    signups = sum(r.conversions.get("signup", 0) for r in rows)
    code_uses = sum(r.conversions.get("code_use", 0) for r in rows)
    cost_per = round(spent / results, 2) if results else None

    # forecast: each post's views scaled up to 30 days by the usual curve; results scale with views
    projected_views, ends = 0.0, []
    forecastable = False
    for r in rows:
        for p in r.posts:
            age = _age(p.get("live_at"), now)
            if age is None:
                continue
            ends.append(p["live_at"] + timedelta(days=T.FORECAST_DAYS))
            if age >= T.FORECAST_MIN_DAYS and p.get("views") is not None:
                forecastable = True
                projected_views += (p.get("views") or 0) / max(curve_share(age), 0.05)
            else:
                projected_views += p.get("views") or 0
    forecast = None
    if forecastable and views:
        scale = projected_views / views
        forecast = {"views": int(round(projected_views)), "results": int(round(results * scale)) if kind != "views" else int(round(projected_views)),
                    "by": max(ends).date().isoformat() if ends else None, "estimate": True}

    days = [(now.date() - timedelta(days=i)) for i in range(29, -1, -1)]
    series = [{"day": d.isoformat(), "views": series_rows.get("views", {}).get(d, 0), "clicks": series_rows.get("clicks", {}).get(d, 0),
               "results": series_rows.get("results", {}).get(d, 0)} for d in days]

    costs_per = [r.cost / results_of(r, kind) for r in rows if results_of(r, kind)]
    avg_cost_per = statistics.median(costs_per) if costs_per else None  # the median: one outlier doesn't skew everyone
    creators = []
    for r in rows:
        v = sum(p.get("views") or 0 for p in r.posts)
        res = results_of(r, kind)
        tag, why = verdict(r, avg_cost_per, kind, now)
        creators.append({"deal_id": r.deal_id, "name": r.name, "avatar_url": r.avatar_url, "cost": r.cost, "views": v, "clicks": r.clicks,
                         "results": res, "code": r.code, "link": r.link,
                         "cost_per_1k_views": round(r.cost / v * 1000, 2) if v else None,
                         "cost_per_result": round(r.cost / res, 2) if res else None,
                         "expected_views": int((r.typical_views or 0) * max(1, len(r.posts))) or None,
                         "verdict": tag, "why": why, "conversions": r.conversions})
    order = {"rebook": 0, "ok": 1, "too_early": 2, "skip": 3}
    creators.sort(key=lambda c: (order[c["verdict"]], c["cost_per_result"] or 1e9, -c["views"]))

    posts = []
    for r in rows:
        for p in r.posts:
            due, live = p.get("due_on"), p.get("live_at")
            state = "live" if live else "late" if due and due < now.date() else "due"
            posts.append({**p, "deal_id": r.deal_id, "name": r.name, "avatar_url": r.avatar_url, "state": state,
                          "live_at": live.isoformat() if live else None, "due_on": due.isoformat() if due else None})
    rank = {"late": 0, "live": 1, "due": 2}
    posts.sort(key=lambda p: (rank[p["state"]], p["live_at"] or p["due_on"] or ""), reverse=False)

    to_pay, paid_list = [], []
    for r in rows:
        if r.stage == "paid":
            paid_list.append({"deal_id": r.deal_id, "name": r.name, "amount": r.paid_amount if r.paid_amount is not None else r.cost,
                              "paid_at": r.paid_at.isoformat() if r.paid_at else None, "method": r.pay_method})
            continue
        live = any(p.get("live_at") for p in r.posts)
        due_now = r.pay_when in ("upfront", "half_half") or live
        if r.cost and due_now:
            amount = r.cost / 2 if r.pay_when == "half_half" and not live else r.cost
            to_pay.append({"deal_id": r.deal_id, "name": r.name, "avatar_url": r.avatar_url, "amount": round(amount, 2),
                           "why": "Post is live" if live else "Agreed to pay before they post" if r.pay_when == "upfront" else "First half, before they post"})

    return {
        "goal": {"kind": kind, "count": goal.get("count"), "value_each": value_each},
        "totals": {"spent": round(spent, 2), "paid": round(paid, 2), "views": views, "clicks": clicks, "results": results,
                   "signups": signups, "code_uses": code_uses, "cost_per_result": cost_per,
                   "cost_per_1k_views": round(spent / views * 1000, 2) if views else None,
                   "value": round(results * value_each, 2) if value_each and kind in ("signups", "sales") else None,
                   "return": round(results * value_each / spent, 2) if value_each and spent and kind in ("signups", "sales") else None},
        "forecast": forecast, "series": series, "posts": posts, "creators": creators, "to_pay": to_pay, "paid": paid_list,
    }
