from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.schemas.qa import AskFileQuestionIn, AskFileQuestionOut, QaMessageOut
from app.services.rag_service import (
  answer_question_with_rag,
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


@router.get("/messages/{file_id}", response_model=list[QaMessageOut])
def get_messages(file_id: str, limit: int = Query(default=50, ge=1, le=200), user=Depends(get_current_user)):
  return list_qa_messages(
    user_id=user["user_id"],
    file_id=file_id,
    limit=limit,
  )