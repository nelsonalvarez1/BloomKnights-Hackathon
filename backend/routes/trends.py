"""/api/trends — Google Search Trends for a store (Sally's pull).

LIVE-FIRST: pulls the interest series from Google Trends (trends_live.py) on
each request, falling back to the seeded weekly series if pytrends rate-limits
or errors. `source` says which path served it. Set PERIGEE_TRENDS_CACHED=1 to
pin to the seed (a controlled trend shape for a scripted demo).

Spike detection: latest 2-bucket average vs the trailing baseline — say
"recent interest vs baseline" in the demo, nothing fancier.
"""

import os

from fastapi import APIRouter, HTTPException

import trends_live
from database import get_conn
from schemas import TrendPoint, TrendsResponse
from synth import synth_trends

router = APIRouter()

SPIKE_RATIO = 1.5  # recent average must be 1.5x baseline to count as a spike


def _detect_spike(points: list[TrendPoint]) -> tuple[bool, str | None]:
    if len(points) < 6:
        return False, None
    baseline = sum(p.interest for p in points[:-2]) / (len(points) - 2)
    recent = sum(p.interest for p in points[-2:]) / 2
    if baseline > 0 and recent / baseline >= SPIKE_RATIO:
        return True, max(points[-2:], key=lambda p: p.interest).date
    return False, None


@router.get("/api/trends", response_model=TrendsResponse)
def get_trends(store_id: int):
    conn = get_conn()
    try:
        store = conn.execute(
            "SELECT company, ticker FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
        meta = conn.execute(
            "SELECT query, region FROM trend_meta WHERE store_id = ?", (store_id,)
        ).fetchone()
        rows = conn.execute(
            "SELECT date, interest FROM trend_points WHERE store_id = ? ORDER BY date",
            (store_id,),
        ).fetchall()
    finally:
        conn.close()

    if store is None:
        raise HTTPException(404, f"Unknown store {store_id}")

    # No seeded series (any company past the 3 hero stores) -> synthesize a
    # stable, company-aligned series so the panel always loads instantly.
    if meta is None or not rows:
        query, region, syn = synth_trends(store_id, store["ticker"], store["company"])
        points = [TrendPoint(date=d, interest=v) for d, v in syn]
        spike_detected, spike_date = _detect_spike(points)
        return TrendsResponse(
            store_id=store_id, query=query, region=region, points=points,
            spike_detected=spike_detected, spike_date=spike_date, source="modeled",
        )

    query, region = meta["query"], meta["region"]

    # Live-first: real interest-over-time from Google Trends, else the seed.
    source = "cached"
    points = [TrendPoint(date=r["date"], interest=r["interest"]) for r in rows]
    if not os.environ.get("PERIGEE_TRENDS_CACHED"):
        try:
            live = trends_live.fetch_interest(query, region)
            points = [TrendPoint(date=d, interest=v) for d, v in live]
            source = "live"
        except Exception:
            pass  # pytrends flaky -> keep the seeded series

    spike_detected, spike_date = _detect_spike(points)

    return TrendsResponse(
        store_id=store_id,
        query=query,
        region=region,
        points=points,
        spike_detected=spike_detected,
        spike_date=spike_date,
        source=source,
    )
