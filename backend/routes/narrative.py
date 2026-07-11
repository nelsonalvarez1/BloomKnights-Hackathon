"""/api/narrative — assembles the fused signal payload and triggers the Gemini call.

If GEMINI_API_KEY is set, the thesis comes from Gemini. If not (local dev,
or the API dies on stage), it falls back to a deterministic template built
from the same real payload — the demo never hard-fails.
"""

import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException

from database import get_conn
from routes.edgar import get_edgar
from routes.jets import get_jets
from routes.satellite import get_satellite
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
and dates. 3 short paragraphs max. State a confidence level (low/medium/high) and
why. Do not invent facts not present in the payload.

Store: {store_name} ({company}, {ticker}) — {city}, {state}

Satellite imagery (before/after capture of the site):
- Before: {before_date}
- After: {after_date}

Google Search Trends ("{query}", {region}):
- Recent weekly interest: {trend_tail}
- Spike detected: {spike}

Corporate jet activity (ADS-B):
{jet_lines}

SEC EDGAR:
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

    return {
        "store": dict(store),
        "satellite": get_satellite(store_id),
        "trends": get_trends(store_id),
        "jets": get_jets(store_id),
        "edgar": get_edgar(store_id),
    }


def _render_prompt(p: dict) -> str:
    sat, trends, jets, edgar = p["satellite"], p["trends"], p["jets"], p["edgar"]
    jet_lines = "\n".join(
        f"- {e.tail_number} ({e.operator}) {e.event_type} at {e.airport}, "
        f"{e.distance_miles} mi from store, {e.timestamp}"
        for e in jets.events
    ) or "- No jet activity in window"
    filing_lines = "; ".join(f"{f.form_type} on {f.filed_at}" for f in edgar.filings)
    trend_tail = ", ".join(
        f"{pt.date}: {pt.interest}" for pt in trends.points[-4:]
    )
    return PROMPT_TEMPLATE.format(
        store_name=p["store"]["name"], company=p["store"]["company"],
        ticker=p["store"]["ticker"], city=p["store"]["city"], state=p["store"]["state"],
        before_date=sat.before.captured_at, after_date=sat.after.captured_at,
        query=trends.query, region=trends.region,
        trend_tail=trend_tail, spike=trends.spike_detected,
        jet_lines=jet_lines, signal_date=edgar.signal_date,
        filing_lines=filing_lines, lead_days=edgar.lead_days,
    )


def _confidence(p: dict) -> str:
    return compute_activity_score(p["trends"], p["jets"]).confidence


def _fallback_thesis(p: dict) -> str:
    sat, trends, jets, edgar = p["satellite"], p["trends"], p["jets"], p["edgar"]
    store = p["store"]
    parts = [
        f"Satellite imagery of {store['name']} ({store['ticker']}) captures the site on "
        f"{sat.before.captured_at} and again on {sat.after.captured_at}, giving a visual "
        f"before/after of on-the-ground activity at the location."
    ]
    if trends.spike_detected:
        parts.append(
            f'Google search interest for "{trends.query}" ({trends.region}) spiked to '
            f"{max(pt.interest for pt in trends.points)} around {trends.spike_date}, "
            f"corroborating the physical signal with demand-side attention."
        )
    else:
        parts.append(
            f'Google search interest for "{trends.query}" shows no corroborating spike, '
            f"which caps conviction on the physical signal."
        )
    if jets.proximity_flag:
        e = jets.events[0]
        parts.append(
            f"Corporate aviation adds an intent signal: {e.tail_number} ({e.operator}) "
            f"logged a {e.event_type} at {e.airport}, {e.distance_miles} miles from the "
            f"site, on {e.timestamp[:10]}."
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

    sources = ["satellite", "edgar"]
    if payload["trends"].points:
        sources.insert(1, "trends")
    if payload["jets"].events:
        sources.insert(-1, "jets")

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
        confidence=_confidence(payload),
        generated_at=datetime.now(timezone.utc).isoformat(),
        sources=sources,
    )
