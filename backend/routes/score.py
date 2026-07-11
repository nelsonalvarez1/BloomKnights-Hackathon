"""/api/score — the fused activity score (the hero number on the dashboard).

Pulls the three funnel signals (imports -> satellite -> trends) and runs them
through fusion.compute_activity_score. Returns the 0-1 score, the confidence
band, and the per-component breakdown so the frontend can show WHY the score
is what it is, not just the number.
"""

from fastapi import APIRouter

from routes.imports import get_imports
from routes.satellite import get_satellite
from routes.trends import get_trends
from schemas import ScoreResponse
from fusion import compute_activity_score

router = APIRouter()


def _safe(fn, store_id):
    """Return the response, or None if that signal has no data for the store."""
    try:
        return fn(store_id)
    except Exception:
        return None


@router.get("/api/score", response_model=ScoreResponse)
def get_score(store_id: int):
    trends = _safe(get_trends, store_id)
    imports = _safe(get_imports, store_id)
    satellite = _safe(get_satellite, store_id)

    from schemas import TrendsResponse
    if trends is None:
        trends = TrendsResponse(
            store_id=store_id, query="", region="", points=[], spike_detected=False,
        )

    result = compute_activity_score(
        trends=trends,
        imports=imports,
        satellite_count_change_pct=satellite.count_change_pct if satellite else None,
    )

    return ScoreResponse(
        store_id=store_id,
        score=result.score,
        confidence=result.confidence,
        components={
            "imports": result.import_component,
            "satellite": result.satellite_component,
            "trend": result.trend_component,
        },
        weights=result.weights,
    )
