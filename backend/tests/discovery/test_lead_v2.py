"""Lead v2 data for the creator panel: post cards (best match / above usual / latest), sponsorship,
skipped-reason buckets. All computed in code from data we already fetched: no API, Jev or LLM calls."""

from datetime import datetime, timezone

from app.discovery.legacy import to_legacy_lead
from app.discovery.skipped import bucket, summarise
from app.metrics.posts import analyse_posts, match_terms, matched_topics, sponsorship

T = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _post(i, text, views=1000, likes=50, description=""):
    return {"post_id": f"v{i}", "url": f"https://youtu.be/v{i}", "text": text, "description": description,
            "views": views, "likes": likes, "comments": 3, "published_at": T, "thumbnail_url": f"https://i/{i}.jpg",
            "format": "long"}


def test_topic_matching_needs_most_of_the_words():
    topics = match_terms(["machine learning interviews", "AI agents", "", "ai agents", "the"])
    assert topics == ["machine learning interviews", "AI agents"]  # deduped, empty and stop-word-only dropped
    assert matched_topics("Crack your Machine Learning interview", topics) == ["machine learning interviews"]  # plural folded
    assert matched_topics("Machine shop tour", topics) == []  # 1 of 3 words is not enough
    assert matched_topics("Machine learning interviews in 2026", topics) == ["machine learning interviews"]
    assert matched_topics("Building AI agents with LangGraph", topics) == ["AI agents"]
    assert matched_topics("Cooking pasta", topics) == []


def test_sponsorship_phrases_and_brands():
    assert sponsorship("My setup", "This video is sponsored by NordVPN. Use code KRISH") == (True, ["NordVPN"])
    assert sponsorship("#ad Trying the new phone") == (True, [])
    assert sponsorship("#adventure in the hills") == (False, [])  # "#ad" is a whole tag, not a prefix
    assert sponsorship("Try Brilliant.org", "Thanks to Brilliant.org for sponsoring")[1] == ["Brilliant.org"]
    assert sponsorship("Thanks to everyone who watched") == (False, [])  # no paid phrase, no brand
    assert sponsorship("In partnership with Notion Labs we built this")[1] == ["Notion Labs"]


def test_post_cards_reach_relative_to_the_creators_usual():
    posts = [_post(1, "AI agents explained", views=3000), _post(2, "Vlog", views=1000),
             _post(3, "Q&A", views=500), _post(4, "Sponsored by Brilliant: AI agents", views=1000)]
    cards, signals = analyse_posts(posts, ["AI agents"], limit=3)
    assert [c["id"] for c in cards] == ["v1", "v2", "v3"]  # keeps newest-first order, capped
    assert cards[0]["x_usual"] == 3.0 and cards[0]["matched_topics"] == ["AI agents"]
    assert cards[0]["reach_label"] == "views" and cards[0]["published_at"] == T.isoformat()
    assert signals == {"posts_checked": 4, "fit_posts": 2, "sponsored_posts": 1,
                       "sponsor_brands": ["Brilliant"], "median_reach": 1000}


def test_likes_stand_in_for_views_and_missing_reach_is_safe():
    cards, signals = analyse_posts([_post(1, "photo", views=None, likes=200), _post(2, "photo", views=None, likes=100),
                                    {"post_id": "x", "text": "text post", "views": None, "likes": None}], [])
    assert cards[0]["reach_label"] == "likes" and cards[0]["reach"] == 200 and cards[0]["x_usual"] == 1.33
    assert cards[2]["reach"] is None and cards[2]["x_usual"] is None
    assert signals["median_reach"] == 150
    assert analyse_posts([], ["x"]) == ([], {"posts_checked": 0, "fit_posts": 0, "sponsored_posts": 0,
                                             "sponsor_brands": [], "median_reach": None})


def test_legacy_lead_carries_the_panel_fields():
    profile = {"platform_id": "UC1", "display_name": "Krish", "followers": 10000, "verified": True, "person_id": "p1",
               "recent_posts": [_post(1, "AI agents in production")], "platform_stats": {}}
    record = {"parts": {"fit": 40.0, "health": 20.0, "bonus": 0.0, "risk": -5.0, "country_unknown_factor": None}}
    lead = to_legacy_lead(profile, {"momentum": 1.4}, record, "Fits.", "saas", topics=["AI agents"])
    assert lead["posts"][0]["matched_topics"] == ["AI agents"] and lead["signals"]["fit_posts"] == 1
    assert lead["score_parts"]["fit"] == 40.0 and lead["trend"] == 1.4
    assert lead["verified"] is True and lead["person_id"] == "p1" and lead["match_terms"] == ["AI agents"]
    # older callers (no topics) still work
    assert to_legacy_lead(profile, {}, {}, None, "saas")["match_terms"] == []


def test_skipped_reasons_fold_into_plain_buckets():
    assert bucket("inactive for 140 days") == bucket("no recent posts") == "inactive"
    assert bucket("suspicious engagement: likes spike") == "suspicious engagement"
    assert bucket("below the view floor for saas (high price)") == "too few views"
    assert bucket("Something new: 12 things") == "something new"
    out = summarise([("shortlisted", None), ("filtered_out", "inactive for 3 days; inactive for 3 days"),
                     ("judged", "not an individual creator; posts in a different language")])
    assert out["looked_at"] == 3 and out["skipped"] == 2
    assert {r["reason"]: r["count"] for r in out["reasons"]} == {"inactive": 1, "not an individual creator": 1,
                                                               "different language": 1}
