"""SQLite connection + schema init + demo seed data.

perigee.db is gitignored and recreated at runtime, so it's always safe to
delete the file and restart to get a clean seed. Teammates replace the seed
rows with real pipeline output as their pieces come online; the shapes here
match schemas.py exactly.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "perigee.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT NOT NULL,
    ticker TEXT NOT NULL,
    cik TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS satellite_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    kind TEXT NOT NULL CHECK (kind IN ('before', 'after')),
    captured_at TEXT NOT NULL,
    image_url TEXT NOT NULL,
    vehicle_count INTEGER NOT NULL,
    boxes_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS trend_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    date TEXT NOT NULL,
    interest INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS trend_meta (
    store_id INTEGER PRIMARY KEY REFERENCES stores(id),
    query TEXT NOT NULL,
    region TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jet_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    tail_number TEXT NOT NULL,
    operator TEXT NOT NULL,
    event_type TEXT NOT NULL,
    airport TEXT NOT NULL,
    distance_miles REAL NOT NULL,
    timestamp TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS filings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    form_type TEXT NOT NULL,
    filed_at TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    store_id INTEGER PRIMARY KEY REFERENCES stores(id),
    signal_date TEXT NOT NULL
);
"""

# ---- Demo seed data ---------------------------------------------------------
# Real companies / CIKs so the EDGAR links resolve; the activity numbers are
# demo placeholders until the real pipelines land.

STORES = [
    {
        "id": 1, "name": "Walmart Supercenter #943", "company": "Walmart Inc.",
        "ticker": "WMT", "cik": "0000104169",
        "city": "Orlando", "state": "FL", "lat": 28.4812, "lon": -81.4622,
    },
    {
        "id": 2, "name": "Home Depot #6348", "company": "The Home Depot, Inc.",
        "ticker": "HD", "cik": "0000354950",
        "city": "Miami", "state": "FL", "lat": 25.7743, "lon": -80.3200,
    },
    {
        "id": 3, "name": "Target T-2075", "company": "Target Corporation",
        "ticker": "TGT", "cik": "0000027419",
        "city": "Tampa", "state": "FL", "lat": 27.9506, "lon": -82.4572,
    },
]

def _boxes(count: int, seed: int) -> str:
    """Deterministic fake YOLO boxes spread across the lot, normalized 0-1."""
    boxes = []
    for i in range(min(count, 14)):  # cap what we draw; count is the real number
        x = ((seed * 37 + i * 61) % 83) / 100
        y = ((seed * 53 + i * 29) % 78) / 100
        boxes.append({
            "x": round(x, 3), "y": round(y, 3), "w": 0.045, "h": 0.03,
            "label": "vehicle", "confidence": round(0.62 + ((seed + i * 7) % 33) / 100, 2),
        })
    return json.dumps(boxes)

SATELLITE = {
    1: [("before", "2026-05-14", "/samples/store1_before.jpg", 118),
        ("after",  "2026-06-29", "/samples/store1_after.jpg", 212)],
    2: [("before", "2026-05-20", "/samples/store2_before.jpg", 96),
        ("after",  "2026-06-28", "/samples/store2_after.jpg", 141)],
    3: [("before", "2026-05-11", "/samples/store3_before.jpg", 104),
        ("after",  "2026-06-30", "/samples/store3_after.jpg", 89)],
}

TRENDS = {
    1: ("walmart orlando", "US-FL",
        [("2026-04-19", 42), ("2026-04-26", 45), ("2026-05-03", 41), ("2026-05-10", 44),
         ("2026-05-17", 47), ("2026-05-24", 43), ("2026-05-31", 46), ("2026-06-07", 52),
         ("2026-06-14", 61), ("2026-06-21", 78), ("2026-06-28", 100), ("2026-07-05", 91)]),
    2: ("home depot miami", "US-FL",
        [("2026-04-19", 55), ("2026-04-26", 53), ("2026-05-03", 57), ("2026-05-10", 54),
         ("2026-05-17", 58), ("2026-05-24", 56), ("2026-05-31", 60), ("2026-06-07", 66),
         ("2026-06-14", 74), ("2026-06-21", 88), ("2026-06-28", 100), ("2026-07-05", 95)]),
    3: ("target tampa", "US-FL",
        [("2026-04-19", 71), ("2026-04-26", 69), ("2026-05-03", 73), ("2026-05-10", 70),
         ("2026-05-17", 66), ("2026-05-24", 62), ("2026-05-31", 58), ("2026-06-07", 55),
         ("2026-06-14", 51), ("2026-06-21", 48), ("2026-06-28", 45), ("2026-07-05", 44)]),
}

JETS = {
    1: [("N721WM", "Walmart Aviation", "landing", "KMCO — Orlando Intl",
         9.4, "2026-06-29T14:22:00Z", 28.4294, -81.3090),
        ("N721WM", "Walmart Aviation", "proximity", "KMCO — Orlando Intl",
         11.8, "2026-06-30T09:05:00Z", 28.4550, -81.3800)],
    2: [("N723HD", "Home Depot Flight Ops", "landing", "KMIA — Miami Intl",
         7.1, "2026-06-27T16:40:00Z", 25.7959, -80.2870)],
    3: [],
}

FILINGS = {
    1: {
        "signal_date": "2026-06-30",
        "filings": [
            ("Form 4", "2026-07-03",
             "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000104169&type=4",
             "Insider transaction reported by a Section 16 officer."),
            ("8-K", "2026-07-05",
             "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000104169&type=8-K",
             "Material event disclosure: regional distribution expansion."),
        ],
    },
    2: {
        "signal_date": "2026-06-28",
        "filings": [
            ("8-K", "2026-07-02",
             "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000354950&type=8-K",
             "Material event disclosure: store remodel program update."),
        ],
    },
    3: {
        "signal_date": "2026-06-30",
        "filings": [
            ("Form 4", "2026-07-06",
             "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000027419&type=4",
             "Insider transaction reported by a Section 16 officer."),
        ],
    },
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0] > 0:
            return
        for s in STORES:
            conn.execute(
                "INSERT INTO stores VALUES (:id, :name, :company, :ticker, :cik, :city, :state, :lat, :lon)",
                s,
            )
        for store_id, snaps in SATELLITE.items():
            for kind, captured_at, image_url, count in snaps:
                conn.execute(
                    "INSERT INTO satellite_snapshots (store_id, kind, captured_at, image_url, vehicle_count, boxes_json)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (store_id, kind, captured_at, image_url, count, _boxes(count, store_id)),
                )
        for store_id, (query, region, points) in TRENDS.items():
            conn.execute("INSERT INTO trend_meta VALUES (?, ?, ?)", (store_id, query, region))
            conn.executemany(
                "INSERT INTO trend_points (store_id, date, interest) VALUES (?, ?, ?)",
                [(store_id, d, v) for d, v in points],
            )
        for store_id, events in JETS.items():
            conn.executemany(
                "INSERT INTO jet_events (store_id, tail_number, operator, event_type, airport,"
                " distance_miles, timestamp, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(store_id, *e) for e in events],
            )
        for store_id, data in FILINGS.items():
            conn.execute("INSERT INTO signals VALUES (?, ?)", (store_id, data["signal_date"]))
            conn.executemany(
                "INSERT INTO filings (store_id, form_type, filed_at, url, description)"
                " VALUES (?, ?, ?, ?, ?)",
                [(store_id, *f) for f in data["filings"]],
            )
        conn.commit()
    finally:
        conn.close()
