"""
生成任务（Run）路由
- POST /v1/runs      创建一次生成任务（上传的文件 → LLM → 结构化输出）
- GET  /v1/runs/{id} 查询某次生成任务的状态和结果
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.run import CreateRunIn, RunOut
from app.services.run_service import create_run_for_user, get_run_for_user

router = APIRouter(prefix="/v1/runs", tags=["runs"])


@router.post("", response_model=RunOut)
def create_run(body: CreateRunIn, user=Depends(get_current_user)):
    """创建生成任务：指定 file_id 和模板类型（sop/checklist/summary）"""
    return create_run_for_user(
        user_id=user["user_id"],
        file_id=body.file_id,
        template=body.template,
    )


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, user=Depends(get_current_user)):
    """查询某次生成任务的详情（状态、结果、错误信息等）"""
    return get_run_for_user(
        user_id=user["user_id"],
        run_id=run_id,
    )