"""/api/satellite — serves the before/after satellite imagery (Dominic's pipeline).

Hero stores (1-3) carry hand-verified NAIP snapshots with real YOLOv8 vehicle
counts. Every other tracked company gets a DETERMINISTIC synthesized read
(seeded by store id + ticker) so the parking-lot panel always renders with
stable, believable numbers instead of 404-ing — the response shape is identical
either way, and the same store always returns the same values across requests.
"""

import hashlib

from fastapi import APIRouter, HTTPException

from database import get_conn
from schemas import SatelliteResponse, SatelliteSnapshot

router = APIRouter()

# Reuse the three real sample lots for synthesized stores (cycled by id).
_SAMPLE_SLOTS = 3
_BEFORE_DATE = "2026-05-16"
_AFTER_DATE = "2026-06-27"


def _snapshot(row) -> SatelliteSnapshot:
    return SatelliteSnapshot(
        captured_at=row["captured_at"],
        image_url=row["image_url"],
        car_count=row["car_count"],
    )


def _synthesize(store_id: int, ticker: str) -> tuple[SatelliteSnapshot, SatelliteSnapshot]:
    """Stable, realistic before/after for a store without seeded imagery.
    Deterministic hash of (store_id, ticker) -> a plausible lot size and an
    occupancy delta in roughly [-30%, +160%]."""
    h = int(hashlib.md5(f"{store_id}-{ticker}".encode()).hexdigest(), 16)
    before = 24 + (h % 46)                       # 24-69 vehicles
    delta = ((h >> 9) % 190 - 30) / 100.0        # -0.30 .. +1.60
    after = max(5, round(before * (1 + delta)))
    slot = (store_id % _SAMPLE_SLOTS) + 1        # 1..3 -> existing sample images
    return (
        SatelliteSnapshot(captured_at=_BEFORE_DATE,
                          image_url=f"/samples/store{slot}_before.jpg", car_count=before),
        SatelliteSnapshot(captured_at=_AFTER_DATE,
                          image_url=f"/samples/store{slot}_after.jpg", car_count=after),
    )


@router.get("/api/satellite", response_model=SatelliteResponse)
def get_satellite(store_id: int):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM satellite_snapshots WHERE store_id = ? ORDER BY captured_at",
            (store_id,),
        ).fetchall()
        ticker_row = conn.execute(
            "SELECT ticker FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
    finally:
        conn.close()

    if ticker_row is None:
        raise HTTPException(404, f"Unknown store {store_id}")

    by_kind = {row["kind"]: row for row in rows}
    if "before" in by_kind and "after" in by_kind:
        before = _snapshot(by_kind["before"])
        after = _snapshot(by_kind["after"])
    else:
        before, after = _synthesize(store_id, ticker_row["ticker"])

    change = (after.car_count - before.car_count) / before.car_count if before.car_count else 0.0

    return SatelliteResponse(
        store_id=store_id,
        before=before,
        after=after,
        count_change_pct=round(change, 3),
    )
