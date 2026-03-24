import json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.schemas.qa import AskFileQuestionIn, AskFileQuestionOut, QaMessageOut
from app.services.rag_service import (
    answer_question_with_rag,
    answer_question_with_rag_stream,
    answer_with_tools_stream,
    analyze_document_stream,
    save_qa_message,
    list_qa_messages,
)

router = APIRouter(prefix="/v1/qa", tags=["qa"])


@router.post("/ask", response_model=AskFileQuestionOut)
def ask_question(body: AskFileQuestionIn, user=Depends(get_current_user)):
  user_id = user["user_id"]

  save_qa_message(
    user_id=user_id,
    file_id=body.file_id,
    role="user",
    content=body.question,
    citations=[],
  )

  result = answer_question_with_rag(
    user_id=user_id,
    file_id=body.file_id,
    question=body.question,
  )

  save_qa_message(
    user_id=user_id,
    file_id=body.file_id,
    role="assistant",
    content=result["answer"],
    citations=result["citations"],
  )

  return result


@router.post("/ask/stream")
def ask_question_stream(body: AskFileQuestionIn, user=Depends(get_current_user)):
  """
  流式问答接口。
  返回 SSE（Server-Sent Events）格式的响应，前端用 EventSource 或 fetch 接收。
  
  SSE 格式说明：
  每条消息是一行 "data: {JSON}\n\n"
  前端收到后解析 JSON，根据 type 字段判断是 citations、token 还是 done
  """
  user_id = user["user_id"]

  # 先保存用户的问题到数据库
  save_qa_message(
    user_id=user_id,
    file_id=body.file_id,
    role="user",
    content=body.question,
    citations=[],
  )

  # 调用流式RAG函数，拿到generator和citations
  generator, citations = answer_question_with_rag_stream(
    user_id=user_id,
    file_id=body.file_id,
    question=body.question
  )

  def event_stream():
    """
    把 generator 产出的每条消息，包装成 SSE 格式。
    SSE 格式要求每条消息以 "data: " 开头，以 "\n\n" 结尾。
    """
    full_answer = ""
    
    for item in generator:
      if item["type"] == "token":
        full_answer +=item["token"]

      # 把python dict转成JSON字符串，发给前端
      yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

      if item["type"] == "done":
        save_qa_message(
          user_id=user_id,
          file_id=body.file_id,
          role="assistant",
          content=full_answer,
          citations=citations,
        )

  return StreamingResponse(
    event_stream(),
    media_type="text/event-stream",
    headers={
      "Cache-Control": "no-cache",  # 不缓存
      "Connection": "Keep-alive",   # 保持连接
      "X-Accel-Buffering": "no",    # 禁止 Nginx缓冲
    }
  )


# 使用tool stream
@router.post("/ask/agent")
def ask_question_agent(body: AskFileQuestionIn, user=Depends(get_current_user)):
  """
  Agent 模式问答接口。
  和 /ask/stream 的区别：LLM 自主决定是否搜索文档、搜什么。
  SSE 消息类型多了 tool_call 和 tool_result。
  """
  user_id = user["user_id"]

  save_qa_message(
    user_id=user_id,
    file_id=body.file_id,
    role="user",
    content=body.question,
    citations=[],
  )

  generator, citations = answer_with_tools_stream(
    user_id=user_id,
    file_id=body.file_id,
    question=body.question
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
    }
  )


@router.get("/messages/{file_id}", response_model=list[QaMessageOut])
def get_messages(file_id: str, limit: int = Query(default=50, ge=1, le=200), user=Depends(get_current_user)):
  return list_qa_messages(
    user_id=user["user_id"],
    file_id=file_id,
    limit=limit,
  )


@router.post("/analyze")
def analyze_document(body: AskFileQuestionIn, user=Depends(get_current_user)):
  """
  多步骤文档分析接口。
  和 /ask/agent 的区别：Agent 会先看文档全貌，再逐步深入分析。
  适合复杂分析任务。
  """
  user_id = user["user_id"]

  save_qa_message(
    user_id=user_id,
    file_id=body.file_id,
    role="user",
    content=body.question,
    citations=[],
  )

  generator, citations = analyze_document_stream(
    user_id=user_id,
    file_id=body.file_id,
    task=body.question,
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