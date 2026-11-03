"""Fake-engagement detection (spec §4.5).

Until a platform has ANOMALY_MIN_TRAINING_ROWS creators in the database, simple rules decide.
After that, an IsolationForest trained on our own creators replaces them. Both return a score
in 0..1: above ANOMALY_WARN_ABOVE shows a warning, above ANOMALY_EXCLUDE_ABOVE drops the creator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from app.metrics import constants as C

FEATURES = ("log_followers", "engagement", "comment_ratio", "reach_ratio", "views_cv", "interval_cv")


def feature_row(m: dict) -> list[float]:
    """Feature vector from computed metrics; missing values become 0 (neutral after scaling)."""
    followers = m.get("followers") or 0
    return [
        math.log10(followers + 1),
        m.get("engagement_rate") or 0.0,
        m.get("comment_ratio") or 0.0,
        m.get("reach_ratio") or 0.0,
        m.get("views_cv") or 0.0,
        m.get("interval_cv") or 0.0,
    ]


def rule_score(m: dict) -> tuple[float, list[str]]:
    """Rule-based fallback. Returns (score, reasons)."""
    score, reasons = 0.0, []
    er = m.get("engagement_rate")
    if er is not None and m.get("has_public_views") and er < C.ZOMBIE_ENGAGEMENT_BELOW:
        score, reasons = max(score, 0.85), reasons + ["very low engagement for the views"]
    cr = m.get("comment_ratio")
    if cr is not None and cr < C.LOW_COMMENT_RATIO_BELOW:
        score, reasons = max(score, 0.7), reasons + ["almost no comments compared with likes"]
    rr = m.get("reach_ratio")
    if rr is not None and (m.get("followers") or 0) >= C.LOW_REACH_MIN_FOLLOWERS and rr < C.LOW_REACH_RATIO_BELOW:
        score, reasons = max(score, 0.7), reasons + ["views far below follower count"]
    return score, reasons


@dataclass
class AnomalyModel:
    """IsolationForest plus the numbers needed to map its output to 0..1."""

    forest: object
    mean: np.ndarray
    std: np.ndarray
    cutoff: float  # outlyingness at the contamination boundary
    max_seen: float  # most outlying training row

    def score(self, m: dict) -> float:
        x = (np.array([feature_row(m)]) - self.mean) / self.std
        s = float(-self.forest.score_samples(x)[0])  # higher = more unusual
        if s < self.cutoff:
            return round(C.ANOMALY_WARN_ABOVE * max(0.0, s) / self.cutoff, 3) if self.cutoff > 0 else 0.0
        span = max(self.max_seen - self.cutoff, 1e-9)
        return round(min(1.0, C.ANOMALY_WARN_ABOVE + (1 - C.ANOMALY_WARN_ABOVE) * (s - self.cutoff) / span), 3)


def fit_model(rows: Sequence[dict], random_state: int = 0) -> Optional[AnomalyModel]:
    """Train on one platform's creators. Returns None if there aren't enough rows yet."""
    if len(rows) < C.ANOMALY_MIN_TRAINING_ROWS:
        return None
    from sklearn.ensemble import IsolationForest

    X = np.array([feature_row(r) for r in rows], dtype=float)
    mean, std = X.mean(axis=0), X.std(axis=0)
    std[std == 0] = 1.0
    Xs = (X - mean) / std
    forest = IsolationForest(contamination=C.ANOMALY_CONTAMINATION, random_state=random_state).fit(Xs)
    outlying = -forest.score_samples(Xs)
    cutoff = float(-forest.offset_)
    return AnomalyModel(forest=forest, mean=mean, std=std, cutoff=cutoff, max_seen=float(outlying.max()))


def anomaly_score(m: dict, model: Optional[AnomalyModel] = None) -> tuple[float, list[str]]:
    """Model score when a trained model exists, else rules. Rules still add their reasons."""
    rules, reasons = rule_score(m)
    if model is None:
        return rules, reasons
    return max(model.score(m), rules), reasons
