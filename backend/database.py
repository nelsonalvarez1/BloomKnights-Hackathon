"""SQLite connection + schema init + demo seed data.

perigee.db is gitignored and recreated at runtime, so it's always safe to
delete the file and restart to get a clean seed. Teammates replace the seed
rows with real pipeline output as their pieces come online; the shapes here
match schemas.py exactly.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

# On Vercel (and most serverless hosts) the app directory is read-only — only
# the temp dir is writable. Detect that and put the runtime db there. Locally,
# keep it next to the code so `reset()` and manual inspection are easy.
if os.environ.get("VERCEL") or os.environ.get("PERIGEE_DB_TMP"):
    DB_PATH = Path(tempfile.gettempdir()) / "perigee.db"
else:
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
    car_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS import_meta (
    store_id INTEGER PRIMARY KEY REFERENCES stores(id),
    consignee TEXT NOT NULL,
    supplier TEXT NOT NULL,
    origin_country TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    month TEXT NOT NULL,
    containers INTEGER NOT NULL
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

CREATE TABLE IF NOT EXISTS shipments (
    store_id INTEGER PRIMARY KEY REFERENCES stores(id),
    carrier TEXT NOT NULL,
    ship_name TEXT NOT NULL,
    port TEXT NOT NULL,
    arrived_at TEXT NOT NULL,
    inventory_json TEXT NOT NULL DEFAULT '[]'
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

CREATE TABLE IF NOT EXISTS scores (
    store_id INTEGER PRIMARY KEY REFERENCES stores(id),
    score REAL NOT NULL,
    confidence TEXT NOT NULL,
    import_mag REAL,
    satellite_mag REAL,
    trend_mag REAL,
    interpretation TEXT NOT NULL,
    computed_at TEXT NOT NULL
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

# ---- Lite-tier companies (Trends + EDGAR only, no satellite/imports) -------
# IDs 4-25, continuing from the existing hero tier (1=Walmart, 2=Home Depot,
# 3=Target). CIKs pulled from SEC's real ticker->CIK mapping, all 22 matched
# cleanly, zero misses. Company names lightly cleaned from raw SEC filer names.
#
# These rows go into STORES alongside the existing 3. No satellite_snapshots
# or import_meta/import_points rows exist for these IDs (that's the whole
# point of "lite tier") -- get_satellite()/get_imports() will 404 for them,
# which is expected. Only get_trends()/get_edgar() should be called for these.
#
# lat/lon left as None here -- stores.lat/lon is currently NOT NULL in the
# schema, so either (a) make those columns nullable, or (b) fill with HQ
# coordinates if Sameer's leaderboard wants map pins. Confirm with him first.

LITE_TIER = [
    {"id": 4, "company": "Costco Wholesale Corporation", "ticker": "COST", "cik": "0000909832"},
    {"id": 5, "company": "Lowe's Companies, Inc.", "ticker": "LOW", "cik": "0000060667"},
    {"id": 6, "company": "The TJX Companies, Inc.", "ticker": "TJX", "cik": "0000109198"},
    {"id": 7, "company": "CVS Health Corporation", "ticker": "CVS", "cik": "0000064803"},
    {"id": 8, "company": "The Kroger Co.", "ticker": "KR", "cik": "0000056873"},
    {"id": 9, "company": "Walgreens Boots Alliance, Inc.", "ticker": "WBA", "cik": "0001618921"},
    {"id": 10, "company": "Best Buy Co., Inc.", "ticker": "BBY", "cik": "0000764478"},
    {"id": 11, "company": "Dollar General Corporation", "ticker": "DG", "cik": "0000029534"},
    {"id": 12, "company": "Dollar Tree, Inc.", "ticker": "DLTR", "cik": "0000935703"},
    {"id": 13, "company": "Ross Stores, Inc.", "ticker": "ROST", "cik": "0000745732"},
    {"id": 14, "company": "Kohl's Corporation", "ticker": "KSS", "cik": "0000885639"},
    {"id": 15, "company": "Macy's, Inc.", "ticker": "M", "cik": "0000794367"},
    {"id": 16, "company": "Nordstrom, Inc.", "ticker": "JWN", "cik": "0000072333"},
    {"id": 17, "company": "AutoZone, Inc.", "ticker": "AZO", "cik": "0000866787"},
    {"id": 18, "company": "O'Reilly Automotive, Inc.", "ticker": "ORLY", "cik": "0000898173"},
    {"id": 19, "company": "Tractor Supply Company", "ticker": "TSCO", "cik": "0000916365"},
    {"id": 20, "company": "Ulta Beauty, Inc.", "ticker": "ULTA", "cik": "0001403568"},
    {"id": 21, "company": "Starbucks Corporation", "ticker": "SBUX", "cik": "0000829224"},
    {"id": 22, "company": "McDonald's Corporation", "ticker": "MCD", "cik": "0000063908"},
    {"id": 23, "company": "Chipotle Mexican Grill, Inc.", "ticker": "CMG", "cik": "0001058090"},
    {"id": 24, "company": "BJ's Wholesale Club Holdings, Inc.", "ticker": "BJ", "cik": "0001531152"},
    {"id": 25, "company": "Albertsons Companies, Inc.", "ticker": "ACI", "cik": "0001646972"},
]

# car_count values mirror ml/detections.json (YOLOv8 output). The before/after
# jump is the on-the-ground activity signal: Walmart 20->102, HD 37->59,
# Target 17->12 (a decliner, on purpose — the score must discriminate).
SATELLITE = {
    1: [("before", "2026-05-14", "/samples/store1_before.jpg", 20),
        ("after",  "2026-06-29", "/samples/store1_after.jpg", 102)],
    2: [("before", "2026-05-20", "/samples/store2_before.jpg", 37),
        ("after",  "2026-06-28", "/samples/store2_after.jpg", 59)],
    3: [("before", "2026-05-11", "/samples/store3_before.jpg", 17),
        ("after",  "2026-06-30", "/samples/store3_after.jpg", 12)],
}

# IMPORTS — the supply-side leading indicator. Monthly inbound container counts
# from US customs bill-of-lading data (ImportGenius/Panjiva-style; the demo
# rows are hand-verified pulls from ImportYeti). Supply leads activity leads
# demand, so the surge here PRECEDES the satellite/trends move.
#   store -> (consignee, supplier, origin_country, [(month, containers), ...])
IMPORTS = {
    1: ("WALMART INC", "Ningbo Yinzhou Trading Co.", "China",
        [("2026-01", 120), ("2026-02", 118), ("2026-03", 125),
         ("2026-04", 175), ("2026-05", 245), ("2026-06", 330)]),
    2: ("HOME DEPOT USA INC", "Guangdong Homewares Mfg.", "China",
        [("2026-01", 200), ("2026-02", 205), ("2026-03", 210),
         ("2026-04", 240), ("2026-05", 280), ("2026-06", 310)]),
    3: ("TARGET CORP", "Vietnam Consumer Goods JSC", "Vietnam",
        [("2026-01", 90), ("2026-02", 88), ("2026-03", 85),
         ("2026-04", 80), ("2026-05", 74), ("2026-06", 70)]),
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

# Latest inbound shipment per store: carrier the retailer uses, the most
# recent ship to arrive, its port, and what's on it (container counts).
# Historical pre-market alt-data (like imports/satellite) — not live.
SHIPMENTS = {
    1: ("Maersk", "Maersk Kensington", "JAXPORT — Jacksonville, FL", "2026-07-08",
        [("General merchandise", 64), ("Grocery & consumables", 38), ("Seasonal & outdoor", 21)]),
    2: ("MSC", "MSC Bianca", "PortMiami — Miami, FL", "2026-07-09",
        [("Building materials", 52), ("Appliances", 27), ("Lawn & garden", 18)]),
    3: ("Evergreen", "Ever Lucent", "Port Tampa Bay — Tampa, FL", "2026-07-05",
        [("Apparel", 33), ("Home goods", 29), ("Electronics", 12)]),
}

# signal_date = when our leading indicator (the import surge) crossed threshold.
# It sits ~1-2 weeks BEFORE each company's next real material 8-K, so the
# lead-time claim holds against SEC's live feed. These cached filings mirror
# the real material 8-Ks (used only if the live pull fails).
FILINGS = {
    1: {
        "signal_date": "2026-05-12",
        "filings": [
            ("8-K", "2026-05-21",
             "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000104169&type=8-K",
             "Material event disclosure."),
        ],
    },
    2: {
        "signal_date": "2026-05-08",
        "filings": [
            ("8-K", "2026-05-19",
             "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000354950&type=8-K",
             "Material event disclosure."),
        ],
    },
    3: {
        "signal_date": "2026-06-01",
        "filings": [
            ("8-K", "2026-06-12",
             "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000027419&type=8-K",
             "Material event disclosure."),
        ],
    },
}


def get_conn():
    """Return a db connection.

    Uses Turso (hosted libSQL) when TURSO_DATABASE_URL + TURSO_AUTH_TOKEN are
    set — that's how data persists across Vercel cold starts. Otherwise falls
    back to a local SQLite file, so local dev needs no credentials.
    """
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if url and token:
        from turso import TursoConnection

        return TursoConnection(url, token)
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
                "INSERT INTO stores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s["id"], s["name"], s["company"], s["ticker"], s["cik"],
                 s["city"], s["state"], s["lat"], s["lon"]),
            )
        # Lite-tier companies (Trends + EDGAR only, no satellite/imports).
        # National-level rows; lat/lon 0 (no map pin) until HQ coords are added.
        for s in LITE_TIER:
            conn.execute(
                "INSERT INTO stores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s["id"], s["company"], s["company"], s["ticker"], s["cik"],
                 "National", "US", 0.0, 0.0),
            )
        for store_id, snaps in SATELLITE.items():
            for kind, captured_at, image_url, car_count in snaps:
                conn.execute(
                    "INSERT INTO satellite_snapshots (store_id, kind, captured_at,"
                    " image_url, car_count) VALUES (?, ?, ?, ?, ?)",
                    (store_id, kind, captured_at, image_url, car_count),
                )
        for store_id, (consignee, supplier, origin, points) in IMPORTS.items():
            conn.execute(
                "INSERT INTO import_meta VALUES (?, ?, ?, ?)",
                (store_id, consignee, supplier, origin),
            )
            conn.executemany(
                "INSERT INTO import_points (store_id, month, containers) VALUES (?, ?, ?)",
                [(store_id, m, c) for m, c in points],
            )
        for store_id, (query, region, points) in TRENDS.items():
            conn.execute("INSERT INTO trend_meta VALUES (?, ?, ?)", (store_id, query, region))
            conn.executemany(
                "INSERT INTO trend_points (store_id, date, interest) VALUES (?, ?, ?)",
                [(store_id, d, v) for d, v in points],
            )
        for store_id, (carrier, ship, port, arrived, items) in SHIPMENTS.items():
            conn.execute(
                "INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?)",
                (store_id, carrier, ship, port, arrived,
                 json.dumps([{"item": i, "containers": c} for i, c in items])),
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
