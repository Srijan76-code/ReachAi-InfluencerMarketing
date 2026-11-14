"""Turn Jev answers + metrics into fit, risk, a final score and a label (spec §4.7).

Pure code: no model calls. Also returns the fields the current results screen reads
(relevance_score, final_score, deal_status, score_breakdown) so the UI keeps working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.judge import constants as K
from app.judge.client import Judgment
from app.metrics.compute import Metrics


@dataclass
class CreatorScore:
    fit: float
    health: float
    risk: float
    bonus: float
    final_score: float
    deal_status: str
    dropped: bool
    drop_reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)  # shown as badges: rising, trend, suspicious
    parts: dict = field(default_factory=dict)  # "why this score": points from fit, health, bonus, risk
    country: Optional[str] = None  # set when Jev judged the audience country (the platform listed none)

    def legacy_fields(self, metrics: Metrics) -> dict:
        """Fields the existing results UI reads."""
        return {
            "relevance_score": round(self.fit * 100),
            "final_score": self.final_score,
            "deal_status": self.deal_status,
            "score_breakdown": {
                "strategy_score": round(self.fit * 100, 1),
                "health_score": round(self.health * 100),
                "risk_penalty": metrics.reliability or "Medium",
            },
        }


def _norm(answer_value: float, levels: int) -> float:
    return max(0.0, min(1.0, answer_value / (levels - 1)))


def _score(j: Judgment, qid: str) -> float:
    """Normalised 0..1 score, or 0 if the question wasn't asked."""
    return _norm(j.score(qid), K.SCORE_LEVELS[qid]) if qid in j.answers else 0.0


def _noul(j: Judgment, qid: str, default: float) -> float:
    return j.noul(qid) if qid in j.answers else default


def label(final_score: float) -> str:
    if final_score >= K.STRONG_BUY_FROM:
        return "Strong Buy"
    if final_score >= K.CONSIDER_FROM:
        return "Consider"
    return "Avoid"


def judged_country(j: Judgment) -> tuple[str, Optional[str]]:
    """Jev's answer to the country question, with the thresholds applied:
    ("in_target", code) | ("outside", None) | ("unknown", None). Unasked counts as unknown."""
    a = j.answers.get("country")
    if a is None:
        return "unknown", None
    choice, conf = str(a.value), (a.confidence if a.confidence is not None else 0.0)
    if choice == "other":
        return ("outside", None) if conf >= K.COUNTRY_JEV_DROP_FROM else ("unknown", None)
    if choice != "not_stated" and conf >= K.COUNTRY_JEV_ACCEPT_FROM:
        return "in_target", choice
    return "unknown", None


