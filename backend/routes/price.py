"""/api/price — the stock the signal is about, for the market-context overlay.

LIVE current quote from Finnhub (price_live.py); the daily history is the
cached move across the signal/filing window so the timeline can overlay "what
the stock did after we flagged it." Live-first with a seeded fallback, same
pattern as /api/edgar: `source` says which path served the current quote.

The seeded history is illustrative pre-market context — the run-up (or drop)
around each company's real 8-K. Current quote overrides the latest point when
Finnhub is reachable.
"""

import price_live
from fastapi import APIRouter, HTTPException

from database import get_conn
from schemas import PricePoint, PriceResponse

router = APIRouter()

# Cached daily closes spanning the signal -> filing -> reaction window. WMT/HD
# ran up after their 8-Ks; TGT drifted down (matches the bearish signal).
PRICE_HISTORY = {
    "WMT": [("2026-05-01", 98.4), ("2026-05-08", 99.1), ("2026-05-15", 101.7),
            ("2026-05-22", 104.9), ("2026-05-29", 106.2), ("2026-06-05", 108.0),
            ("2026-06-15", 109.4), ("2026-06-26", 111.2), ("2026-07-06", 112.6)],
    "HD":  [("2026-05-01", 404.0), ("2026-05-08", 406.5), ("2026-05-15", 411.0),
            ("2026-05-22", 418.3), ("2026-05-29", 421.0), ("2026-06-05", 425.7),
            ("2026-06-15", 429.1), ("2026-06-26", 434.8), ("2026-07-06", 438.9)],
    "TGT": [("2026-05-01", 158.2), ("2026-05-08", 157.0), ("2026-05-15", 154.1),
            ("2026-05-22", 150.6), ("2026-05-29", 148.0), ("2026-06-05", 145.2),
            ("2026-06-15", 142.7), ("2026-06-26", 140.0), ("2026-07-06", 138.3)],
}


@router.get("/api/price", response_model=PriceResponse)
def get_price(store_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT ticker FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, f"Unknown store {store_id}")

    ticker = row["ticker"]
    hist = PRICE_HISTORY.get(ticker, [])
    history = [PricePoint(date=d, close=c) for d, c in hist]
    last_close = hist[-1][1] if hist else 0.0
    prev_close = hist[-2][1] if len(hist) >= 2 else last_close

    # Live-first: real current quote from Finnhub, else fall back to the last
    # seeded close so the panel always renders.
    source = "cached"
    current = last_close
    change = round(last_close - prev_close, 2)
    percent_change = round((change / prev_close * 100) if prev_close else 0.0, 2)
    try:
        q = price_live.fetch_quote(ticker)
        current = q["current"]
        change = q["change"]
        percent_change = q["percent_change"]
        prev_close = q["prev_close"]
        source = "live"
        if history:
            history[-1].close = current  # anchor the chart to the live price
    except Exception:
        pass

    return PriceResponse(
        store_id=store_id,
        ticker=ticker,
        current=current,
        change=change,
        percent_change=percent_change,
        prev_close=prev_close,
        history=history,
        source=source,
    )
