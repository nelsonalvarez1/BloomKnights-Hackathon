"""/api/narrative — assembles the fused signal payload and triggers the Gemini call.

The thesis tells one story: supply (imports) leads on-the-ground activity
(satellite car counts) leads consumer demand (search trends); we fuse those
into an activity score, and SEC EDGAR confirms it days later — the lead time
is the edge.

If GEMINI_API_KEY is set, the thesis comes from Gemini. If not (local dev, or
the API dies on stage), it falls back to a deterministic template built from
the same real payload — the demo never hard-fails.
"""

import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException

from database import get_conn
from routes.edgar import get_edgar
from routes.imports import get_imports
from routes.satellite import get_satellite
from routes.supply import get_supply
from routes.trends import get_trends
from schemas import NarrativeRequest, NarrativeResponse
from fusion import compute_activity_score, interpret_combined

router = APIRouter()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

PROMPT_TEMPLATE = """You are a senior alt-data analyst at a quantitative hedge fund writing an
institutional investment-signal note for the investment committee. Use ONLY the
data below — never invent facts. Cite specific numbers and dates for every claim.
The core narrative is one causal funnel: SUPPLY (imports) leads on-the-ground
ACTIVITY (satellite parking counts) leads consumer DEMAND (search), which drives
REVENUE and EARNINGS, and SEC EDGAR confirms it later — the lead time is the edge.

Write in tight, confident desk prose. Reason about the RELATIONSHIPS between
signals, do not just restate them. Use exactly these labeled sections, each 1-3
sentences, separated by blank lines:

Investment Thesis — the one-line call and why the edge exists.
Evidence Summary — the strongest quantified signals, in funnel order.
Signal Breakdown — supply, activity, and demand each read individually.
Contradictory Evidence — anything cutting against the thesis (or "none material").
Risk Factors — what would invalidate the call.
Expected Catalyst — the EDGAR filing / earnings event and its timing.
Bull Case / Bear Case — the asymmetry.
Recommendation — STRONG BUY / BUY / HOLD / REDUCE / AVOID, with the confidence
level (low/medium/high) and why.

Store: {store_name} ({company}, {ticker}) — {city}, {state}
Fused activity score: {score} of 1.0 ({confidence} confidence)

SUPPLY — US customs imports (consignee {consignee}, supplier {supplier}, {origin_country}):
- Monthly inbound containers: {import_tail}
- Surge vs. baseline: {import_surge}

ACTIVITY — Satellite parking-lot vehicle counts (NAIP imagery, YOLOv8):
- Before ({before_date}): {before_cars} cars
- After ({after_date}): {after_cars} cars ({count_change})

DEMAND — Google Search Trends ("{query}", {region}):
- Recent weekly interest: {trend_tail}
- Spike detected: {spike}

SUPPLY DETAIL — Latest inbound shipment (customs/port record):
{supply_lines}

VALIDATION — SEC EDGAR:

- Our combined signal fired: {signal_date} (day 0)
- Filings after signal: {filing_lines}
- Lead time: {lead_days} days ahead of the first filing
"""


