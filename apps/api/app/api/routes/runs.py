from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.run import CreateRunIn, RunOut
from app.services.run_service import create_run_for_user, get_run_for_user

router = APIRouter(prefix="/v1/runs", tags=["runs"])


@router.post("", response_model=RunOut)
def create_run(body: CreateRunIn, user=Depends(get_current_user)):
    return create_run_for_user(
        user_id=user["user_id"],
        file_id=body.file_id,
        template=body.template,
    )


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, user=Depends(get_current_user)):
    return get_run_for_user(
        user_id=user["user_id"],
        run_id=run_id,
    )