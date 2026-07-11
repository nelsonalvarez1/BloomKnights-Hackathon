"""
Hr 8 - failsafe toggle, wired for real (not just a backup video).

Covers the three sources that actually make LIVE calls and can fail
on stage: OpenSky, EDGAR, Google Trends. Imports doesn't need this -
per Dominic's design it's already 100% cached, there's no "live" mode
to fall back from.

Two failure paths handled the same way:
1. Manual toggle ON - skip live entirely, always serve the cache.
   (the judge-facing "we're going to cached mode" panic button)
2. Automatic - live call raises an exception -> caught, falls back
   to cache transparently, response says live=false so the frontend
   can show a small "showing cached data" indicator.

State (failsafe on/off) persists to a JSON file, not just an
in-memory variable - so a backend restart mid-demo doesn't silently
reset you back to "live" mode without anyone noticing.
"""

import json
from pathlib import Path
from typing import Callable

from fastapi import APIRouter
from pydantic import BaseModel

failsafe_router = APIRouter()

STATE_PATH = Path(__file__).resolve().parent / "failsafe_state.json"


def _read_state() -> dict:
    if not STATE_PATH.exists():
        return {"enabled": False}
    with open(STATE_PATH) as f:
        return json.load(f)


def _write_state(enabled: bool):
    with open(STATE_PATH, "w") as f:
        json.dump({"enabled": enabled}, f)


class FailsafeState(BaseModel):
    enabled: bool


@failsafe_router.get("/failsafe/status")
def failsafe_status():
    return _read_state()


@failsafe_router.post("/failsafe/toggle")
def failsafe_toggle(state: FailsafeState):
    _write_state(state.enabled)
    return _read_state()


def _load_cache(cache_path: str):
    path = Path(cache_path)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _save_cache(cache_path: str, payload: dict):
    with open(cache_path, "w") as f:
        json.dump(payload, f, indent=2)


def with_failsafe(source: str, live_fetch: Callable[[], dict], cache_path: str) -> dict:
    """
    Central helper every live-data route should call.

    - Failsafe manually enabled -> serve cache, never attempt live.
    - Failsafe off -> try live; on ANY exception, log it and fall back
      to cache automatically rather than crashing the endpoint.
    - Every successful live fetch re-saves the cache, so the fallback
      stays fresh for next time.
    """
    state = _read_state()

    if state.get("enabled"):
        cached = _load_cache(cache_path)
        return {"source": source, "live": False, "data": cached, "reason": "failsafe_manual"}

    try:
        payload = live_fetch()
        _save_cache(cache_path, payload)
        return {"source": source, "live": True, "data": payload}
    except Exception as e:
        print(f"[failsafe] live fetch for {source} failed ({e!r}), falling back to cache")
        cached = _load_cache(cache_path)
        return {
            "source": source, "live": False, "data": cached,
            "reason": "live_fetch_failed", "error": str(e),
        }
