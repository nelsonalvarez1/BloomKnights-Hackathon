"""Deterministic per-company signal synthesis.

Companies without hand-seeded alt-data (everything past the 3 hero stores) get
a synthesized-but-STABLE read so every panel loads and, crucially, all of a
company's signals point the SAME direction — supply, activity, and demand line
up into one coherent recommendation instead of contradicting each other.

Everything is seeded off a single per-company bias in [-1, 1], so satellite,
trends, and imports for a given store always agree and never change between
requests. The 3 hero stores keep their curated real data (these helpers are
only called as a fallback when no seed exists).
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta


def company_bias(store_id: int, ticker: str) -> float:
    """Stable directional bias in [-1, 1] for a company. Positive = expanding,
    negative = contracting. Skewed slightly positive so the universe isn't all
    sells, but with real decliners in the mix."""
    h = int(hashlib.md5(f"{store_id}:{ticker}".encode()).hexdigest(), 16)
    raw = ((h % 1000) / 1000.0)          # 0..1
    return round((raw - 0.42) / 0.58, 3)  # ~ -0.72 .. +1.0, tilted positive


def _ramp(base: float, bias: float, n: int, spread: float, seed: int) -> list[int]:
    """A gently noised monotone-ish ramp of n points sloping with bias."""
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        wobble = (((seed >> (i % 16)) & 7) - 3) / 100.0  # ±3% deterministic noise
        val = base * (1 + bias * spread * t + wobble)
        out.append(max(1, round(val)))
    return out


def synth_satellite(store_id: int, ticker: str) -> tuple[int, int]:
    """(before_count, after_count) vehicles, delta driven by bias."""
    bias = company_bias(store_id, ticker)
    h = int(hashlib.md5(f"sat{store_id}{ticker}".encode()).hexdigest(), 16)
    before = 24 + (h % 46)                    # 24-69
    after = max(5, round(before * (1 + bias * 1.35)))
    return before, after


def synth_trends(store_id: int, ticker: str, company: str, weeks: int = 12) -> tuple[str, str, list[tuple[str, int]]]:
    """(query, region, [(iso_date, interest), ...]) — weekly buckets sloping
    with the company bias, clamped to Google Trends' 0-100 scale."""
    bias = company_bias(store_id, ticker)
    seed = int(hashlib.md5(f"trd{store_id}{ticker}".encode()).hexdigest(), 16)
    base = 40 + (seed % 30)                    # 40-69 baseline interest
    raw = _ramp(base, bias, weeks, 0.8, seed)
    points = []
    start = date.today() - timedelta(weeks=weeks)
    for i, v in enumerate(raw):
        d = start + timedelta(weeks=i)
        points.append((d.isoformat(), max(1, min(100, v))))
    query = company.split(",")[0].split(" Inc")[0].split(" Corp")[0].strip().lower()
    return query, "US", points


def synth_imports(store_id: int, ticker: str, months: int = 6) -> tuple[str, str, str, list[tuple[str, int]]]:
    """(consignee, supplier, origin, [(YYYY-MM, containers), ...]) sloping with bias."""
    bias = company_bias(store_id, ticker)
    seed = int(hashlib.md5(f"imp{store_id}{ticker}".encode()).hexdigest(), 16)
    base = 90 + (seed % 160)                   # 90-249 baseline containers
    raw = _ramp(base, bias, months, 1.1, seed)
    points = []
    today = date.today().replace(day=1)
    # walk back `months` from current month
    y, m = today.year, today.month
    seq = []
    for _ in range(months):
        seq.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    seq.reverse()
    for (yy, mm), v in zip(seq, raw):
        points.append((f"{yy:04d}-{mm:02d}", v))
    origins = ["China", "Vietnam", "India", "Mexico", "South Korea"]
    return f"{ticker} IMPORT OF RECORD", "Overseas Manufacturing Co.", origins[seed % len(origins)], points


_CARRIERS = ["Maersk", "MSC", "CMA CGM", "Evergreen", "Hapag-Lloyd", "COSCO"]
_VESSELS = ["Kensington", "Bianca", "Ever Lucent", "Marseille", "Aurora", "Meridian"]
_PORTS = [
    "Port of Los Angeles — Los Angeles, CA", "Port of Long Beach — Long Beach, CA",
    "Port Newark — Newark, NJ", "PortMiami — Miami, FL", "Port Houston — Houston, TX",
    "Port of Savannah — Savannah, GA",
]
_CATEGORIES = ["General merchandise", "Consumer goods", "Seasonal & outdoor",
               "Electronics", "Apparel", "Home goods", "Grocery & staples"]


def synth_supply(store_id: int, ticker: str) -> tuple[str, str, str, str, list[tuple[str, int]]]:
    """(carrier, ship_name, port, arrived_at, [(item, containers), ...]) — the
    total volume scales with the company's most recent synthesized import month."""
    seed = int(hashlib.md5(f"sup{store_id}{ticker}".encode()).hexdigest(), 16)
    _, _, _, imp_points = synth_imports(store_id, ticker)
    latest = imp_points[-1][1]
    carrier = _CARRIERS[seed % len(_CARRIERS)]
    ship = f"{carrier} {_VESSELS[(seed >> 3) % len(_VESSELS)]}"
    port = _PORTS[(seed >> 6) % len(_PORTS)]
    arrived = (date.today() - timedelta(days=2 + seed % 6)).isoformat()
    # split the latest-month volume across 3 believable categories
    c1 = round(latest * 0.5)
    c2 = round(latest * 0.32)
    c3 = max(1, latest - c1 - c2)
    cats = [_CATEGORIES[seed % len(_CATEGORIES)],
            _CATEGORIES[(seed >> 4) % len(_CATEGORIES)],
            _CATEGORIES[(seed >> 8) % len(_CATEGORIES)]]
    items = list(zip(cats, [c1, c2, c3]))
    return carrier, ship, port, arrived, items


def synth_signal_date(store_id: int, ticker: str) -> str:
    """A plausible recent 'signal fired' date (deterministic), used to anchor
    EDGAR lead-time when no seeded signal exists."""
    seed = int(hashlib.md5(f"sig{store_id}{ticker}".encode()).hexdigest(), 16)
    days_ago = 18 + (seed % 20)                # 18-37 days ago
    return (date.today() - timedelta(days=days_ago)).isoformat()
