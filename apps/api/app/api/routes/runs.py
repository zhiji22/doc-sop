
from fastapi import APIRouter, Depends, BackgroundTasks, Query

from app.api.deps import get_current_user
from app.schemas.run import CreateRunIn, RunOut
from app.services.run_service import (
    create_run_record,
    process_run,
    get_run_for_user,
    list_runs_for_user,
)

router = APIRouter(prefix="/v1/runs", tags=["runs"])


@router.post("", response_model=RunOut)
def create_run(
    body: CreateRunIn,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    run = create_run_record(
        user_id=user["user_id"],
        file_id=body.file_id,
        template=body.template,
    )

    background_tasks.add_task(
        process_run,
        run["id"],
        user["user_id"],
    )

    return run


@router.get("", response_model=list[RunOut])
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(get_current_user),
):
    return list_runs_for_user(
        user_id=user["user_id"],
        limit=limit,
    )


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, user=Depends(get_current_user)):
    return get_run_for_user(
        user_id=user["user_id"],
        run_id=run_id,
    )