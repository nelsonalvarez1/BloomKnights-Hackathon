"""/api/satellite — serves the satellite detection output (Dominic's pipeline).

Until the real YOLO pipeline writes into satellite_snapshots, this serves the
demo seed rows. The response shape is final either way.
"""

import json

from fastapi import APIRouter, HTTPException

from database import get_conn
from schemas import BoundingBox, SatelliteResponse, SatelliteSnapshot

router = APIRouter()


def _snapshot(row) -> SatelliteSnapshot:
    return SatelliteSnapshot(
        captured_at=row["captured_at"],
        image_url=row["image_url"],
        vehicle_count=row["vehicle_count"],
        boxes=[BoundingBox(**b) for b in json.loads(row["boxes_json"])],
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

    before, after = _snapshot(by_kind["before"]), _snapshot(by_kind["after"])
    delta = (after.vehicle_count - before.vehicle_count) / before.vehicle_count * 100
    return SatelliteResponse(
        store_id=store_id, before=before, after=after, delta_pct=round(delta, 1)
    )
