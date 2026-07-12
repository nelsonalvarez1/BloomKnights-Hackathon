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
from synth import synth_imports

router = APIRouter()

SURGE_RATIO = 1.3  # recent avg must be 1.3x baseline to count as a surge


@router.get("/api/imports", response_model=ImportsResponse)
def get_imports(store_id: int):
    conn = get_conn()
    try:
        store = conn.execute(
            "SELECT ticker FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
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

    if store is None:
        raise HTTPException(404, f"Unknown store {store_id}")

    # No seeded manifests -> synthesize a company-aligned series so the supply
    # signal is consistent with satellite/trends for every tracked name.
    if meta is None or not rows:
        consignee, supplier, origin, syn = synth_imports(store_id, store["ticker"])
        points = [ImportPoint(month=m, containers=c) for m, c in syn]
    else:
        consignee = meta["consignee"]
        supplier = meta["supplier"]
        origin = meta["origin_country"]
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
        consignee=consignee,
        supplier=supplier,
        origin_country=origin,
        points=points,
        surge_detected=surge_detected,
        surge_pct=surge_pct,
    )
