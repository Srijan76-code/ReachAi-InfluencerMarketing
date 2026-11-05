"""Track's arithmetic (code only): the view curve, verdicts, totals, forecast, who to pay; finding posts by link or code."""

from datetime import date, datetime, timedelta, timezone

from app.tracking import report as R
from app.tracking.find import matched_by, uploads_playlist, video_id_from

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)


def row(name, cost, views=None, age=None, typical=1000, signups=0, stage="live", pay_when="on_live", clicks=0, due=None):
    posts = [{"id": name, "views": views, "live_at": NOW - timedelta(days=age) if age is not None else None, "due_on": due, "url": None}]
    return R.Row(deal_id=name, name=name, avatar_url=None, cost=cost, stage=stage, pay_when=pay_when, paid_amount=None, paid_at=None,
                 pay_method=None, typical_views=typical, code=None, link=None, posts=posts, clicks=clicks, conversions={"signup": signups})


def test_view_curve_is_interpolated_and_capped():
    assert R.curve_share(0) == 0 and R.curve_share(30) == 1.0 and R.curve_share(90) == 1.0
    assert R.curve_share(5) == 0.65  # halfway between day 3 (0.55) and day 7 (0.75)


def test_verdicts_compare_with_expected_views_and_average_cost():
    great, poor, fine, new = row("a", 10, 2000, 10, signups=20), row("b", 50, 300, 10, signups=1), row("c", 20, 1000, 10, signups=5), row("d", 20, 100, 1)
    rep = R.build([great, poor, fine, new], {"kind": "signups"}, {}, now=NOW)
    v = {c["name"]: c["verdict"] for c in rep["creators"]}
    assert v == {"a": "rebook", "b": "skip", "c": "ok", "d": "too_early"}
    assert [c["name"] for c in rep["creators"]][0] == "a"  # best first
    assert next(c for c in rep["creators"] if c["name"] == "a")["why"] == "2.0× the views we expected."


def test_totals_forecast_and_to_pay():
    rows = [row("a", 10, 1100, 3, signups=11), row("b", 30, None, None, stage="agreed", pay_when="upfront", due=date(2026, 11, 10))]
    rep = R.build(rows, {"kind": "signups", "count": 500, "value_each": 5}, {}, now=NOW)
    t = rep["totals"]
    assert t["spent"] == 40 and t["views"] == 1100 and t["results"] == 11 and t["cost_per_result"] == round(40 / 11, 2)
    assert t["value"] == 55 and t["return"] == round(55 / 40, 2)
    assert rep["forecast"] == {"views": 2000, "results": 20, "by": "2026-12-17", "estimate": True}  # 1100 / 0.55
    assert [p["state"] for p in rep["posts"]] == ["late", "live"]
    assert [(p["name"], p["amount"]) for p in rep["to_pay"]] == [("a", 10), ("b", 30)]  # live, and agreed upfront


def test_no_forecast_until_a_post_has_two_days():
    assert R.build([row("a", 10, 100, 1)], {"kind": "views"}, {}, now=NOW)["forecast"] is None


def test_finding_posts_by_link_or_code_and_reading_links():
    assert matched_by("Try it: https://reach.ai/r/k3x9p2m", "k3x9p2m", "SRIJAN42") == "link"
    assert matched_by("Use code srijan42 for 10% off", "zzz", "SRIJAN42") == "code"
    assert matched_by("Use code SRIJAN421", None, "SRIJAN42") is None
    assert video_id_from("https://youtu.be/dQw4w9WgXcQ?t=3") == "dQw4w9WgXcQ"
    assert video_id_from("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert video_id_from("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=x") == "dQw4w9WgXcQ"
    assert video_id_from("https://evil.com/watch?v=dQw4w9WgXcQ") is None
    assert uploads_playlist("UCabc") == "UUabc" and uploads_playlist("x") is None


def test_post_analysis_against_their_usual():
    r = row("a", 20, 3000, 10, typical=1000, signups=6)
    r.posts[0].update(likes=250, comments=50)
    r.engagement_usual = 0.05
    a = R.post_analysis(r.posts[0], r, NOW, "signups", 1)
    assert a == {"vs_usual": 3.0, "trend": "trending", "views_per_day": 300, "engagement": 10.0, "engagement_vs_usual": 2.0, "results": 6}
    assert R.post_analysis({"views": None}, r, NOW, "signups", 1)["trend"] is None
    assert R.post_analysis(r.posts[0], r, NOW, "signups", 2)["results"] is None  # two live posts: can't split results


def test_insights_only_when_backed_by_data():
    def fmt(r, k):
        r.posts[0]["deliverable"] = k
        return r
    rows = [fmt(row("s1", 10, 10000, 10, typical=2000, signups=10), "short"), fmt(row("s2", 10, 8000, 10, typical=2000, signups=8), "short"),
            fmt(row("v1", 100, 5000, 10, typical=20000, signups=5), "integration"), fmt(row("v2", 100, 4000, 10, typical=20000, signups=4), "integration"),
            row("late", 30, None, None, stage="agreed", due=date(2026, 11, 1))]
    for r in rows:
        r.fair_low, r.fair_high = 80, 120
    text = " | ".join(i["text"] for i in R.build(rows, {"kind": "signups"}, {}, now=NOW)["insights"])
    assert "1 post is late (late)" in text
    assert "Shorts cost $1.11 per 1,000 views, against $22 for sponsored segments." in text
    assert "Smaller channels brought signups 20.0× cheaper" in text
    assert "s1's audience converts best: 1 signup per 1,000 views." in text
    assert "s1's post is at 5.0× their usual views." in text
    assert "You're paying 50% under the fair price on average." in text
    assert R.build([row("x", 10, 100, 1)], {"kind": "signups"}, {}, now=NOW)["insights"] == [
        {"kind": "setup", "tone": "plain", "action": "setup", "text": "Posts are live but no signups are counted yet. Set up counting to see which creators bring them."}]
