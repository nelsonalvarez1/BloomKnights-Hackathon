"""/api/edgar — the filing timeline and the filing-lag calculation.

lead_days (signal day 0 -> first filing) is the money-shot number the whole
demo builds to.
"""

from datetime import date

from fastapi import APIRouter, HTTPException

from database import get_conn
from schemas import EdgarResponse, Filing

router = APIRouter()


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
        rows = conn.execute(
            "SELECT form_type, filed_at, url, description FROM filings"
            " WHERE store_id = ? ORDER BY filed_at",
            (store_id,),
        ).fetchall()
    finally:
        conn.close()

    if store is None or signal is None or not rows:
        raise HTTPException(404, f"No EDGAR data for store {store_id}")

    filings = [Filing(**dict(r)) for r in rows]
    signal_date = signal["signal_date"]
    first_filed = date.fromisoformat(filings[0].filed_at)
    lead_days = (first_filed - date.fromisoformat(signal_date)).days

    return EdgarResponse(
        store_id=store_id,
        company=store["company"],
        cik=store["cik"],
        signal_date=signal_date,
        filings=filings,
        lead_days=lead_days,
    )
