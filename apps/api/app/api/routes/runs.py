
from fastapi import APIRouter, Depends, Query
from arq.connections import ArqRedis, create_pool

from app.api.deps import get_current_user
from app.schemas.run import CreateRunIn, RunOut, ShareRunOut, PublicRunOut
from app.services.run_service import (
    create_run_record,
    get_run_for_user,
    list_runs_for_user,
    create_or_enable_share_for_run,
    disable_share_for_run,
    get_public_run_by_share_id,
)
from app.worker import parse_redis_url
from app.core.config import settings

router = APIRouter(prefix="/v1/runs", tags=["runs"])


async def get_arq_pool() -> ArqRedis:
    """
    获取 ARQ 的 Redis 连接池。
    用于向队列中投递任务。
    """
    redis_settings = parse_redis_url(settings.REDIS_URL)
    return await create_pool(redis_settings)

@router.post("", response_model=RunOut)
async def create_run(
    body: CreateRunIn,
    user=Depends(get_current_user),
):
    run = create_run_record(
        user_id=user["user_id"],
        file_id=body.file_id,
        template=body.template,
    )

    # 把任务投递到ARQ队列中
    pool = await get_arq_pool()
    await pool.enqueue_job(
        "task_process_run",       # 任务函数名（字符串）
        run["id"],                # 第一个参数：run_id
        user["user_id"],          # 第二个参数：user_id
    )
    await pool.close()

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

@router.post("/{run_id}/unshare", response_model=ShareRunOut)
def unshare_run(run_id: str, user=Depends(get_current_user)):
    return disable_share_for_run(
        user_id=user["user_id"],
        run_id=run_id,
    )