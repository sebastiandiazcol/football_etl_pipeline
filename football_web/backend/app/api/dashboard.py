from pathlib import Path
from typing import Any, Dict, List

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from ..core.dependencies import get_current_user
from ..models.user import User, UserRole

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

GOLD_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "03_gold.db"


async def _get_gold_conn():
    if not GOLD_DB_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics database not available",
        )
    return await aiosqlite.connect(str(GOLD_DB_PATH))


@router.get("/stats")
async def get_stats(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        conn = await _get_gold_conn()
        async with conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    COUNT(*) AS total_matches,
                    COUNT(DISTINCT team_id) AS total_teams,
                    ROUND(AVG(CAST(is_btts AS FLOAT)) * 100, 2) AS btts_percentage,
                    ROUND(AVG(CAST(is_over_2_5 AS FLOAT)) * 100, 2) AS over25_percentage,
                    ROUND(AVG(CAST(goals_for + goals_against AS FLOAT)), 2) AS avg_goals_per_match
                FROM fact_team_match
                """
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return {}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/recent-matches")
async def recent_matches(current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    try:
        conn = await _get_gold_conn()
        async with conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT * FROM fact_team_match
                ORDER BY date_key DESC
                LIMIT 20
                """
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/teams")
async def get_teams(current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    try:
        conn = await _get_gold_conn()
        async with conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM dim_team ORDER BY team_name")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
