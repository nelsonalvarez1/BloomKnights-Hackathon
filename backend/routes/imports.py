"""/api/imports — inbound container volume from US customs bill-of-lading data.

The supply-side leading indicator: a company importing sharply more containers
is building inventory for a ramp the market hasn't priced yet. Data is the
same class hedge funds buy from Panjiva/ImportGenius; our demo rows are
hand-verified pulls from ImportYeti (public customs manifests).

Surge detection mirrors the trends spike logic: recent 2-month average vs. the
trailing baseline.
"""

from fastapi import APIRouter, HTTPException

from database import get_conn
from schemas import ImportPoint, ImportsResponse

router = APIRouter()

SURGE_RATIO = 1.3  # recent avg must be 1.3x baseline to count as a surge


@router.get("/api/imports", response_model=ImportsResponse)
def get_imports(store_id: int):
    conn = get_conn()
    try:
        meta = conn.execute(
            "SELECT consignee, supplier, origin_country FROM import_meta"
            " WHERE store_id = ?",
            (store_id,),
        ).fetchone()
        rows = conn.execute(
            "SELECT month, containers FROM import_points WHERE store_id = ?"
            " ORDER BY month",
            (store_id,),
        ).fetchall()
    finally:
        conn.close()

    if meta is None or not rows:
        raise HTTPException(404, f"No import data for store {store_id}")

    points = [ImportPoint(month=r["month"], containers=r["containers"]) for r in rows]

    surge_detected, surge_pct = False, None
    if len(points) >= 3:
        baseline = sum(p.containers for p in points[:-2]) / (len(points) - 2)
        recent = sum(p.containers for p in points[-2:]) / 2
        if baseline > 0:
            surge_pct = round((recent - baseline) / baseline, 3)
            surge_detected = recent / baseline >= SURGE_RATIO

    return ImportsResponse(
        store_id=store_id,
        consignee=meta["consignee"],
        supplier=meta["supplier"],
        origin_country=meta["origin_country"],
        points=points,
        surge_detected=surge_detected,
        surge_pct=surge_pct,
    )
