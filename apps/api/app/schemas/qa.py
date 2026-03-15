from pydantic import BaseModel


class AskFileQuestionIn(BaseModel):
    file_id: str
    question: str


class CitationOut(BaseModel):
    chunk_id: str
    chunk_index: int
    snippet: str


class AskFileQuestionOut(BaseModel):
    answer: str
    citations: list[CitationOut]


class QaMessageOut(BaseModel):
    id: str
    file_id: str
    user_id: str
    role: str
    content: str
    citations: list[dict] | None = None
    created_at: str | None = None