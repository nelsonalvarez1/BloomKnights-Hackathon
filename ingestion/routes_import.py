"""
FastAPI route for /data/imports - serves import_ingest.py's output
(fallback/cached_imports.json) to the frontend.
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Assumes this file lives in the same folder as import_ingest.py (i.e.
# ingestion/), mirroring exactly how import_ingest.py itself computes
# OUTPUT_JSON. If you move this file into backend/ instead, either
# adjust this path or set CACHED_IMPORTS_PATH via an env var, don't
# guess a repo depth that might not match.
CACHED_IMPORTS_PATH = Path(__file__).resolve().parent / "fallback" / "cached_imports.json"


def load_cached_imports() -> dict:
    if not CACHED_IMPORTS_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"cached_imports.json not found at {CACHED_IMPORTS_PATH} - "
                    f"run 'python ingestion/import_ingest.py' first",
        )
    with open(CACHED_IMPORTS_PATH) as f:
        return json.load(f)


@router.get("/data/imports")
def get_all_imports():
    """Returns every company's import record, as produced by import_ingest.py."""
    data = load_cached_imports()
    return data


@router.get("/data/imports/top")
def get_top_imports(n: int = 5):
    """
    Returns the top N companies by surge_pct (descending), surged
    companies first. Useful for the screener's ranked list view.
    """
    data = load_cached_imports()
    records = data.get("records", [])

    # None surge_pct sorts last, not first - a missing/invalid metric
    # shouldn't outrank a real negative surge
    sortable = [r for r in records if r.get("surge_pct") is not None]
    unsortable = [r for r in records if r.get("surge_pct") is None]
    sortable.sort(key=lambda r: r["surge_pct"], reverse=True)

    return {
        "source": data.get("source"),
        "pulled_at": data.get("pulled_at"),
        "top": (sortable + unsortable)[:n],
    }


@router.get("/data/imports/{store_id}")
def get_import_by_store_id(store_id: int):
    """Returns a single company's import record by store_id."""
    data = load_cached_imports()
    for record in data.get("records", []):
        if record.get("store_id") == store_id:
            return record
    raise HTTPException(status_code=404, detail=f"no import record for store_id={store_id}")
