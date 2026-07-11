"""Shared Pydantic models — THE contract everyone codes against.

Every route response and every frontend fetch in src/api.js matches a model
in this file. Change a shape here first, then update both sides.
"""

from pydantic import BaseModel


# ---- Stores ----------------------------------------------------------------

class Store(BaseModel):
    id: int
    name: str
    company: str
    ticker: str
    cik: str
    city: str
    state: str
    lat: float
    lon: float


# ---- /api/satellite --------------------------------------------------------

class SatelliteSnapshot(BaseModel):
    captured_at: str  # ISO date
    image_url: str    # served from frontend/public/samples/
    car_count: int    # vehicles detected by YOLOv8 in the lot (ml/detect_satellite.py)


class SatelliteResponse(BaseModel):
    store_id: int
    before: SatelliteSnapshot
    after: SatelliteSnapshot
    count_change_pct: float  # (after - before) / before — the activity delta


# ---- /api/imports ----------------------------------------------------------
# US customs bill-of-lading (ImportGenius/Panjiva-style) — the supply-side
# signal. Container inflow leads on-the-ground activity, which leads demand.

class ImportPoint(BaseModel):
    month: str        # "2026-05"
    containers: int   # inbound container count (TEU-equivalent) that month


class ImportsResponse(BaseModel):
    store_id: int
    consignee: str        # matched importer-of-record, e.g. "WALMART INC"
    supplier: str         # top foreign supplier on the manifests
    origin_country: str   # e.g. "China"
    points: list[ImportPoint]
    surge_detected: bool
    surge_pct: float | None = None  # recent months vs. baseline, e.g. 1.14 = +114%


# ---- /api/trends -----------------------------------------------------------

class TrendPoint(BaseModel):
    date: str      # ISO date (weekly buckets)
    interest: int  # Google Trends 0-100 relative interest


class TrendsResponse(BaseModel):
    store_id: int
    query: str            # the search term tracked, e.g. "walmart orlando"
    region: str           # Trends geo, e.g. "US-FL"
    points: list[TrendPoint]
    spike_detected: bool
    spike_date: str | None = None
<<<<<<< HEAD
    source: str = "cached"  # "live" = pulled from Google Trends this request
=======
>>>>>>> 51a0bc0d8f236dfd0014768c54c43812b21ab797


# ---- /api/supply -----------------------------------------------------------

class ShipmentItem(BaseModel):
    item: str        # inventory category, e.g. "General merchandise"
    containers: int  # container count for that category


class SupplyResponse(BaseModel):
    store_id: int
    carrier: str      # shipping company the retailer uses
    ship_name: str    # latest ship to come in
    port: str         # where it docked
    arrived_at: str   # ISO date
    items: list[ShipmentItem]
    total_containers: int


# ---- /api/price ------------------------------------------------------------
# Market context — the stock the signal is about. Current quote is pulled LIVE
# from Finnhub; the daily history is the cached move for the overlay chart.

class PricePoint(BaseModel):
    date: str    # ISO date
    close: float


class PriceResponse(BaseModel):
    store_id: int
    ticker: str
    current: float
    change: float          # vs. previous close, absolute
    percent_change: float  # vs. previous close, %
    prev_close: float
    history: list[PricePoint]  # recent daily closes (for the timeline overlay)
    source: str            # "live" = current quote from Finnhub this request


# ---- /api/edgar ------------------------------------------------------------

class Filing(BaseModel):
    form_type: str  # "Form 4", "8-K", ...
    filed_at: str
    url: str
    description: str


class EdgarResponse(BaseModel):
    store_id: int
    company: str
    cik: str
    signal_date: str      # day 0 — when our combined signal fired
    filings: list[Filing]
    lead_days: int        # days between signal_date and the first filing
    source: str = "cached"  # "live" = pulled from data.sec.gov this request


# ---- /api/narrative --------------------------------------------------------

class NarrativeRequest(BaseModel):
    store_id: int


class NarrativeResponse(BaseModel):
    store_id: int
    thesis: str
    confidence: str  # "low" | "medium" | "high"
    generated_at: str
    sources: list[str]  # which signals the thesis cites


# ---- /api/score ------------------------------------------------------------
# The fused activity score — the hero number. Combines the supply→activity→
# demand funnel (imports + satellite + trends) into one 0-1 score.

class ScoreResponse(BaseModel):
    store_id: int
    score: float        # 0.0 - 1.0, anomaly magnitude
    confidence: str      # "low" | "medium" | "high"
    components: dict[str, float]         # anomaly magnitude per signal
    directions: dict[str, int]           # -1 unusual drop / 0 normal / +1 unusual rise
    weights: dict[str, float]            # effective weights actually applied
    interpretation: str                  # combined physical-evidence read
