"""/api/supply — supply-chain signal: the retailer's latest inbound cargo ship.

Serves the shipping carrier the retailer uses, the most recent vessel to
arrive, its port, and the inventory on board. Seed rows until a real AIS/port
data pull lands.
"""

import json

from fastapi import APIRouter, HTTPException

from database import get_conn
from schemas import ShipmentItem, SupplyResponse
from synth import synth_supply

router = APIRouter()


@router.get("/api/supply", response_model=SupplyResponse)
def get_supply(store_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM shipments WHERE store_id = ?", (store_id,)
        ).fetchone()
        store = conn.execute(
            "SELECT ticker FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
    finally:
        conn.close()

    if store is None:
        raise HTTPException(404, f"Unknown store {store_id}")

    # Synthesize a company-aligned latest shipment when none is seeded, so the
    # supply panel always renders and its volume matches the import trend.
    if row is None:
        carrier, ship, port, arrived, syn_items = synth_supply(store_id, store["ticker"])
        items = [ShipmentItem(item=i, containers=c) for i, c in syn_items]
        return SupplyResponse(
            store_id=store_id, carrier=carrier, ship_name=ship, port=port,
            arrived_at=arrived, items=items,
            total_containers=sum(i.containers for i in items),
        )

    items = [ShipmentItem(**i) for i in json.loads(row["inventory_json"])]
    return SupplyResponse(
        store_id=store_id,
        carrier=row["carrier"],
        ship_name=row["ship_name"],
        port=row["port"],
        arrived_at=row["arrived_at"],
        items=items,
        total_containers=sum(i.containers for i in items),
    )
