"""/api/satellite — serves the before/after satellite imagery (Dominic's pipeline).

Until the real NAIP images are wired in, this serves the demo seed rows. The
response shape is final either way.
"""

from fastapi import APIRouter, HTTPException

from database import get_conn
from schemas import SatelliteResponse, SatelliteSnapshot

router = APIRouter()


def _snapshot(row) -> SatelliteSnapshot:
    return SatelliteSnapshot(
        captured_at=row["captured_at"],
        image_url=row["image_url"],
        car_count=row["car_count"],
    )


@router.get("/api/satellite", response_model=SatelliteResponse)
def get_satellite(store_id: int):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM satellite_snapshots WHERE store_id = ? ORDER BY captured_at",
            (store_id,),
        ).fetchall()
    finally:
        conn.close()

    by_kind = {row["kind"]: row for row in rows}
    if "before" not in by_kind or "after" not in by_kind:
        raise HTTPException(404, f"No satellite data for store {store_id}")

    before = _snapshot(by_kind["before"])
    after = _snapshot(by_kind["after"])
    change = (after.car_count - before.car_count) / before.car_count if before.car_count else 0.0

    return SatelliteResponse(
        store_id=store_id,
        before=before,
        after=after,
        count_change_pct=round(change, 3),
    )
