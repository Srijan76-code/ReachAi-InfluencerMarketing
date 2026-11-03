import random

import pytest

from app.metrics import constants as C
from app.metrics import stats
from app.metrics.anomaly import anomaly_score, fit_model
from app.metrics.baselines import engagement_percentile, percentile_among, prior_percentile
from app.metrics.compute import BriefContext, compute_metrics, health_score, passes_gates, view_floor
from app.metrics.pricing import cpm, expected_clicks, fair_range, geo_multiplier, valuation
from app.platforms.base import PLATFORMS, CreatorProfile, PlatformAdapter
from tests.shared_core.factories import NOW, post, profile

BRIEF = BriefContext(industry="edtech", price_tier="high")


# --- stats -------------------------------------------------------------------------

def test_follower_tiers_and_boundaries():
    assert stats.follower_tier(None) == "nano"
    assert stats.follower_tier(9_999) == "nano"
    assert stats.follower_tier(10_000) == "micro"
    assert stats.follower_tier(499_999) == "mid"
    assert stats.follower_tier(5_000_000) == "mega"


def test_median_is_robust_to_one_viral_video():
    posts = [post(i, views=10_000) for i in range(9)] + [post(9, views=2_000_000)]
    assert stats.median_views(posts) == 10_000
    assert stats.reliability(stats.views_of(posts)) == "High"


def test_reliability_bands():
    assert stats.reliability([100, 100, 100]) == "High"
    assert stats.reliability([100, 150, 60, 200, 40]) in {"Medium", "Low"}
    assert stats.reliability([10, 1000, 50, 5000, 20]) == "Low"
    assert stats.reliability([]) is None
    assert stats.reliability([0, 0, 0]) is None  # median 0: undefined, not a crash


def test_shorts_and_long_videos_are_not_mixed():
    longs = [post(i, views=50_000) for i in range(4)]
    shorts = [post(10 + i, views=500, short=True) for i in range(6)]
    chosen = stats.primary_format_posts(longs + shorts)
    assert all(p["is_short_form"] for p in chosen)  # more shorts -> compare shorts
    assert stats.primary_format_posts(longs[:2] + shorts[:2]) == longs[:2]  # tie -> long-form


def test_engagement_with_and_without_views():
    assert stats.engagement_rate([post(0, views=1000, likes=50, comments=10)], 5000) == pytest.approx(0.06)
    linkedin = [post(0, views=None, likes=200, comments=50)]
    assert stats.engagement_rate(linkedin, 10_000) == pytest.approx(0.025)
    assert stats.engagement_rate([post(0, views=0, likes=0, comments=0)], 100) is None
    assert stats.engagement_rate([], 100) is None


def test_momentum_and_outperformance():
    newest = [post(i, views=30_000) for i in range(5)]
    older = [post(5 + i, views=10_000) for i in range(10)]
    assert stats.momentum(newest + older) == pytest.approx(3.0)
    assert stats.momentum(newest + older[:2]) is None  # not enough posts
    assert stats.outperformance(newest, 15_000) == pytest.approx(2.0)
    assert stats.outperformance(newest, 0) is None


def test_dates_handle_missing_and_naive_values():
    posts = [post(0, days_ago=10), {**post(1), "published_at": None}]
    assert stats.days_since_last_post(posts, NOW) == 10
    naive = [{**post(0), "published_at": NOW.replace(tzinfo=None)}]
    assert stats.days_since_last_post(naive, NOW) == 0
    assert stats.days_since_last_post([{**post(0), "published_at": None}], NOW) is None
    assert stats.posting_interval_days([post(0)]) is None


def test_cadence_score_steps():
    assert stats.cadence_score(3) == 1.0
    assert stats.cadence_score(30) == 0.7
    assert stats.cadence_score(60) == 0.4
    assert stats.cadence_score(400) == C.CADENCE_SCORE_FLOOR
    assert stats.cadence_score(None) == C.CADENCE_SCORE_FLOOR


# --- baselines ------------------------------------------------------------------------

def test_prior_percentile_shape():
    assert prior_percentile(0.04, 0.04) == pytest.approx(0.5)
    assert prior_percentile(0.12, 0.04) == pytest.approx(1.0)
    assert prior_percentile(0.04 / 3, 0.04) == pytest.approx(0.0)
    assert prior_percentile(0, 0.04) == 0.0


def test_real_peers_replace_prior_only_when_enough():
    few = [0.01] * 10
    many = [i / 1000 for i in range(C.MIN_PEERS)]
    assert engagement_percentile(0.05, "youtube", "mid", few) == prior_percentile(0.05, C.ENGAGEMENT_PRIOR["youtube"]["mid"])
    assert engagement_percentile(0.1, "youtube", "mid", many) == percentile_among(0.1, many)
    assert engagement_percentile(None, "youtube", "mid") is None


# --- pricing --------------------------------------------------------------------------

def test_pricing_matches_old_pipeline_for_youtube():
    # old pipeline: (avg_views / 1000) * INDUSTRY_CPM * geo multiplier
    assert cpm("youtube", "edtech", "IN") == pytest.approx(22.0 * 0.25)
    assert valuation("youtube", 40_000, "mid", "edtech", "IN") == pytest.approx(220.0)
    assert valuation("youtube", None, "mid", "edtech", "IN") is None
    assert geo_multiplier(None) == C.GEO_DEFAULT
    assert geo_multiplier("us") == 1.0


