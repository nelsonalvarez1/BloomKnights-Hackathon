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
from routes.jets import get_jets
from routes.satellite import get_satellite
from routes.supply import get_supply
from routes.trends import get_trends
from schemas import NarrativeRequest, NarrativeResponse
from fusion import compute_activity_score

router = APIRouter()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

PROMPT_TEMPLATE = """You are an alt-data analyst writing a short investment-signal thesis.
Use ONLY the data below. Cite each signal type you use. Be specific with numbers
and dates. Tell it as one funnel: SUPPLY (imports) leads on-the-ground ACTIVITY
(satellite) leads consumer DEMAND (search), then EDGAR confirms it later. 3 short
paragraphs max. State the confidence level (low/medium/high) and why. Do not
invent facts not present in the payload.

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

SECONDARY — Corporate jet activity (insider-intent flag, not part of the score):
{jet_lines}


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
        "jets": get_jets(store_id),
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
    imp, sat, trends, jets, edgar = (
        p["imports"], p["satellite"], p["trends"], p["jets"], p["edgar"]
    )
    score = _score(p)
    jet_lines = "\n".join(
        f"- {e.tail_number} ({e.operator}) {e.event_type} at {e.airport}, "
        f"{e.distance_miles} mi from store, {e.timestamp}"
        for e in jets.events
    ) or "- No jet activity in window"
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
        jet_lines=jet_lines, supply_lines=supply_lines, signal_date=edgar.signal_date,
        filing_lines=filing_lines, lead_days=edgar.lead_days,
    )


def _fallback_thesis(p: dict) -> str:
    imp, sat, trends, jets, edgar = (
        p["imports"], p["satellite"], p["trends"], p["jets"], p["edgar"]
    )
    store = p["store"]
    parts = []

    if imp.surge_detected:
        parts.append(
            f"Supply first: {imp.consignee} pulled in {imp.points[-1].containers} inbound "
            f"containers in {imp.points[-1].month} from {imp.supplier} ({imp.origin_country}), "
            f"{_pct(imp.surge_pct)} above baseline — inventory building ahead of a ramp."
        )
    else:
        parts.append(
            f"Customs imports for {imp.consignee} show no supply surge "
            f"({_pct(imp.surge_pct) if imp.surge_pct is not None else 'flat'} vs. baseline), "
            f"which caps conviction on the physical signal."
        )

    parts.append(
        f"That shows up on the ground: satellite counts of {store['name']} ({store['ticker']}) "
        f"went from {sat.before.car_count} cars on {sat.before.captured_at} to "
        f"{sat.after.car_count} on {sat.after.captured_at} — {_pct(sat.count_change_pct)} "
        f"vehicles in the lot."
    )

    if trends.spike_detected:
        parts.append(
            f'Demand confirms it: Google interest for "{trends.query}" ({trends.region}) '
            f"spiked to {max(pt.interest for pt in trends.points)} around {trends.spike_date}."
        )
    else:
        parts.append(
            f'Google interest for "{trends.query}" shows no corroborating spike, '
            f"so the read leans on the supply and activity signals."
        )

    if jets.proximity_flag:
        e = jets.events[0]
        parts.append(
            f"Secondary intent flag: {e.tail_number} ({e.operator}) logged a {e.event_type} "
            f"at {e.airport}, {e.distance_miles} mi from the site, on {e.timestamp[:10]}."
        )

    supply = p["supply"]
    if supply is not None:
        parts.append(
            f"On the supply side, {supply.ship_name} ({supply.carrier}) docked at "
            f"{supply.port} on {supply.arrived_at} carrying {supply.total_containers} "
            f"containers for the retailer — inbound inventory consistent with the "
            f"activity the other signals show."
        )
    parts.append(
        f"The combined signal fired on {edgar.signal_date}; the first related filing "
        f"({edgar.filings[0].form_type}) hit EDGAR {edgar.lead_days} days later — the "
        f"market's first official confirmation of what the signals already showed."
    )
    return "\n\n".join(parts)


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

    # Sources in funnel order; jets only if there was activity (secondary).
    sources = []
    if payload["imports"].points:
        sources.append("imports")
    sources.append("satellite")
    if payload["trends"].points:
        sources.append("trends")
    if payload["jets"].events:
        sources.insert(-1, "jets")
    if payload["supply"] is not None:
        sources.insert(-1, "supply")


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
