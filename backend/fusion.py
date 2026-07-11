"""fusion.py — quantitative anomaly-detection fusion model (Nelson's piece).

Upgrade from pct-change heuristic to z-score anomaly detection:

    "Did activity increase?"  -->  "How unusual is this vs. historical behavior?"

    IMPORTS (supply anomaly)
            |
    SATELLITE (physical activity anomaly)
            |
    TRENDS (demand anomaly)
            v
    Weighted anomaly-magnitude fusion score
            v
    EDGAR validation (see validate_against_filings())

Each of imports/satellite/trends is scored as a SignalComponent: a magnitude
in [0, 1] ("how unusual") and a direction in {-1, 0, +1} ("which way").
Direction never reduces the score — a large unusual DECREASE (e.g. an import
collapse suggesting supply disruption) is just as important a signal as a
large unusual increase. Only magnitude feeds the fused score; direction is
carried through for narrative interpretation.

NOTE ON SATELLITE: z-score needs a real historical distribution (mean + std).
Satellite currently only has 2 points per store (before/after) — one prior
value can't produce a std, so z-score isn't meaningful here yet. Satellite
stays on direct pct-change-with-direction until Dominic's pipeline produces
more than 2 snapshots per site; the interface (SignalComponent, weight
redistribution) is otherwise identical so upgrading later is a one-function change.

Import this from routes/narrative.py and routes/score.py:
    from fusion import compute_activity_score
"""

from __future__ import annotations
import statistics
from dataclasses import dataclass, field

from schemas import TrendsResponse, ImportsResponse


# Default weights. Sum to 1.0. imports + satellite are physical evidence
# (0.80 combined); trends is demand-side confirmation (0.20).
DEFAULT_WEIGHTS = {"imports": 0.40, "satellite": 0.40, "trend": 0.20}


# ---------------------------------------------------------------------------
# 1. Z-score anomaly detection
# ---------------------------------------------------------------------------

def _zscore(values: list[float]) -> float | None:
    """Z-score of the most recent value against the historical distribution
    formed by everything before it.

        z = (current - historical_mean) / historical_stdev

    Returns None if there's insufficient history (need >= 3 prior points,
    i.e. 4 total) or the historical values have zero variance (a flat line
    has no meaningful "unusual" — std would be 0, division undefined).
    """
    if len(values) < 4:
        return None
    *historical, current = values
    mean = statistics.mean(historical)
    stdev = statistics.pstdev(historical)
    if stdev == 0:
        return None
    return (current - mean) / stdev


# ---------------------------------------------------------------------------
# 2. Z-score -> anomaly magnitude
# ---------------------------------------------------------------------------

def _zscore_to_anomaly(z: float) -> float:
    """Normalized anomaly magnitude in [0, 1]. Direction-agnostic on purpose —
    this answers 'how unusual', not 'good or bad'. z=0 -> 0.0, z=2 -> 0.4,
    z>=5 -> 1.0 (clamped)."""
    return _clamp01(abs(z) / 5)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# 3. Signal component: magnitude + preserved direction
# ---------------------------------------------------------------------------

@dataclass
class SignalComponent:
    magnitude: float  # 0.0-1.0, how unusual
    direction: int     # +1 unusual increase, -1 unusual decrease, 0 = normal/no data


def _signal_from_zscore(z: float | None) -> SignalComponent:
    if z is None:
        return SignalComponent(magnitude=0.0, direction=0)
    magnitude = round(_zscore_to_anomaly(z), 3)
    direction = 0 if magnitude == 0 else (1 if z > 0 else -1)
    return SignalComponent(magnitude=magnitude, direction=direction)


# ---------------------------------------------------------------------------
# 4. Component functions -> SignalComponent
# ---------------------------------------------------------------------------

def trend_component(trends: TrendsResponse) -> SignalComponent:
    """Z-score anomaly of the latest search-interest reading vs its own
    history. Returns a neutral SignalComponent if there's no usable data."""
    if not trends or not trends.points:
        return SignalComponent(0.0, 0)
    z = _zscore([p.interest for p in trends.points])
    return _signal_from_zscore(z)


def import_component(imports: ImportsResponse | None) -> SignalComponent:
    """Z-score anomaly of the latest inbound-container reading vs its own
    history. This is the supply-side leading indicator."""
    if imports is None or not imports.points:
        return SignalComponent(0.0, 0)
    z = _zscore([p.containers for p in imports.points])
    return _signal_from_zscore(z)


