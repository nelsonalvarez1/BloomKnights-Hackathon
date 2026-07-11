"""Helpers for pipelines to write real data into perigee.db — no raw SQL needed.

Usage from a script anywhere in the repo (ml/, ingestion/, signals/):

    import sys
    sys.path.insert(0, "backend")  # or the relative path to backend/
    import ingest

    ingest.replace_satellite(
        store_id=1, kind="after", captured_at="2026-07-11",
        image_url="/samples/store1_after.jpg", vehicle_count=187,
        boxes=[{"x": 0.31, "y": 0.44, "w": 0.05, "h": 0.03,
                "label": "vehicle", "confidence": 0.91}],
    )
    ingest.replace_trends(1, "walmart orlando", "US-FL",
                          [("2026-06-28", 100), ("2026-07-05", 91)])

Each replace_* call validates against schemas.py before touching the db, and
replaces that store's rows wholesale — call it with the complete dataset for
the store, not a delta. Writes persist across backend restarts; run reset()
to wipe back to the demo seed.
"""

import json

from database import DB_PATH, get_conn, init_db
from schemas import BoundingBox, Filing, JetEvent, TrendPoint


def replace_satellite(store_id, kind, captured_at, image_url, vehicle_count, boxes):
    """Replace one snapshot (kind: 'before' or 'after') for a store.

    boxes: list of dicts with x, y, w, h (normalized 0-1), label, confidence.
    Remember to put the actual image file at frontend/public/<image_url>.
    """
    if kind not in ("before", "after"):
        raise ValueError("kind must be 'before' or 'after'")
    validated = [BoundingBox(**b).model_dump() for b in boxes]
    init_db()
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM satellite_snapshots WHERE store_id = ? AND kind = ?",
            (store_id, kind),
        )
        conn.execute(
            "INSERT INTO satellite_snapshots (store_id, kind, captured_at, image_url,"
            " vehicle_count, boxes_json) VALUES (?, ?, ?, ?, ?, ?)",
            (store_id, kind, captured_at, image_url, vehicle_count, json.dumps(validated)),
        )
        conn.commit()
    finally:
        conn.close()


def replace_trends(store_id, query, region, points):
    """Replace all trend data for a store.

    points: list of (date, interest) tuples, e.g. [("2026-06-28", 100), ...].
    """
    validated = [TrendPoint(date=d, interest=v) for d, v in points]
    init_db()
    conn = get_conn()
    try:
        conn.execute("DELETE FROM trend_points WHERE store_id = ?", (store_id,))
        conn.execute("DELETE FROM trend_meta WHERE store_id = ?", (store_id,))
        conn.execute("INSERT INTO trend_meta VALUES (?, ?, ?)", (store_id, query, region))
        conn.executemany(
            "INSERT INTO trend_points (store_id, date, interest) VALUES (?, ?, ?)",
            [(store_id, p.date, p.interest) for p in validated],
        )
        conn.commit()
    finally:
        conn.close()


def replace_jets(store_id, events):
    """Replace all jet events for a store.

    events: list of dicts matching schemas.JetEvent — tail_number, operator,
    event_type ('landing' | 'proximity'), airport, distance_miles, timestamp,
    lat, lon. Pass [] for no activity.
    """
    validated = [JetEvent(**e) for e in events]
    init_db()
    conn = get_conn()
    try:
        conn.execute("DELETE FROM jet_events WHERE store_id = ?", (store_id,))
        conn.executemany(
            "INSERT INTO jet_events (store_id, tail_number, operator, event_type,"
            " airport, distance_miles, timestamp, lat, lon)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (store_id, e.tail_number, e.operator, e.event_type, e.airport,
                 e.distance_miles, e.timestamp, e.lat, e.lon)
                for e in validated
            ],
        )
        conn.commit()
    finally:
        conn.close()


def replace_filings(store_id, signal_date, filings):
    """Replace the signal date and all filings for a store.

    signal_date: ISO date our combined signal fired (day 0).
    filings: list of dicts matching schemas.Filing — form_type, filed_at,
    url, description.
    """
    validated = [Filing(**f) for f in filings]
    init_db()
    conn = get_conn()
    try:
        conn.execute("DELETE FROM filings WHERE store_id = ?", (store_id,))
        conn.execute("DELETE FROM signals WHERE store_id = ?", (store_id,))
        conn.execute("INSERT INTO signals VALUES (?, ?)", (store_id, signal_date))
        conn.executemany(
            "INSERT INTO filings (store_id, form_type, filed_at, url, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [(store_id, f.form_type, f.filed_at, f.url, f.description) for f in validated],
        )
        conn.commit()
    finally:
        conn.close()


def reset():
    """Wipe everything back to the demo seed (deletes perigee.db, reseeds)."""
    DB_PATH.unlink(missing_ok=True)
    init_db()
