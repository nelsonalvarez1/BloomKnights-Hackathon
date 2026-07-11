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

class BoundingBox(BaseModel):
    # Normalized 0-1 coordinates relative to the image, so the frontend can
    # overlay them at any render size.
    x: float
    y: float
    w: float
    h: float
    label: str
    confidence: float


class SatelliteSnapshot(BaseModel):
    captured_at: str  # ISO date
    image_url: str    # served from frontend/public/samples/
    vehicle_count: int
    boxes: list[BoundingBox]


class SatelliteResponse(BaseModel):
    store_id: int
    before: SatelliteSnapshot
    after: SatelliteSnapshot
    delta_pct: float  # change in vehicle count, before -> after


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


# ---- /api/jets -------------------------------------------------------------

class JetEvent(BaseModel):
    tail_number: str
    operator: str
    event_type: str  # "landing" | "proximity"
    airport: str
    distance_miles: float  # distance from the store
    timestamp: str
    lat: float
    lon: float


class JetsResponse(BaseModel):
    store_id: int
    events: list[JetEvent]
    proximity_flag: bool


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


# ---- /api/narrative --------------------------------------------------------

class NarrativeRequest(BaseModel):
    store_id: int


class NarrativeResponse(BaseModel):
    store_id: int
    thesis: str
    confidence: str  # "low" | "medium" | "high"
    generated_at: str
    sources: list[str]  # which signals the thesis cites
