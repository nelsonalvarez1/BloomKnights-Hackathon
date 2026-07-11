"""US customs bill-of-lading ingestion - the supply-side signal.

Every ocean container imported into the US files a CBP customs manifest
(consignee, shipper, container count, arrival date, port, goods). That data is
public and is exactly what Panjiva (S&P) and ImportGenius resell to funds. We
pull the free version from ImportYeti (https://www.importyeti.com), which is
searchable by company name.

WHY THIS IS CACHED, NOT LIVE
----------------------------
Consignee names in customs data are filthy - "WALMART INC", "WAL MART STORES",
subsidiaries, and the importer-of-record often isn't the brand. Matching
manifests to a specific ticker is the whole risk, so we do it by hand once,
verify it, and serve a cached JSON from the fallback layer. On stage it looks
live; behind the curtain it's vetted. The numbers are REAL (public manifests),
just pre-pulled.

HOW TO REFRESH FOR A COMPANY
----------------------------
1. Search the consignee on importyeti.com, confirm it's the right entity.
2. Read off monthly inbound container counts + the top supplier/origin.
3. Add/replace an entry in CACHED_IMPORTS below (store_id -> record).
4. Run `python ingestion/import_ingest.py --ingest` to write into perigee.db,
   or without --ingest to just (re)write the cached JSON.

Metric (kept identical to backend/routes/imports.py so the API and this file
agree): surge = recent 2-month avg vs. the trailing baseline.

*** SCALE-UP NOTE (top 3 -> top 25) ***
Entries 1-3 are Dominic's real, hand-verified ImportYeti pulls - unchanged.
Entries 4-25 are PLACEHOLDERS ONLY - plausible-looking numbers so the
pipeline/screener run end-to-end for testing, but they are NOT real
shipment data. Each is tagged "PLACEHOLDER" in the supplier field as a
loud reminder. Replace each one with a real importyeti.com lookup before
this touches a judge-facing demo - the project's own non-negotiable rule
is "every number is real," and these 22 currently violate that.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTPUT_JSON = Path(__file__).parent / "fallback" / "cached_imports.json"

# store_id -> (consignee, supplier, origin_country, [(month, containers), ...])
# Hand-verified pulls from ImportYeti. Mirrors backend/database.py IMPORTS so
# the cached file and the seed tell the same story.
CACHED_IMPORTS = {
    # --- REAL, hand-verified (Dominic) --------------------------------
    1: ("WALMART INC", "Ningbo Yinzhou Trading Co.", "China",
        [("2026-01", 120), ("2026-02", 118), ("2026-03", 125),
         ("2026-04", 175), ("2026-05", 245), ("2026-06", 330)]),
    2: ("HOME DEPOT USA INC", "Guangdong Homewares Mfg.", "China",
        [("2026-01", 200), ("2026-02", 205), ("2026-03", 210),
         ("2026-04", 240), ("2026-05", 280), ("2026-06", 310)]),
    3: ("TARGET CORP", "Vietnam Consumer Goods JSC", "Vietnam",
        [("2026-01", 90), ("2026-02", 88), ("2026-03", 85),
         ("2026-04", 80), ("2026-05", 74), ("2026-06", 70)]),

    # --- PLACEHOLDER -- replace with real importyeti.com lookups ------
    4: ("AMAZON COM INC", "PLACEHOLDER - look up real supplier", "China",
        [("2026-01", 500), ("2026-02", 510), ("2026-03", 505),
         ("2026-04", 520), ("2026-05", 515), ("2026-06", 530)]),
    5: ("COSTCO WHOLESALE CORP", "PLACEHOLDER - look up real supplier", "China",
        [("2026-01", 400), ("2026-02", 405), ("2026-03", 410),
         ("2026-04", 415), ("2026-05", 420), ("2026-06", 425)]),
    6: ("KROGER CO", "PLACEHOLDER - look up real supplier", "Mexico",
        [("2026-01", 150), ("2026-02", 152), ("2026-03", 148),
         ("2026-04", 151), ("2026-05", 149), ("2026-06", 150)]),
    7: ("CVS HEALTH CORP", "PLACEHOLDER - look up real supplier", "India",
        [("2026-01", 80), ("2026-02", 82), ("2026-03", 79),
         ("2026-04", 81), ("2026-05", 80), ("2026-06", 82)]),
    8: ("TJX COMPANIES INC", "PLACEHOLDER - look up real supplier", "Vietnam",
        [("2026-01", 220), ("2026-02", 225), ("2026-03", 218),
         ("2026-04", 230), ("2026-05", 240), ("2026-06", 245)]),
    9: ("LOWES COMPANIES INC", "PLACEHOLDER - look up real supplier", "China",
        [("2026-01", 180), ("2026-02", 185), ("2026-03", 190),
         ("2026-04", 195), ("2026-05", 200), ("2026-06", 205)]),
    10: ("BEST BUY CO INC", "PLACEHOLDER - look up real supplier", "South Korea",
         [("2026-01", 100), ("2026-02", 98), ("2026-03", 102),
          ("2026-04", 99), ("2026-05", 101), ("2026-06", 100)]),
    11: ("DOLLAR GENERAL CORP", "PLACEHOLDER - look up real supplier", "China",
         [("2026-01", 130), ("2026-02", 128), ("2026-03", 132),
          ("2026-04", 129), ("2026-05", 131), ("2026-06", 130)]),
    12: ("DOLLAR TREE INC", "PLACEHOLDER - look up real supplier", "China",
         [("2026-01", 140), ("2026-02", 138), ("2026-03", 142),
          ("2026-04", 139), ("2026-05", 141), ("2026-06", 140)]),
    13: ("ROSS STORES INC", "PLACEHOLDER - look up real supplier", "Vietnam",
         [("2026-01", 95), ("2026-02", 93), ("2026-03", 97),
          ("2026-04", 94), ("2026-05", 96), ("2026-06", 95)]),
    14: ("ULTA BEAUTY INC", "PLACEHOLDER - look up real supplier", "France",
         [("2026-01", 60), ("2026-02", 62), ("2026-03", 58),
          ("2026-04", 61), ("2026-05", 60), ("2026-06", 62)]),
    15: ("TRACTOR SUPPLY CO", "PLACEHOLDER - look up real supplier", "China",
         [("2026-01", 75), ("2026-02", 77), ("2026-03", 73),
          ("2026-04", 76), ("2026-05", 75), ("2026-06", 77)]),
    16: ("DICKS SPORTING GOODS INC", "PLACEHOLDER - look up real supplier", "Vietnam",
         [("2026-01", 85), ("2026-02", 87), ("2026-03", 83),
          ("2026-04", 86), ("2026-05", 85), ("2026-06", 87)]),
    17: ("BURLINGTON STORES INC", "PLACEHOLDER - look up real supplier", "China",
         [("2026-01", 70), ("2026-02", 72), ("2026-03", 68),
          ("2026-04", 71), ("2026-05", 70), ("2026-06", 72)]),
    18: ("FIVE BELOW INC", "PLACEHOLDER - look up real supplier", "China",
         [("2026-01", 65), ("2026-02", 67), ("2026-03", 63),
          ("2026-04", 66), ("2026-05", 65), ("2026-06", 67)]),
    19: ("WILLIAMS SONOMA INC", "PLACEHOLDER - look up real supplier", "Vietnam",
         [("2026-01", 50), ("2026-02", 52), ("2026-03", 48),
          ("2026-04", 51), ("2026-05", 50), ("2026-06", 52)]),
    20: ("AUTOZONE INC", "PLACEHOLDER - look up real supplier", "Mexico",
         [("2026-01", 90), ("2026-02", 92), ("2026-03", 88),
          ("2026-04", 91), ("2026-05", 90), ("2026-06", 92)]),
    21: ("OREILLY AUTOMOTIVE INC", "PLACEHOLDER - look up real supplier", "Mexico",
         [("2026-01", 88), ("2026-02", 90), ("2026-03", 86),
          ("2026-04", 89), ("2026-05", 88), ("2026-06", 90)]),
    22: ("BJS WHOLESALE CLUB HOLDINGS", "PLACEHOLDER - look up real supplier", "China",
         [("2026-01", 55), ("2026-02", 57), ("2026-03", 53),
          ("2026-04", 56), ("2026-05", 55), ("2026-06", 57)]),
    23: ("GAMESTOP CORP", "PLACEHOLDER - look up real supplier", "China",
         [("2026-01", 30), ("2026-02", 28), ("2026-03", 32),
          ("2026-04", 29), ("2026-05", 30), ("2026-06", 28)]),
    24: ("SHERWIN WILLIAMS CO", "PLACEHOLDER - look up real supplier", "Netherlands",
         [("2026-01", 45), ("2026-02", 47), ("2026-03", 43),
          ("2026-04", 46), ("2026-05", 45), ("2026-06", 47)]),
    25: ("CASEYS GENERAL STORES INC", "PLACEHOLDER - look up real supplier", "USA-domestic",
         [("2026-01", 20), ("2026-02", 21), ("2026-03", 19),
          ("2026-04", 20), ("2026-05", 21), ("2026-06", 20)]),
}

SURGE_RATIO = 1.3


def surge(points):
    """(recent_avg / baseline_avg, pct_change, surged?) or (None, None, False)."""
    counts = [c for _, c in points]
    if len(counts) < 3:
        return None, None, False
    baseline = sum(counts[:-2]) / (len(counts) - 2)
    recent = sum(counts[-2:]) / 2
    if baseline <= 0:
        return None, None, False
    ratio = recent / baseline
    return ratio, round((recent - baseline) / baseline, 3), ratio >= SURGE_RATIO


def build_records():
    records = []
    for store_id, (consignee, supplier, origin, points) in CACHED_IMPORTS.items():
        _, pct, surged = surge(points)
        records.append({
            "store_id": store_id,
            "consignee": consignee,
            "supplier": supplier,
            "origin_country": origin,
            "points": [{"month": m, "containers": c} for m, c in points],
            "surge_detected": surged,
            "surge_pct": pct,
        })
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ingest", action="store_true",
                        help="also write import rows into perigee.db")
    args = parser.parse_args()

    records = build_records()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps({
        "source": "us_customs_bill_of_lading (ImportYeti)",
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_JSON}")
    for r in records:
        surge_txt = (
            f"{round(r['surge_pct'] * 100):+d}%" if r["surge_pct"] is not None else "n/a"
        )
        flag = "SURGE" if r["surge_detected"] else "     "
        print(f"  store {r['store_id']} {r['consignee']:20s} {flag} {surge_txt} vs baseline")

    if args.ingest:
        sys.path.insert(0, str(REPO / "backend"))
        import ingest

        for store_id, (consignee, supplier, origin, points) in CACHED_IMPORTS.items():
            ingest.replace_imports(store_id, consignee, supplier, origin, points)
        print("ingested import rows into perigee.db")


if __name__ == "__main__":
    main()
