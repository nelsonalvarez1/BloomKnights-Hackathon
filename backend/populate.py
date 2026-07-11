"""Populate perigee.db and compute real confidence scores for every company.

Run from the repo root or backend/:
    python backend/populate.py

What it does:
  1. reset() — wipes and reseeds the DB (hero tier 1-3 with full imports +
     satellite + trends; lite tier 4-25 as company rows only).
  2. Pulls LIVE Google Trends for each lite-tier company and writes it in via
     ingest.replace_trends (falls back per-company if pytrends rate-limits).
  3. Runs fusion.compute_activity_score on every store and persists the result
     to the `scores` table (ingest.write_score) — this is what /api/leaderboard
     serves, so 25 stores don't get re-scored (with live pulls) per request.

Scores are computed off the DB (PERIGEE_TRENDS_CACHED pins get_trends to the
rows we just wrote) so the run is deterministic and doesn't double-pull Trends.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make backend/ importable

import ingest
import trends_live
from database import LITE_TIER, get_conn
from fusion import compute_activity_score
from schemas import TrendsResponse

# Real live Trends pulls are cached here so they ACCUMULATE across runs and
# survive reset() — pytrends rate-limits after ~15-18 calls per window, so we
# never re-pull a ticker we already have, and top up the stragglers next run.
CACHE_FILE = Path(__file__).resolve().parent.parent / "ingestion" / "fallback" / "cached_lite_trends.json"


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2) + "\n")

# Brand search terms for the lite tier — plain brand names pull far better
# Trends data than the full legal filer name.
LITE_QUERIES = {
    "COST": "costco", "LOW": "lowes", "TJX": "tj maxx", "CVS": "cvs",
    "KR": "kroger", "WBA": "walgreens", "BBY": "best buy", "DG": "dollar general",
    "DLTR": "dollar tree", "ROST": "ross", "KSS": "kohls", "M": "macys",
    "JWN": "nordstrom", "AZO": "autozone", "ORLY": "oreilly", "TSCO": "tractor supply",
    "ULTA": "ulta", "SBUX": "starbucks", "MCD": "mcdonalds", "CMG": "chipotle",
    "BJ": "bjs wholesale", "ACI": "albertsons",
}


def _chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def pull_lite_trends() -> set:
    """Populate lite-tier Trends from cache first, then pull whatever's missing
    in BATCHES of 5 (one pytrends call per batch — stays under the rate limit).
    Returns store_ids that ended up with real trend data. Cache accumulates
    across runs; companies still missing are skipped, never fabricated."""
    cache = _load_cache()
    query_of = {s["ticker"]: LITE_QUERIES.get(s["ticker"], s["company"].split()[0].lower())
                for s in LITE_TIER}
    id_of = {s["ticker"]: s["id"] for s in LITE_TIER}

    missing = [t for s in LITE_TIER if (t := s["ticker"]) not in cache]
    print(f"== lite-tier Trends: {len(cache)} cached, {len(missing)} to pull "
          f"in {(len(missing) + 4) // 5} batched calls ==")

    for batch in _chunk(missing, 5):
        queries = [query_of[t] for t in batch]
        try:
            got = trends_live.fetch_interest_batch(queries, "US")
            for t in batch:
                pts = got.get(query_of[t])
                if pts:
                    cache[t] = pts
            _save_cache(cache)  # persist after each batch so 429s keep prior wins
            print(f"  batch {batch}: got {sum(1 for t in batch if t in cache and query_of[t] in got)}")
            time.sleep(3.0)
        except Exception as e:
            print(f"  batch {batch}: skip ({type(e).__name__}) — top up next run")

    # Write every cached ticker into the DB and collect scorable ids.
    have = set()
    for s in LITE_TIER:
        pts = cache.get(s["ticker"])
        if pts:
            ingest.replace_trends(s["id"], query_of[s["ticker"]], "US",
                                  [tuple(p) for p in pts])
            have.add(s["id"])

    print(f"   -> {len(have)}/{len(LITE_TIER)} lite companies have real Trends"
          f" ({len(cache)} cached)\n")
    return have


HERO_IDS = {1, 2, 3}


def score_all(scorable_ids):
    # Score off the DB rows we just wrote (no live re-pull, deterministic).
    os.environ["PERIGEE_TRENDS_CACHED"] = "1"
    from routes.imports import get_imports
    from routes.satellite import get_satellite
    from routes.trends import get_trends

    # Hero tier always has data; lite tier only if it got real Trends.
    ids = sorted(HERO_IDS | set(scorable_ids))

    now = datetime.now(timezone.utc).isoformat()
    print(f"== computing + persisting confidence scores for {len(ids)} companies ==")
    for sid in ids:
        try:
            trends = get_trends(sid)
        except Exception:
            trends = TrendsResponse(
                store_id=sid, query="", region="", points=[], spike_detected=False
            )
        try:
            imports = get_imports(sid)
        except Exception:
            imports = None
        try:
            sat_pct = get_satellite(sid).count_change_pct
        except Exception:
            sat_pct = None

        result = compute_activity_score(
            trends=trends, imports=imports, satellite_count_change_pct=sat_pct
        )
        from fusion import interpret_combined
        ingest.write_score(
            store_id=sid,
            score=result.score,
            confidence=result.confidence,
            import_mag=result.import_signal.magnitude if imports is not None else None,
            satellite_mag=result.satellite_signal.magnitude if sat_pct is not None else None,
            trend_mag=result.trend_signal.magnitude,
            interpretation=interpret_combined(
                result.import_signal, result.satellite_signal
            ),
            computed_at=now,
        )


def print_leaderboard():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT st.ticker, st.company, sc.score, sc.confidence"
            " FROM scores sc JOIN stores st ON st.id = sc.store_id"
            " ORDER BY sc.score DESC, st.company ASC"
        ).fetchall()
    finally:
        conn.close()
    print("\n== LEADERBOARD (all companies by activity score) ==")
    print(f"   {'#':>2}  {'TICKER':6s} {'SCORE':>6s}  {'CONF':7s} COMPANY")
    for i, r in enumerate(rows, 1):
        print(f"   {i:>2}. {r['ticker']:6s} {r['score']:>6.3f}  "
              f"{r['confidence'].upper():7s} {r['company']}")


def main():
    ingest.reset()  # wipe + reseed stores 1-25 + hero-tier signal data
    have = pull_lite_trends()
    score_all(have)
    print_leaderboard()
    print("\nDone. /api/leaderboard now serves these. /api/score recomputes live.")
    print("Re-run to top up any lite companies that were rate-limited this pass.")


if __name__ == "__main__":
    main()
