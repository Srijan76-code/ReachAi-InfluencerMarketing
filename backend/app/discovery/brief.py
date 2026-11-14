"""Turn the campaign form payload (frontend SubmitCampaignButton) into one typed brief."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.judge.questions import JudgeBrief
from app.metrics.compute import BriefContext

# ISO 3166-1 alpha-2 codes (the frontend currently sends the first two letters of a country
# name, e.g. "UN" for United States; codes not in this set are ignored rather than trusted).
ISO_COUNTRIES = set(
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ "
    "CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR "
    "GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO "
    "JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR "
    "MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO "
    "RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV "
    "TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split()
) | {"UK"}

PRICE_TIER = {"low_ticket": "low", "mid_ticket": "medium", "high_ticket": "high"}


@dataclass
class Brief:
    brand_name: str
    product: str  # the outcome the product delivers
    industry: str
    business_model: str  # b2b | b2c | d2c
    price_range: str  # low_ticket | mid_ticket | high_ticket
    persona: str
    locations: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=lambda: ["en"])
    goal: str = "signups"
    creator_type: str = "mentor"
    budget_total: int = 0
    creator_count: int = 5
    min_subscribers: int = 1_000
    max_subscribers: int | None = None
    target_countries: list[str] = field(default_factory=list)
    exclude_kids_content: bool = True
    ignored_countries: list[str] = field(default_factory=list)  # codes the form sent that aren't real
    platforms: list[str] = field(default_factory=list)  # chosen by the user; empty = ReachAI chooses
    competitors: list[str] = field(default_factory=list)  # entered by the user; empty = the strategy's suggestions
    competitor_mode: str = "show"  # show | prefer | avoid: what promoting a competitor does to a creator

    @property
    def founder_type(self) -> str:
        return "b2b" if self.business_model == "b2b" else "consumer"

    @property
    def price_tier(self) -> str:
        return PRICE_TIER.get(self.price_range, "medium")

    def metrics_context(self) -> BriefContext:
        return BriefContext(industry=(self.industry or "other").lower(), price_tier=self.price_tier)

    def judge_brief(self, *, pain_points=None, trend_topics=None, safety_level="medium") -> JudgeBrief:
        return JudgeBrief(
            product=f"{self.brand_name}: {self.product}",
            persona=self.persona,
            category=self.industry,
            pain_points=list(pain_points or []),
            languages=self.languages or ["en"],
            safety_level=safety_level,
            trend_topics=list(trend_topics or []),
            target_countries=self.target_countries,
            exclude_kids_content=self.exclude_kids_content,
        )

    def constraints(self) -> dict:
        return {
            "min_subscribers": self.min_subscribers,
            "max_subscribers": self.max_subscribers,
            "target_countries": self.target_countries,
        }

    def hash(self) -> str:
        # competitors only change code-side scoring, so they don't invalidate cached strategies and Jev answers
        d = {k: v for k, v in asdict(self).items() if k not in ("competitors", "competitor_mode")}
        return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)


def _clean_countries(codes: Any) -> tuple[list[str], list[str]]:
    good, bad = [], []
    for c in codes or []:
        code = str(c).strip().upper()
        if not code:
            continue
        (good if code in ISO_COUNTRIES else bad).append("GB" if code == "UK" else code)
    return list(dict.fromkeys(good)), bad


COMPETITOR_MODES = ("show", "prefer", "avoid")
MAX_COMPETITORS = 10


def _clean_competitors(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    names = [" ".join(str(v).split())[:60] for v in values]
    return list(dict.fromkeys(n for n in names if len(n) >= 2))[:MAX_COMPETITORS]


def _clean_platforms(values: Any) -> list[str]:
    from app.platforms.base import PLATFORMS

    if not isinstance(values, (list, tuple)):
        return []  # the old single `platform` field is ignored: old forms always sent "youtube"
    names = [str(v).strip().lower() for v in values]
    return list(dict.fromkeys(n for n in names if n in PLATFORMS))


def parse_brief(details: dict) -> Brief:
    details = details or {}
    brand, audience = details.get("brand") or {}, details.get("audience") or {}
    campaign, cons = details.get("campaign") or {}, details.get("constraints") or {}
    countries, ignored = _clean_countries(cons.get("target_countries") or audience.get("locations"))
    min_s = cons.get("min_subscribers")
    max_s = cons.get("max_subscribers")
    if min_s is not None and max_s is not None and max_s < min_s:
        min_s, max_s = max_s, min_s
    return Brief(
        brand_name=(brand.get("name") or "the brand").strip(),
        product=(brand.get("core_outcome") or "").strip(),
        industry=(brand.get("industry") or "other").strip().lower(),
        business_model=(brand.get("business_model") or "b2c").lower(),
        price_range=(brand.get("product_price_range") or "mid_ticket").lower(),
        persona=(audience.get("target_persona") or "").strip(),
        locations=countries,
        languages=[str(l).lower() for l in (audience.get("languages") or ["en"])],
        goal=campaign.get("goal") or "signups",
        creator_type=campaign.get("creator_authority_level") or "mentor",
        budget_total=int(campaign.get("budget_total") or 0),
        creator_count=max(1, min(50, int(campaign.get("creator_count") or 5))),
        min_subscribers=int(min_s) if min_s is not None else 1_000,
        max_subscribers=int(max_s) if max_s is not None else None,
        target_countries=countries,
        exclude_kids_content=bool(cons.get("exclude_kids_content", True)),
        ignored_countries=ignored,
        platforms=_clean_platforms(campaign.get("platforms")),
        competitors=_clean_competitors(campaign.get("competitors")),
        competitor_mode=campaign.get("competitor_mode") if campaign.get("competitor_mode") in COMPETITOR_MODES else "show",
    )
