"""fusion.py — the real activity-score math (Nelson's piece).

Replaces the placeholder in routes/narrative.py's _confidence(), which
currently just counts two booleans:

    fired = sum([trends.spike_detected, jets.proximity_flag])
    return {0: "low", 1: "medium", 2: "high"}[fired]

This does a real weighted combination instead, and is built to upgrade
automatically once Dominic's satellite vehicle-count lands in the schema —
until then it just redistributes that weight across trends + jets so
nothing breaks.

Import this from routes/narrative.py:
    from fusion import compute_activity_score
"""

from __future__ import annotations
from dataclasses import dataclass

from schemas import TrendsResponse, JetsResponse


# Default weights. Sum to 1.0. Satellite weight only applies once a real
# count-change number is passed in; otherwise it's redistributed to the
# other two proportionally (see _effective_weights).
DEFAULT_WEIGHTS = {"trend": 0.5, "jet": 0.3, "satellite": 0.2}


def _effective_weights(satellite_available: bool, weights: dict) -> dict:
    if satellite_available:
        return weights
    remaining = weights["trend"] + weights["jet"]
    return {
        "trend": weights["trend"] / remaining,
        "jet": weights["jet"] / remaining,
        "satellite": 0.0,
    }


def trend_component(trends: TrendsResponse) -> float:
    """
    Recent-vs-baseline pct change, clamped to [0, 1]. Reuses the same
    baseline/recent split as the spike detector in routes/trends.py so
    the two stay consistent with each other.
    Returns 0.0 if there's no usable trend data, never raises.
    """
    pts = trends.points
    if not pts:
        return 0.0
    if len(pts) < 6:
        baseline = pts[0].interest or 1
        recent = pts[-1].interest
    else:
        baseline = sum(p.interest for p in pts[:-2]) / (len(pts) - 2)
        recent = sum(p.interest for p in pts[-2:]) / 2
    if baseline <= 0:
        return 0.0
    pct_change = (recent - baseline) / baseline
    return max(0.0, min(1.0, pct_change))


def jet_component(jets: JetsResponse) -> float:
    """Binary today (proximity_flag from jets.py). Room to grade by
    distance later, but a flat 0/1 is honest and defensible right now."""
    return 1.0 if jets.proximity_flag else 0.0


def satellite_component(count_change_pct: float | None) -> float:
    """count_change_pct: (after_count - before_count) / before_count,
    already computed elsewhere once Dominic's YOLO counts exist. None
    means 'not available yet' — the caller should not fabricate a number."""
    if count_change_pct is None:
        return 0.0
    return max(0.0, min(1.0, count_change_pct))


@dataclass
class ActivityScore:
    score: float          # 0.0 - 1.0
    confidence: str        # "low" | "medium" | "high"
    trend_component: float
    jet_component: float
    satellite_component: float | None  # None = not available yet


def compute_activity_score(
    trends: TrendsResponse,
    jets: JetsResponse,
    satellite_count_change_pct: float | None = None,
    weights: dict | None = None,
) -> ActivityScore:
    weights = weights or DEFAULT_WEIGHTS
    satellite_available = satellite_count_change_pct is not None
    w = _effective_weights(satellite_available, weights)

    t = trend_component(trends)
    j = jet_component(jets)
    s = satellite_component(satellite_count_change_pct)

    score = round(min(1.0, t * w["trend"] + j * w["jet"] + s * w["satellite"]), 3)

    if score >= 0.66:
        confidence = "high"
    elif score >= 0.33:
        confidence = "medium"
    else:
        confidence = "low"

    return ActivityScore(
        score=score,
        confidence=confidence,
        trend_component=round(t, 3),
        jet_component=j,
        satellite_component=round(s, 3) if satellite_available else None,
    )