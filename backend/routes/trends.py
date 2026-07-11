"""/api/trends — serves Google Search Trends data for a store (Sally's pull).

Spike detection: latest 2-week average vs the trailing baseline. Simple on
purpose — say "recent interest vs baseline" in the demo, nothing fancier.
"""

from fastapi import APIRouter, HTTPException

from database import get_conn
from schemas import TrendPoint, TrendsResponse

router = APIRouter()

SPIKE_RATIO = 1.5  # recent average must be 1.5x baseline to count as a spike


@router.get("/api/trends", response_model=TrendsResponse)
def get_trends(store_id: int):
    conn = get_conn()
    try:
        meta = conn.execute(
            "SELECT query, region FROM trend_meta WHERE store_id = ?", (store_id,)
        ).fetchone()
        rows = conn.execute(
            "SELECT date, interest FROM trend_points WHERE store_id = ? ORDER BY date",
            (store_id,),
        ).fetchall()
    finally:
        conn.close()

    if meta is None or not rows:
        raise HTTPException(404, f"No trends data for store {store_id}")

    points = [TrendPoint(date=r["date"], interest=r["interest"]) for r in rows]

    spike_detected, spike_date = False, None
    if len(points) >= 6:
        baseline = sum(p.interest for p in points[:-2]) / (len(points) - 2)
        recent = sum(p.interest for p in points[-2:]) / 2
        if baseline > 0 and recent / baseline >= SPIKE_RATIO:
            spike_detected = True
            spike_date = max(points[-2:], key=lambda p: p.interest).date

    return TrendsResponse(
        store_id=store_id,
        query=meta["query"],
        region=meta["region"],
        points=points,
        spike_detected=spike_detected,
        spike_date=spike_date,
    )