def test_linkedin_price_without_views_and_fair_range():
    assert valuation("linkedin", None, "micro", "saas", "US") == C.LINKEDIN_PRICE_BY_TIER["micro"]
    assert fair_range(100.0, "Low") == (60.0, 150.0)
    assert fair_range(None, "High") is None
    assert expected_clicks(10_000, "tech") == 250
    assert expected_clicks(None, "tech") is None


# --- compute + gates ---------------------------------------------------------------------

def test_compute_metrics_for_a_healthy_creator():
    m = compute_metrics(profile(), BRIEF, now=NOW)
    assert m.tier == "mid" and m.has_public_views and m.posts_used == 15
    assert m.median_views == 10_000 and m.reliability == "High"
    assert 0 <= m.health <= 1 and m.anomaly_score < C.ANOMALY_WARN_ABOVE
    assert m.fair_low < m.valuation < m.fair_high
    ok, reason = passes_gates(m, BRIEF)
    assert ok, reason


def test_rising_creator_is_flagged():
    posts = [post(i, views=40_000, days_ago=2 + i) for i in range(5)] + [post(5 + i, views=10_000) for i in range(10)]
    assert compute_metrics(profile(posts=posts), BRIEF, now=NOW).rising


@pytest.mark.parametrize(
    "posts,reason",
    [
        ([], "no recent posts"),
        ([post(i, days_ago=300 + i) for i in range(10)], "inactive"),
        ([post(i, views=150) for i in range(10)], "too few views"),
        ([post(i, views=800) for i in range(10)], "below the view floor"),
    ],
)
def test_gates_drop_bad_creators(posts, reason):
    m = compute_metrics(profile(posts=posts), BRIEF, now=NOW)
    ok, why = passes_gates(m, BRIEF)
    assert not ok and reason in why


def test_view_floor_follows_price_tier():
    assert view_floor(BriefContext("edtech", "high")) == 1000
    assert view_floor(BriefContext("edtech", "low")) == 4000
    assert view_floor(BriefContext("unknown", "medium")) == 2000


def test_linkedin_creator_without_views_is_not_dropped_for_views():
    posts = [post(i, views=None, likes=300, comments=40) for i in range(10)]
    m = compute_metrics(profile(platform="linkedin", followers=20_000, posts=posts), BRIEF, now=NOW)
    assert not m.has_public_views and m.median_views is None
    assert m.valuation == C.LINKEDIN_PRICE_BY_TIER["micro"] * geo_multiplier("IN")
    assert passes_gates(m, BRIEF)[0]


def test_health_treats_unknown_engagement_as_neutral():
    assert health_score(None, "High", 3) == pytest.approx(0.4 * 0.5 + 0.3 * 1.0 + 0.3 * 1.0)


# --- anomaly --------------------------------------------------------------------------------

def test_rules_catch_bought_engagement():
    zombie = {"followers": 500_000, "engagement_rate": 0.001, "has_public_views": True, "comment_ratio": 0.05, "reach_ratio": 0.1}
    score, reasons = anomaly_score(zombie)
    assert score > C.ANOMALY_EXCLUDE_ABOVE and reasons
    no_comments = {"followers": 50_000, "engagement_rate": 0.04, "has_public_views": True, "comment_ratio": 0.0001}
    assert anomaly_score(no_comments)[0] >= C.ANOMALY_WARN_ABOVE
    normal = {"followers": 50_000, "engagement_rate": 0.04, "has_public_views": True, "comment_ratio": 0.05, "reach_ratio": 0.3}
    assert anomaly_score(normal) == (0.0, [])


def test_suspicious_creator_is_dropped_by_gates():
    posts = [post(i, views=20_000, likes=10, comments=0) for i in range(10)]
    m = compute_metrics(profile(posts=posts), BRIEF, now=NOW)
    ok, why = passes_gates(m, BRIEF)
    assert not ok and "suspicious" in why


def test_isolation_forest_needs_enough_rows_and_flags_outliers():
    assert fit_model([{}] * 10) is None
    rng = random.Random(0)
    rows = [
        {"followers": rng.randint(20_000, 300_000), "engagement_rate": rng.uniform(0.02, 0.06),
         "comment_ratio": rng.uniform(0.03, 0.08), "reach_ratio": rng.uniform(0.1, 0.5),
         "views_cv": rng.uniform(0.2, 0.8), "interval_cv": rng.uniform(0.2, 0.8)}
        for _ in range(C.ANOMALY_MIN_TRAINING_ROWS)
    ]
    model = fit_model(rows)
    typical = model.score(rows[0])
    weird = model.score({"followers": 5_000_000, "engagement_rate": 0.4, "comment_ratio": 0.0,
                         "reach_ratio": 0.001, "views_cv": 6.0, "interval_cv": 5.0})
    assert typical < C.ANOMALY_WARN_ABOVE
    assert weird >= C.ANOMALY_EXCLUDE_ABOVE
    assert 0.0 <= typical <= 1.0 and 0.0 <= weird <= 1.0


# --- interface -------------------------------------------------------------------------------

def test_adapter_protocol_is_checkable():
    class Fake:
        platform = "youtube"
        async def source_candidates(self, strategy, limits): return []
        async def fetch_profiles(self, refs): return []
        def cheap_filter(self, profile, constraints): return True, None
        def priors(self): return None
        def estimate_cost_usd(self, limits): return 0.0

    assert isinstance(Fake(), PlatformAdapter)
    assert not isinstance(object(), PlatformAdapter)
    assert set(PLATFORMS) == {"youtube", "x", "instagram", "linkedin"}
    p: CreatorProfile = profile()
    assert p["platform"] == "youtube"
