"""finnhub.py — live quote lookup, gated by the fusion activity score.

Per the architecture: yfinance gives a ONE-TIME cached baseline for all ~25
tickers; Finnhub gives a LIVE quote, but only for names the fusion layer
flags as "active" right now. That gating is the whole point of this file —
it exists to avoid burning API calls (and hitting free-tier rate limits) on
tickers with nothing going on.

Env var needed (add to render.yaml alongside GEMINI_API_KEY):
    FINNHUB_API_KEY

Free tier is ~60 calls/minute — comfortably enough for a handful of flagged
tickers, NOT enough to poll all 25 on a loop. Don't call get_live_quote()
in a loop over every company; call is_active() first and only fetch for
the ones that pass.

Usage from wherever the leaderboard/narrative assembles a company's data:
    from fusion import compute_activity_score
    from finnhub_client import is_active, get_live_quote

    score = compute_activity_score(trends, imports, satellite_pct)
    quote = get_live_quote(ticker) if is_active(score) else None
"""

from __future__ import annotations
import os
import httpx

from fusion import ActivityScore

FINNHUB_URL = "https://finnhub.io/api/v1/quote"

# Matches fusion.py's own high-confidence cutoff (score >= 0.66) — an
# "active" company for Finnhub purposes is one fusion already calls "high
# confidence". Keeping these in sync means you're not inventing a second,
# separate threshold that could quietly drift from the one you already
# tuned and tested.
ACTIVE_THRESHOLD = 0.66


def is_active(score: ActivityScore) -> bool:
    """True if this company's fused signal is strong enough to justify
    spending a live API call on it."""
    return score.score >= ACTIVE_THRESHOLD


def get_live_quote(ticker: str) -> dict | None:
    """Fetch a live quote for one ticker. Returns None (never raises) if
    the API key is missing or the request fails — same 'never hard-fail
    on stage' pattern as narrative.py's Gemini call.

    Response shape (subset of Finnhub's real fields):
        {
            "current_price": float,
            "change": float,
            "percent_change": float,
            "high": float,
            "low": float,
            "open": float,
            "previous_close": float,
        }
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        return None

    try:
        resp = httpx.get(
            FINNHUB_URL,
            params={"symbol": ticker, "token": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    # Finnhub returns all zeros for an invalid/unrecognized symbol instead
    # of an error status -- treat that as "no data" rather than a real quote.
    if data.get("c") in (None, 0):
        return None

    return {
        "current_price": data.get("c"),
        "change": data.get("d"),
        "percent_change": data.get("dp"),
        "high": data.get("h"),
        "low": data.get("l"),
        "open": data.get("o"),
        "previous_close": data.get("pc"),
    }