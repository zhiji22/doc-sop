from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.services.trace_service import list_traces, get_trace_details

router = APIRouter(prefix="/v1/traces", tags=["traces"])


@router.get("")
def get_traces(
  limit: int = Query(20, ge=1, le=100),
  user=Depends(get_current_user),
):
  """列出当前用户最近的 Trace 记录"""
  user_id = user["user_id"]
  return list_traces(user_id=user_id, limit=limit)


@router.get("/{trace_id}")
def get_trace(trace_id: str, user=Depends(get_current_user)):
  """获取某个 Trace 的详情（包含所有 Span）"""
  detail = get_trace_details(trace_id)
  if not detail:
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="Trace not found")
  return detail