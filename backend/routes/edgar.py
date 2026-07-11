"""/api/edgar — the filing timeline and the filing-lag calculation.

LIVE-FIRST: on each request we pull the company's real filings from
data.sec.gov (edgar_live.py) and measure lead time against our signal date.
If the network fails, we fall back to the seeded rows so the demo never
breaks. `source` in the response says which path served it ("live"/"cached").

lead_days (signal day 0 -> first filing) is the money-shot number the whole
demo builds to.
"""

from datetime import date

from fastapi import APIRouter, HTTPException

import edgar_live
from database import get_conn
from schemas import EdgarResponse, Filing

router = APIRouter()


def _cached_filings(store_id: int, conn) -> list[Filing]:
    rows = conn.execute(
        "SELECT form_type, filed_at, url, description FROM filings"
        " WHERE store_id = ? ORDER BY filed_at",
        (store_id,),
    ).fetchall()
    return [Filing(**dict(r)) for r in rows]


@router.get("/api/edgar", response_model=EdgarResponse)
def get_edgar(store_id: int):
    conn = get_conn()
    try:
        store = conn.execute(
            "SELECT company, cik FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
        signal = conn.execute(
            "SELECT signal_date FROM signals WHERE store_id = ?", (store_id,)
        ).fetchone()
        cached = _cached_filings(store_id, conn)
    finally:
        conn.close()

    if store is None or signal is None:
        raise HTTPException(404, f"No EDGAR data for store {store_id}")

    signal_date = signal["signal_date"]

    # Live-first: real filings on/after the signal date, straight from SEC.
    source = "cached"
    filings = cached
    try:
        live = edgar_live.fetch_live_filings(store["cik"], since=signal_date)
        if live:
            filings = [Filing(**f) for f in live]
            source = "live"
    except Exception:
        pass  # network/parse hiccup -> keep the cached rows, never 500 on stage

    if not filings:
        raise HTTPException(404, f"No EDGAR filings for store {store_id}")

    # Anchor lead time to the first MATERIAL filing (8-K/10-Q/10-K) — an actual
    # corporate event — rather than the constant Form 4 insider-trade drip.
    material = [f for f in filings if f.form_type in ("8-K", "10-Q", "10-K")]
    anchor = material[0] if material else filings[0]
    lead_days = (date.fromisoformat(anchor.filed_at)
                 - date.fromisoformat(signal_date)).days

    return EdgarResponse(
        store_id=store_id,
        company=store["company"],
        cik=store["cik"],
        signal_date=signal_date,
        filings=filings,
        lead_days=lead_days,
        source=source,
    )