def satellite_component(count_change_pct: float | None) -> SignalComponent:
    """count_change_pct: (after_count - before_count) / before_count from
    Dominic's YOLO counts. NOT z-score (see module docstring) — only 2 data
    points exist per store today, so direction + magnitude are derived
    directly from the pct change instead."""
    if count_change_pct is None:
        return SignalComponent(0.0, 0)
    magnitude = round(_clamp01(abs(count_change_pct)), 3)
    direction = 0 if magnitude == 0 else (1 if count_change_pct > 0 else -1)
    return SignalComponent(magnitude=magnitude, direction=direction)


# ---------------------------------------------------------------------------
# 5 & 6. ActivityScore + fusion calculation
# ---------------------------------------------------------------------------

@dataclass
class ActivityScore:
    score: float                  # 0.0-1.0, anomaly MAGNITUDE only
    confidence: str                 # "low" | "medium" | "high"
    import_signal: SignalComponent
    satellite_signal: SignalComponent
    trend_signal: SignalComponent
    weights: dict                  # effective weights actually applied


def _effective_weights(available: set[str], weights: dict) -> dict:
    avail_total = sum(weights[k] for k in weights if k in available)
    if avail_total <= 0:
        return {k: 0.0 for k in weights}
    return {k: (weights[k] / avail_total if k in available else 0.0) for k in weights}


def compute_activity_score(
    trends: TrendsResponse,
    imports: ImportsResponse | None = None,
    satellite_count_change_pct: float | None = None,
    weights: dict | None = None,
) -> ActivityScore:
    weights = weights or DEFAULT_WEIGHTS

    available = {"trend"}  # trends always "in play" (magnitude 0 if empty)
    if imports is not None and imports.points:
        available.add("imports")
    if satellite_count_change_pct is not None:
        available.add("satellite")

    w = _effective_weights(available, weights)

    trend_sig = trend_component(trends)
    import_sig = import_component(imports) if "imports" in available else SignalComponent(0.0, 0)
    sat_sig = satellite_component(satellite_count_change_pct)

    # Magnitude only — direction NEVER reduces the score. A large unusual
    # decrease is just as important a finding as a large unusual increase.
    score = round(min(1.0, (
        import_sig.magnitude * w["imports"]
        + sat_sig.magnitude * w["satellite"]
        + trend_sig.magnitude * w["trend"]
    )), 3)

    confidence = "high" if score >= 0.66 else "medium" if score >= 0.33 else "low"

    return ActivityScore(
        score=score,
        confidence=confidence,
        import_signal=import_sig,
        satellite_signal=sat_sig,
        trend_signal=trend_sig,
        weights={k: round(v, 3) for k, v in w.items()},
    )


# ---------------------------------------------------------------------------
# 7. Signal interpretation
# ---------------------------------------------------------------------------

def interpret_direction(signal: SignalComponent) -> str:
    """Per-signal label. A = large positive, B = large negative, C = normal."""
    if signal.direction == 0 or signal.magnitude < 0.2:
        return "No significant anomaly"
    return "Unusual increase in activity" if signal.direction > 0 else "Unusual decrease in activity"


def interpret_combined(import_signal: SignalComponent, satellite_signal: SignalComponent) -> str:
    """Combined physical-evidence read (imports + satellite only — trends is
    demand-side confirmation, not physical evidence, so it's excluded here
    per the spec's example)."""
    directions = [s.direction for s in (import_signal, satellite_signal) if s.direction != 0]
    if not directions:
        return "No significant anomaly"
    if all(d > 0 for d in directions):
        return "Positive expansion signal detected"
    if all(d < 0 for d in directions):
        return "Potential contraction or supply disruption detected"
    return "Conflicting signals detected"


# ---------------------------------------------------------------------------
# 9. EDGAR validation support
# ---------------------------------------------------------------------------

def validate_against_filings(signal_date: str, filing_dates: list[str]) -> dict:
    """Answers: 'did a high anomaly score predict a future disclosure?'
    Checks whether any filing landed inside +1/+3/+7/+14 day windows after
    signal_date. Returns the tightest window that was hit, or None."""
    from datetime import date as _date
    d0 = _date.fromisoformat(signal_date)
    filings = sorted(_date.fromisoformat(f) for f in filing_dates)
    windows = [1, 3, 7, 14]
    hit_window = None
    lead_days = None
    for f in filings:
        delta = (f - d0).days
        if delta < 0:
            continue
        for w in windows:
            if delta <= w:
                hit_window = w
                lead_days = delta
                break
        if hit_window is not None:
            break
    return {
        "signal_date": signal_date,
        "hit_window_days": hit_window,   # e.g. 3 -> confirmed within Day+3
        "actual_lead_days": lead_days,
        "validated": hit_window is not None,
    }