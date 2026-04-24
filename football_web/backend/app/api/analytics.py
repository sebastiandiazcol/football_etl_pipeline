import csv
import io
from pathlib import Path
from typing import Any, Dict, List

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..core.dependencies import get_current_user
from ..models.user import User

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

GOLD_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "03_gold.db"


async def _get_gold_conn():
    if not GOLD_DB_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics database not available",
        )
    return await aiosqlite.connect(str(GOLD_DB_PATH))


@router.get("/team/{team_id}")
async def team_stats(
    team_id: int,
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    try:
        conn = await _get_gold_conn()
        async with conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    date_key,
                    goals_for,
                    goals_against,
                    xg_for,
                    points,
                    match_result,
                    is_btts,
                    is_over_2_5
                FROM fact_team_match
                WHERE team_id = ?
                ORDER BY date_key
                """,
                (team_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/players")
async def top_players(
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    try:
        conn = await _get_gold_conn()
        async with conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    player_id,
                    SUM(xg) AS total_xg,
                    SUM(shots) AS total_shots,
                    SUM(goals) AS total_goals,
                    COUNT(*) AS matches_played
                FROM fact_player_match
                GROUP BY player_id
                ORDER BY total_xg DESC
                LIMIT 50
                """
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


def _rows_to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


@router.get("/export/teams")
async def export_teams_csv(
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    try:
        conn = await _get_gold_conn()
        async with conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM fact_team_match ORDER BY date_key")
            rows = await cursor.fetchall()
            data = [dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    csv_content = _rows_to_csv(data)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fact_team_match.csv"},
    )


@router.get("/export/players")
async def export_players_csv(
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    try:
        conn = await _get_gold_conn()
        async with conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM fact_player_match ORDER BY player_id")
            rows = await cursor.fetchall()
            data = [dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    csv_content = _rows_to_csv(data)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fact_player_match.csv"},
    )
