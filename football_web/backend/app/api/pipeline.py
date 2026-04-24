import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..core.dependencies import require_role
from ..models.user import User, UserRole

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# In-memory pipeline run store
_pipeline_runs: List[Dict[str, Any]] = []


class PipelineRunRequest(BaseModel):
    team_id: int
    max_matches: int = 10


async def _execute_etl(run_id: str, team_id: int, max_matches: int) -> None:
    """Background task that runs the ETL pipeline."""
    run = next((r for r in _pipeline_runs if r["id"] == run_id), None)
    if not run:
        return

    run["status"] = "running"
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", "main.py",
            "--team-id", str(team_id),
            "--max-matches", str(max_matches),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            run["status"] = "completed"
            run["output"] = stdout.decode(errors="replace")
        else:
            run["status"] = "failed"
            run["error"] = stderr.decode(errors="replace")
    except Exception as exc:
        run["status"] = "failed"
        run["error"] = str(exc)
    finally:
        run["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_pipeline(
    data: PipelineRunRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    run: Dict[str, Any] = {
        "id": run_id,
        "team_id": data.team_id,
        "max_matches": data.max_matches,
        "status": "pending",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "error": None,
        "triggered_by": current_user.email,
    }
    _pipeline_runs.append(run)
    asyncio.create_task(_execute_etl(run_id, data.team_id, data.max_matches))
    return run


@router.get("/runs")
async def list_runs(
    current_user: User = Depends(require_role(UserRole.admin)),
) -> List[Dict[str, Any]]:
    return list(reversed(_pipeline_runs))


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    current_user: User = Depends(require_role(UserRole.admin)),
) -> Dict[str, Any]:
    run = next((r for r in _pipeline_runs if r["id"] == run_id), None)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run
