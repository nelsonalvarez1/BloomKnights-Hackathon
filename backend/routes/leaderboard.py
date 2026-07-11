"""/api/leaderboard — all tracked companies ranked by activity score.

Reads pre-computed scores from the `scores` table (populated by populate.py).
Store IDs 1-3 are the "hero" tier (full imports + satellite + trends); 4+ are
"lite" tier (Trends + EDGAR only). Returns [] if scores haven't been computed
yet — run `python backend/populate.py`.
"""

from fastapi import APIRouter

from database import get_conn
from schemas import LeaderboardEntry

router = APIRouter()

HERO_IDS = {1, 2, 3}


@router.get("/api/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT s.store_id, st.company, st.ticker, s.score, s.confidence,"
            " s.interpretation, s.computed_at"
            " FROM scores s JOIN stores st ON st.id = s.store_id"
            " ORDER BY s.score DESC, st.company ASC"
        ).fetchall()
    finally:
        conn.close()

    return [
        LeaderboardEntry(
            store_id=r["store_id"],
            company=r["company"],
            ticker=r["ticker"],
            tier="hero" if r["store_id"] in HERO_IDS else "lite",
            score=r["score"],
            confidence=r["confidence"],
            interpretation=r["interpretation"],
            computed_at=r["computed_at"],
        )
        for r in rows
    ]
