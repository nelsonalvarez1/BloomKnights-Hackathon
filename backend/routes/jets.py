"""/api/jets — serves corporate jet activity near a store (Sally's OpenSky data)."""

from fastapi import APIRouter

from database import get_conn
from schemas import JetEvent, JetsResponse

router = APIRouter()

PROXIMITY_MILES = 15  # a jet event within this radius sets the proximity flag


@router.get("/api/jets", response_model=JetsResponse)
def get_jets(store_id: int):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT tail_number, operator, event_type, airport, distance_miles,"
            " timestamp, lat, lon FROM jet_events WHERE store_id = ? ORDER BY timestamp",
            (store_id,),
        ).fetchall()
    finally:
        conn.close()

    events = [JetEvent(**dict(r)) for r in rows]
    return JetsResponse(
        store_id=store_id,
        events=events,
        proximity_flag=any(e.distance_miles <= PROXIMITY_MILES for e in events),
    )