def score_creator(j: Judgment, metrics: Metrics, *, exclude_kids_content: bool = False,
                  country_unknown: bool = False, competitor_promos: Optional[list] = None,
                  competitor_mode: str = "show") -> CreatorScore:
    """`country_unknown`: the brief sets target countries and the platform lists no country for this
    creator. Jev's country answer then decides: a target country (kept, no penalty), another country
    (dropped), or no clue (kept and flagged; ranked lower only on platforms that normally list a country)."""
    country = None
    outside = False
    if country_unknown:
        verdict, country = judged_country(j)
        outside = verdict == "outside"
        country_unknown = verdict == "unknown"
    # a missing country only counts against creators on platforms that normally list one
    penalise_unknown = metrics.platform in K.COUNTRY_LISTED_PLATFORMS
    w = K.FIT_WEIGHTS
    topic = _score(j, "topic_fit")
    stage = _score(j, "audience_stage")
    pain = _noul(j, "pain_point", 0.0)
    fit = w["topic_fit"] * topic + w["audience_stage"] * stage + w["pain_point"] * pain

    safety = _score(j, "safety_risk")
    promo = _noul(j, "promo_heavy", 0.0)
    anomaly = metrics.anomaly_score if metrics.anomaly_score >= K.ANOMALY_RISK_FROM else 0.0
    risk = max(safety, K.PROMO_RISK_FACTOR * promo, anomaly)  # "something is wrong" -> max, not average

    trend = _noul(j, "posts_on_trend", 0.0)
    bonus = (K.RISING_BONUS if metrics.rising else 0.0) + (K.TREND_BONUS if trend > K.TREND_THRESHOLD else 0.0)
    if competitor_promos and competitor_mode == "prefer":
        bonus += K.COMPETITOR_BONUS

    raw = K.FINAL_WEIGHTS["fit"] * fit + K.FINAL_WEIGHTS["health"] * metrics.health + bonus - K.RISK_WEIGHT * risk
    parts = {
        "fit": round(100 * K.FINAL_WEIGHTS["fit"] * fit, 1),
        "health": round(100 * K.FINAL_WEIGHTS["health"] * metrics.health, 1),
        "bonus": round(100 * bonus, 1),
        "risk": round(-100 * K.RISK_WEIGHT * risk, 1),
        "country_unknown_factor": K.COUNTRY_UNKNOWN_FACTOR if country_unknown and penalise_unknown else None,
    }
    if country_unknown and penalise_unknown:
        raw *= K.COUNTRY_UNKNOWN_FACTOR
    final = round(100 * max(0.0, min(1.0, raw)), 1)

    drops: list[str] = []
    if outside:
        drops.append("outside the target countries (judged from their posts)")
    if _noul(j, "is_individual", 1.0) < K.DROP_NOT_INDIVIDUAL_BELOW:
        drops.append("not an individual creator")
    if _noul(j, "language_match", 1.0) < K.DROP_LANGUAGE_BELOW:
        drops.append("posts in a different language")
    if exclude_kids_content and _noul(j, "kids_content", 0.0) > K.DROP_KIDS_ABOVE:
        drops.append("content made for children")
    if _noul(j, "injection", 0.0) > K.DROP_INJECTION_ABOVE:
        drops.append("profile contains instructions aimed at AI")
    if competitor_promos and competitor_mode == "avoid":
        drops.append(f"recently promoted a competitor ({competitor_promos[0]['brand']})")

    flags = []
    if metrics.rising:
        flags.append("rising")
    if trend > K.TREND_THRESHOLD:
        flags.append("trend")
    if metrics.anomaly_score >= K.ANOMALY_RISK_FROM:
        flags.append("suspicious")
    if country_unknown:
        flags.append("country_unknown")
    if country:
        flags.append("country_by_jev")
    if competitor_promos:
        flags.append("competitor")

    return CreatorScore(
        fit=round(fit, 4),
        health=metrics.health,
        risk=round(risk, 4),
        bonus=bonus,
        final_score=final,
        deal_status=label(final),
        dropped=bool(drops),
        drop_reasons=drops,
        flags=flags,
        parts=parts,
        country=country,
    )


def select_platforms(
    preset: list[str], answers: Optional[Judgment], all_platforms: list[str]
) -> dict[str, dict]:
    """Spec §4.9: preset by founder type, adjusted by Jev. Returns {platform: {selected, weight, note}}."""
    out: dict[str, dict] = {}
    for p in all_platforms:
        p_yes = answers.noul(f"platform_{p}") if answers and f"platform_{p}" in answers.answers else None
        in_preset = p in preset
        selected = in_preset or (p_yes is not None and p_yes > K.PLATFORM_ADD_ABOVE)
        note = None
        if in_preset and p_yes is not None and p_yes < K.PLATFORM_LOW_FIT_BELOW:
            note = "low fit for this product"
        elif not in_preset and selected:
            note = "added: good fit for this product"
        weight = p_yes if p_yes is not None else (1.0 if in_preset else 0.0)
        out[p] = {"selected": selected, "weight": round(weight if selected else 0.0, 3), "note": note}
    return out
