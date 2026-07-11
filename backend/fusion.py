"""fusion.py — the real activity-score math (Nelson's piece).

The score models one funnel:

    IMPORTS (supply in)  ->  SATELLITE (activity)  ->  TRENDS (demand)

Container inflow leads on-the-ground activity, which leads consumer demand.
Each stage is a component in [0, 1]; the score is their weighted sum. Corporate
jets are NO LONGER scored — a CEO's jet is an M&A/intent signal on a different
axis, so it stays on the map as a secondary flag but does not move this number.

A component whose data isn't available yet (None) has its weight redistributed
proportionally across the components that ARE available, so partial data still
produces an honest score instead of an artificially low one.

Import this from routes/narrative.py and routes/score.py:
    from fusion import compute_activity_score
"""

from __future__ import annotations
from dataclasses import dataclass

from schemas import TrendsResponse, ImportsResponse


# Default weights. Sum to 1.0. imports + satellite are the physical evidence
# (0.70 combined); trends is the demand confirmation (0.30).
DEFAULT_WEIGHTS = {"imports": 0.35, "satellite": 0.35, "trend": 0.30}


def _effective_weights(available: set[str], weights: dict) -> dict:
    """Redistribute the weight of unavailable components proportionally across
    the available ones, so the returned weights always sum to 1.0 (unless
    nothing is available, in which case everything is 0)."""
    avail_total = sum(weights[k] for k in weights if k in available)
    if avail_total <= 0:
        return {k: 0.0 for k in weights}
    return {k: (weights[k] / avail_total if k in available else 0.0) for k in weights}


def _recent_vs_baseline(values: list[float]) -> float | None:
    """Shared metric: (recent - baseline) / baseline, using the last 2 buckets
    as 'recent' and everything before as 'baseline'. Returns None if there
    isn't enough data. Mirrors the split used by the trends spike detector so
    every signal is measured the same way."""
    if len(values) < 3:
        return None
    baseline = sum(values[:-2]) / (len(values) - 2)
    recent = sum(values[-2:]) / 2
    if baseline <= 0:
        return None
    return (recent - baseline) / baseline


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def trend_component(trends: TrendsResponse) -> float:
    """Recent-vs-baseline pct change in search interest, clamped to [0, 1].
    Returns 0.0 if there's no usable trend data, never raises."""
    pts = trends.points
    if not pts:
        return 0.0
    if len(pts) < 3:
        baseline = pts[0].interest or 1
        recent = pts[-1].interest
        pct = (recent - baseline) / baseline if baseline > 0 else 0.0
    else:
        pct = _recent_vs_baseline([p.interest for p in pts]) or 0.0
    return _clamp01(pct)


def import_component(imports: ImportsResponse) -> float:
    """Recent-vs-baseline pct change in inbound container volume, clamped to
    [0, 1]. This is the supply-side leading indicator."""
    if imports is None or not imports.points:
        return 0.0
    pct = _recent_vs_baseline([p.containers for p in imports.points])
    return _clamp01(pct) if pct is not None else 0.0


def satellite_component(count_change_pct: float | None) -> float:
    """count_change_pct: (after_count - before_count) / before_count, from
    Dominic's YOLO car counts. None means 'not available yet'."""
    if count_change_pct is None:
        return 0.0
    return _clamp01(count_change_pct)


@dataclass
class ActivityScore:
    score: float           # 0.0 - 1.0
    confidence: str         # "low" | "medium" | "high"
    import_component: float | None      # None = not available
    satellite_component: float | None   # None = not available
    trend_component: float
    weights: dict           # effective weights actually applied


def compute_activity_score(
    trends: TrendsResponse,
    imports: ImportsResponse | None = None,
    satellite_count_change_pct: float | None = None,
    weights: dict | None = None,
) -> ActivityScore:
    weights = weights or DEFAULT_WEIGHTS

    available = {"trend"}  # trends is always in play (0.0 if empty)
    if imports is not None and imports.points:
        available.add("imports")
    if satellite_count_change_pct is not None:
        available.add("satellite")

    w = _effective_weights(available, weights)

    t = trend_component(trends)
    i = import_component(imports) if "imports" in available else 0.0
    s = satellite_component(satellite_count_change_pct)

    score = round(min(1.0, i * w["imports"] + s * w["satellite"] + t * w["trend"]), 3)

    if score >= 0.66:
        confidence = "high"
    elif score >= 0.33:
        confidence = "medium"
    else:
        confidence = "low"

    return ActivityScore(
        score=score,
        confidence=confidence,
        import_component=round(i, 3) if "imports" in available else None,
        satellite_component=round(s, 3) if "satellite" in available else None,
        trend_component=round(t, 3),
        weights={k: round(v, 3) for k, v in w.items()},
    )
