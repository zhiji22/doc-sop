import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.schemas.workflow import CreateWorkflowIn, UpdateWorkflowIn, RunWorkflowIn
from app.services.workflow_service import (
  create_workflow,
  list_workflows,
  get_workflow,
  update_workflow,
  delete_workflow,
  run_workflow_stream,
)
from app.services.rag_service import save_qa_message

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


@router.post("")
def create(body: CreateWorkflowIn, user=Depends(get_current_user)):
  """创建一个新的工作流"""
  user_id = user["user_id"]
  return create_workflow(
    user_id=user_id,
    name=body.name,
    description=body.description,
    config=body.config.model_dump(),
  )


@router.get("")
def list_all(user=Depends(get_current_user)):
  """列出用户可用的所有工作流（自己的 + 公开的）"""
  return list_workflows(user_id=user["user_id"])


@router.get("/{workflow_id}")
def get_one(workflow_id: str, user=Depends(get_current_user)):
  """获取单个工作流的详情"""
  wf = get_workflow(workflow_id)
  if not wf:
    raise HTTPException(status_code=404, detail="Workflow not found")
  
  return wf


@router.put("/{workflow_id}")
def update(workflow_id: str, body: UpdateWorkflowIn, user=Depends(get_current_user)):
  """更新工作流（只有创建者可更新）"""
  updates = {}
  if body.name is not None:
    updates["name"] = body.name
  if body.description is not None:
    updates["description"] = body.description
  if body.config is not None:
    updates["config"] = body.config.model_dump()

  ok = update_workflow(workflow_id=workflow_id, user_id=user["user_id"], updates=updates)
  if not ok:
    raise HTTPException(status_code=404, detail="Workflow not found or not owned by you")
  return {"ok": True}


@router.delete("/{workflow_id}")
def delete(workflow_id: str, user=Depends(get_current_user)):
  """删除工作流（只有创建者可删除）"""
  ok = delete_workflow(workflow_id=workflow_id, user_id=user["user_id"])
  if not ok:
    raise HTTPException(status_code=404, detail="Workflow not found or not owned by you")
  return {"ok": True}


@router.post("/run")
def run(body: RunWorkflowIn, user=Depends(get_current_user)):
  """
  执行一个工作流。
  返回 SSE 流式响应。
  """
  user_id = user["user_id"]

  save_qa_message(
    user_id=user_id,
    file_id=body.file_id,
    role="user",
    content=f"[Workflow] {body.question}" if body.question else "[Workflow] Run",
    citations=[],
  )

  generator, citations = run_workflow_stream(
    user_id=user_id,
    file_id=body.file_id,
    workflow_id=body.workflow_id,
    question=body.question,
  )

  def event_stream():
    full_answer = ""
    final_citations = []

    for item in generator:
      if item["type"] == "token":
        full_answer += item["token"]
      if item["type"] == "citations":
        final_citations = item["citations"]

      yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

      if item["type"] == "done":
        save_qa_message(
          user_id=user_id,
          file_id=body.file_id,
          role="assistant",
          content=full_answer,
          citations=final_citations,
        )

  return StreamingResponse(
    event_stream(),
    media_type="text/event-stream",
    headers={
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no",
    },
  )