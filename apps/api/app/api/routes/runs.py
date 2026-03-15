
from fastapi import APIRouter, Depends, BackgroundTasks, Query

from app.api.deps import get_current_user
from app.schemas.run import CreateRunIn, RunOut, ShareRunOut, PublicRunOut
from app.services.run_service import (
    create_run_record,
    process_run,
    get_run_for_user,
    list_runs_for_user,
    create_or_enable_share_for_run,
    get_public_run_by_share_id,
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

@router.post("/{run_id}/share", response_model=ShareRunOut)
def share_run(run_id: str, user=Depends(get_current_user)):
    return create_or_enable_share_for_run(
        user_id=user["user_id"],
        run_id=run_id,
    )


@router.get("/public/{share_id}", response_model=PublicRunOut)
def get_public_run(share_id: str):
    return get_public_run_by_share_id(share_id)