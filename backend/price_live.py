"""Live Finnhub client — real-time stock quote for the price-context panel.

Finnhub's /quote endpoint is free (needs FINNHUB_API_KEY, free tier). It gives
the CURRENT price, change, and previous close — the "what's the market doing"
context that sits beside the signal. Historical daily candles are a Finnhub
premium feature, so the overlay chart's history is seeded (see routes/price.py);
only the live current quote comes from here.

routes/price.py calls fetch_quote() and falls back to the seeded last close if
there's no key or the network fails, so the panel always renders.
"""

import os

import httpx

FINNHUB_URL = "https://finnhub.io/api/v1/quote"


def fetch_quote(ticker: str) -> dict:
    """Return {current, change, percent_change, prev_close} from Finnhub.

    Raises if FINNHUB_API_KEY is unset or the request fails, so the caller can
    fall back to cached values.
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        raise RuntimeError("FINNHUB_API_KEY not set")

    resp = httpx.get(
        FINNHUB_URL, params={"symbol": ticker, "token": api_key}, timeout=10
    )
    resp.raise_for_status()
    q = resp.json()
    # Finnhub: c=current, d=change, dp=percent change, pc=previous close.
    if not q.get("c"):
        raise RuntimeError(f"Finnhub returned no price for {ticker}")
    return {
        "current": round(float(q["c"]), 2),
        "change": round(float(q.get("d") or 0.0), 2),
        "percent_change": round(float(q.get("dp") or 0.0), 2),
        "prev_close": round(float(q.get("pc") or q["c"]), 2),
    }
