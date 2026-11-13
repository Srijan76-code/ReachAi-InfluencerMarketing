"""Scores mean the same on every platform (decided Nov 13): each creator is ranked against its own
platform and size, reel views get wider reliability bands, and a missing country only counts against
creators on platforms that normally list one."""

from dataclasses import replace

import pytest

from app.discovery.legacy import to_legacy_lead
from app.judge import constants as K
from app.judge.combine import score_creator
from app.metrics import constants as C
from app.metrics.baselines import engagement_percentile
from app.metrics.stats import reliability
from tests.shared_core.test_judging import GOOD, judgment, metrics


@pytest.mark.parametrize("platform,tier,typical", [
    ("instagram", "micro", 0.0199), ("instagram", "mid", 0.0135),
    ("youtube", "micro", 0.0198), ("youtube", "mid", 0.0155), ("x", "micro", 0.0164),
])
def test_a_typical_creator_ranks_mid_pack_on_every_platform(platform, tier, typical):
    """The medians we measured on production (Nov 13) land near the 50th percentile on their own platform."""
    pct = engagement_percentile(typical, platform, tier)
    assert 0.4 <= pct <= 0.6


def test_reel_views_get_wider_reliability_bands():
    swingy = [1000, 150, 2900, 200, 2900, 1000]  # spread 0.825: past YouTube's 0.8 line, inside Instagram's 1.04
    assert reliability(swingy, "youtube") == "Low"
    assert reliability(swingy, "instagram") == "Medium"
    assert C.RELIABILITY_SCALE_BY_PLATFORM["instagram"] > 1


@pytest.mark.parametrize("platform,cut", [("youtube", True), ("linkedin", True), ("instagram", False), ("x", False)])
def test_unknown_country_only_cuts_where_the_platform_lists_one(platform, cut):
    m = replace(metrics(), platform=platform)
    known = score_creator(judgment(**GOOD), m)
    unknown = score_creator(judgment(**GOOD), m, country_unknown=True)
    expected = known.final_score * (K.COUNTRY_UNKNOWN_FACTOR if cut else 1.0)
    assert unknown.final_score == pytest.approx(expected, abs=0.1)
    assert "country_unknown" in unknown.flags  # the badge stays either way
    assert (unknown.parts["country_unknown_factor"] is not None) == cut


def test_no_views_means_no_price_yet_not_zero():
    """A photo-only Instagram creator has no public views: the lead says "unknown", never "$0" or 0 views."""
    lead = to_legacy_lead({"platform": "instagram", "platform_id": "p", "followers": 12000}, {"median_views": None},
                          {}, None, "fitness")
    assert lead["valuation"] is None and lead["metrics"]["avg_views"] is None
    priced = to_legacy_lead({"platform": "youtube", "platform_id": "y"}, {"median_views": 4200.4, "valuation": 63.0},
                            {}, None, "saas")
    assert priced["valuation"] == 63.0 and priced["metrics"]["avg_views"] == 4200
