"""
Hour 3 - Google Trends ingestion.

Pulls interest-over-time data for Nelson's locked search terms
and writes the result to JSON.

Install first:
  pip install pytrends pandas

Run:
  python google_trends_ingest.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from pytrends.request import TrendReq


LOCKED_SEARCH_TERMS = [
    # Replace these with Nelson's locked terms exactly
    "term one",
    "term two",
    "term three",
]

OUTPUT_PATH = Path("google_trends_interest_over_time.json")


def fetch_interest_over_time(search_terms, timeframe="today 3-m", geo="US"):
    """
    Fetch Google Trends interest-over-time data.

    timeframe examples:
      "today 1-m"
      "today 3-m"
      "today 12-m"
      "2026-01-01 2026-07-11"

    geo examples:
      "US"
      "" for worldwide
    """
    pytrends = TrendReq(hl="en-US", tz=360)

    pytrends.build_payload(
        kw_list=search_terms,
        cat=0,
        timeframe=timeframe,
        geo=geo,
        gprop="",
    )

    df = pytrends.interest_over_time()

    if df.empty:
        return []

    df = df.reset_index()

    records = []
    for _, row in df.iterrows():
        item = {
            "date": row["date"].isoformat(),
            "terms": {
                term: int(row[term])
                for term in search_terms
                if term in row
            },
        }

        if "isPartial" in row:
            item["is_partial"] = bool(row["isPartial"])

        records.append(item)

    return records


def main():
    if not LOCKED_SEARCH_TERMS or LOCKED_SEARCH_TERMS[0] == "term one":
        print("Add Nelson's locked search terms to LOCKED_SEARCH_TERMS first.")
        raise SystemExit(0)

    data = {
        "source": "google_trends",
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "geo": "US",
        "timeframe": "today 3-m",
        "search_terms": LOCKED_SEARCH_TERMS,
        "interest_over_time": fetch_interest_over_time(
            LOCKED_SEARCH_TERMS,
            timeframe="today 3-m",
            geo="US",
        ),
    }

    OUTPUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"OK - wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