def _build_payload(store_id: int) -> dict:
    conn = get_conn()
    try:
        store = conn.execute(
            "SELECT * FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
    finally:
        conn.close()
    if store is None:
        raise HTTPException(404, f"Unknown store {store_id}")

    try:
        supply = get_supply(store_id)
    except HTTPException:
        supply = None  # supply data is optional; the thesis still works without it

    return {
        "store": dict(store),
        "imports": get_imports(store_id),
        "satellite": get_satellite(store_id),
        "trends": get_trends(store_id),
        "supply": supply,
        "edgar": get_edgar(store_id),
    }


def _score(p: dict):
    return compute_activity_score(
        trends=p["trends"],
        imports=p["imports"],
        satellite_count_change_pct=p["satellite"].count_change_pct,
    )


def _pct(x: float) -> str:
    return f"{'+' if x >= 0 else ''}{round(x * 100)}%"


def _render_prompt(p: dict) -> str:
    imp, sat, trends, edgar = (
        p["imports"], p["satellite"], p["trends"], p["edgar"]
    )
    score = _score(p)
    filing_lines = "; ".join(f"{f.form_type} on {f.filed_at}" for f in edgar.filings)
    trend_tail = ", ".join(f"{pt.date}: {pt.interest}" for pt in trends.points[-4:])
    import_tail = ", ".join(f"{pt.month}: {pt.containers}" for pt in imp.points[-4:])
    import_surge = (
        f"{_pct(imp.surge_pct)} ({'surge' if imp.surge_detected else 'no surge'})"
        if imp.surge_pct is not None else "n/a"
    )
    supply = p["supply"]
    if supply is not None:
        inventory = ", ".join(f"{i.item}: {i.containers} containers" for i in supply.items)
        supply_lines = (
            f"- {supply.ship_name} ({supply.carrier}) arrived {supply.arrived_at} "
            f"at {supply.port}\n- On board: {inventory} "
            f"({supply.total_containers} containers total)"
        )
    else:
        supply_lines = "- No shipment data in window"
    return PROMPT_TEMPLATE.format(
        store_name=p["store"]["name"], company=p["store"]["company"],
        ticker=p["store"]["ticker"], city=p["store"]["city"], state=p["store"]["state"],
        score=score.score, confidence=score.confidence,
        consignee=imp.consignee, supplier=imp.supplier, origin_country=imp.origin_country,
        import_tail=import_tail, import_surge=import_surge,
        before_date=sat.before.captured_at, after_date=sat.after.captured_at,
        before_cars=sat.before.car_count, after_cars=sat.after.car_count,
        count_change=f"{_pct(sat.count_change_pct)} vehicles",
        query=trends.query, region=trends.region,
        trend_tail=trend_tail, spike=trends.spike_detected,
        supply_lines=supply_lines, signal_date=edgar.signal_date,
        filing_lines=filing_lines, lead_days=edgar.lead_days,
    )


def _fallback_thesis(p: dict) -> str:
    """Deterministic institutional note built from the same real payload Gemini
    would see. Reads as a sectioned desk note so the demo never depends on an
    external key. Sections mirror PROMPT_TEMPLATE."""
    imp, sat, trends, edgar = p["imports"], p["satellite"], p["trends"], p["edgar"]
    store = p["store"]
    score = _score(p)

    # Directional conviction — weighted physical + demand vote, matching the
    # frontend fusion engine. Physical evidence (imports+satellite) dominates.
    conv = (
        0.40 * score.satellite_signal.direction * score.satellite_signal.magnitude
        + 0.35 * score.import_signal.direction * score.import_signal.magnitude
        + 0.25 * score.trend_signal.direction * score.trend_signal.magnitude
    )
    if conv > 0.45:
        rec = "STRONG BUY"
    elif conv > 0.15:
        rec = "BUY"
    elif conv > -0.15:
        rec = "HOLD"
    elif conv > -0.45:
        rec = "REDUCE"
    else:
        rec = "AVOID"

    combined = interpret_combined(score.import_signal, score.satellite_signal)
    sat_move = _pct(sat.count_change_pct)
    peak_interest = max(pt.interest for pt in trends.points) if trends.points else 0

    supply_read = (
        f"{imp.consignee} pulled {imp.points[-1].containers} inbound containers in "
        f"{imp.points[-1].month} from {imp.supplier} ({imp.origin_country}), "
        f"{_pct(imp.surge_pct) if imp.surge_pct is not None else 'flat'} vs. baseline"
        + (" — a genuine restock ahead of a ramp." if imp.surge_detected
           else " — supply is not confirming a ramp.")
    )
    activity_read = (
        f"Satellite counts at {store['name']} moved {sat.before.car_count}→"
        f"{sat.after.car_count} vehicles ({sat_move}) between {sat.before.captured_at} "
        f"and {sat.after.captured_at}."
    )
    demand_read = (
        f'Search interest for "{trends.query}" ({trends.region}) '
        + (f"spiked to {peak_interest} around {trends.spike_date}, corroborating the move."
           if trends.spike_detected
           else f"peaked at {peak_interest} with no fresh spike, so demand only partially confirms.")
    )

    # Contradiction check — do any signals disagree with the majority?
    dirs = [s.direction for s in (score.import_signal, score.satellite_signal, score.trend_signal) if s.direction]
    disagreeing = dirs and not (all(d > 0 for d in dirs) or all(d < 0 for d in dirs))

    bullish = conv >= 0
    sections = [
        f"Investment Thesis — {rec} on {store['company']} ({store['ticker']}). "
        f"Fused activity score {score.score}/1.0 at {score.confidence} confidence; "
        f"{combined.lower()}. The edge is timing: the alt-data funnel resolved "
        f"~{edgar.lead_days} days before SEC confirmation.",

        f"Evidence Summary — {supply_read} {activity_read} {demand_read}",

        f"Signal Breakdown — Supply anomaly {score.import_signal.magnitude:.2f} "
        f"({_dir_word(score.import_signal.direction)}); "
        f"physical activity {score.satellite_signal.magnitude:.2f} "
        f"({_dir_word(score.satellite_signal.direction)}); "
        f"demand {score.trend_signal.magnitude:.2f} "
        f"({_dir_word(score.trend_signal.direction)}).",

        "Contradictory Evidence — " + (
            "signals diverge; physical and demand reads point different ways, which "
            "caps conviction until they reconcile." if disagreeing
            else "none material — supply, activity, and demand all point the same way."),

        "Risk Factors — the thesis breaks if the import surge reflects one-off "
        "channel stuffing rather than sell-through, or if the satellite delta is "
        "seasonal. EDGAR non-confirmation inside the window would invalidate the lead-time claim.",

        f"Expected Catalyst — first related filing ({edgar.filings[0].form_type}) landed "
        f"{edgar.lead_days} days after our signal fired on {edgar.signal_date}; the next "
        f"earnings print is the settle-up event.",

        "Bull Case / Bear Case — " + (
            f"bull: the restock feeds a beat the Street hasn't modeled. "
            f"bear: demand cools and inventory becomes a markdown risk."
            if bullish else
            f"bull: the pullback is transitory and mean-reverts. "
            f"bear: soft supply and fading search foreshadow a miss."),

        f"Recommendation — {rec}, {score.confidence} confidence. "
        + (f"Physical evidence and demand align behind the call."
           if not disagreeing else
           "Conviction tempered by conflicting signals; size accordingly."),
    ]
    return "\n\n".join(sections)


def _dir_word(direction: int) -> str:
    return "rising" if direction > 0 else "falling" if direction < 0 else "flat"


def _call_gemini(prompt: str, api_key: str) -> str:
    resp = httpx.post(
        GEMINI_URL.format(model=GEMINI_MODEL),
        headers={"x-goog-api-key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


@router.post("/api/narrative", response_model=NarrativeResponse)
def generate_narrative(req: NarrativeRequest):
    payload = _build_payload(req.store_id)

    # Sources in funnel order; edgar always closes as the validation layer.
    sources = []
    if payload["imports"].points:
        sources.append("imports")
    sources.append("satellite")
    if payload["trends"].points:
        sources.append("trends")
    if payload["supply"] is not None:
        sources.append("supply")
    sources.append("edgar")  # validation layer — the thesis always closes on it

    api_key = os.environ.get("GEMINI_API_KEY")
    thesis = None
    if api_key:
        try:
            thesis = _call_gemini(_render_prompt(payload), api_key)
        except (httpx.HTTPError, KeyError, IndexError):
            thesis = None  # fall through to the template — never 500 on stage
    if thesis is None:
        thesis = _fallback_thesis(payload)

    return NarrativeResponse(
        store_id=req.store_id,
        thesis=thesis,
        confidence=_score(payload).confidence,
        generated_at=datetime.now(timezone.utc).isoformat(),
        sources=sources,
    )
