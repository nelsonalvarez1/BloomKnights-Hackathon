"""Live Google Trends client (pytrends) for /api/trends.

pytrends is the unofficial Trends API — no key, but it can rate-limit (429) or
change without notice. routes/trends.py calls fetch_interest() first and falls
back to the seeded weekly series if this raises, so the demo never hard-fails.

Returns weekly buckets (resampled from Trends' daily series) to match the shape
of the seed rows and keep the spike/z-score math consistent across live/cached.
"""

DEFAULT_TIMEFRAME = "today 3-m"


def fetch_interest(query: str, geo: str, timeframe: str = DEFAULT_TIMEFRAME) -> list[tuple]:
    """Return [(iso_date, interest_0_100), ...] weekly for `query` in `geo`.

    Raises on empty result or any pytrends error so the caller can fall back.
    Imported lazily so the backend runs even if pytrends isn't installed.
    """
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload(kw_list=[query], timeframe=timeframe, geo=geo)
    df = pytrends.interest_over_time()
    if df.empty or query not in df:
        raise RuntimeError(f"no Trends data for {query!r} ({geo})")

    weekly = df[query].resample("W").mean().round().astype(int)
    points = [(idx.date().isoformat(), int(v)) for idx, v in weekly.items() if v > 0]
    if len(points) < 3:
        raise RuntimeError(f"insufficient Trends data for {query!r}")
    return points
