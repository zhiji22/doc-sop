import json
import math
from alembic.command import history
from sqlalchemy import text

from app.db.database import engine
from app.services.chunk_service import split_text_into_chunks
from app.services.embedding_service import get_embedding
from app.core.config import settings
from app.services.llm_service import llm_client


def index_file_chunks(user_id: str, file_id: str, raw_text: str):
  chunks = split_text_into_chunks(raw_text, chunk_size=1000, overlap=150)

  with engine.begin() as conn:
    conn.execute(
      text("delete from public.file_chunks where file_id = :file_id and user_id = :user_id"),
      {"file_id": file_id, "user_id": user_id},
    )

    for idx, chunk in enumerate(chunks):
      embedding = get_embedding(chunk)

      conn.execute(
        text("""
          insert into public.file_chunks (file_id, user_id, chunk_index, content, embedding, meta)
          values (:file_id, :user_id, :chunk_index, :content, :embedding, :meta)
        """),
        {
          "file_id": file_id,
          "user_id": user_id,
          "chunk_index": idx,
          "content": chunk,
          "embedding": json.dumps(embedding),
          "meta": json.dumps({}),
        },
      )

def cosine_similarity(a: list[float], b: list[float]) -> float:
  if not a or not b or len(a) != len(b):
    return -1.0

  dot = sum(x * y for x, y in zip(a, b))
  norm_a = math.sqrt(sum(x * x for x in a))
  norm_b = math.sqrt(sum(y * y for y in b))

  if norm_a == 0 or norm_b == 0:
    return -1.0

  return dot / (norm_a * norm_b)

def retrieve_relevant_chunks(user_id: str, file_id: str, question: str, top_k: int = 4):
  question_embedding = get_embedding(question)

  with engine.begin() as conn:
    rows = conn.execute(
      text("""
        select id, chunk_index, content, embedding
        from public.file_chunks
        where file_id = :file_id and user_id = :user_id
        order by chunk_index asc
      """),
      {"file_id": file_id, "user_id": user_id},
    ).mappings().all()

  scored = []
  for row in rows:
    embedding = row["embedding"]
    if isinstance(embedding, str):
      embedding = json.loads(embedding)

    score = cosine_similarity(question_embedding, embedding)
    scored.append({
      "id": str(row["id"]),
      "chunk_index": row["chunk_index"],
      "content": row["content"],
      "score": score,
    })

  scored.sort(key=lambda x: x["score"], reverse=True)
  return scored[:top_k]


# 构建历史对话
def build_chat_history(user_id: str, file_id: str, max_rounds: int = 5) -> list[dict]:
  """
  从数据库取最近的聊天记录，转换成 OpenAI messages 格式。
  要排除最后一条user信息
  
  参数:
    - max_rounds: 最多取最近几轮对话（1轮 = 1条user + 1条assistant）
      取太多会超出 LLM 上下文窗口，5轮是个安全值
  
  返回:
    - [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
  """
  # 取最近的消息 
  recent_messages = list_qa_messages(
    user_id=user_id,
    file_id=file_id,
    limit=max_rounds * 2 + 1,  # 多取一条，因为可能要去掉最后一条
  )

  # 如果最后一条是 user 消息，去掉它（那是当前刚存的问题，会在 prompt 里单独传）
  if recent_messages and recent_messages[-1]["role"] == "user":
    recent_messages = recent_messages[:-1]

  # 只保留最近 max_rounds 轮
  recent_messages = recent_messages[-(max_rounds * 2):]

  history = []
  for msg in recent_messages:
    history.append({
      "role": msg["role"],
      "content": msg["content"]
    })

  return history


def answer_question_with_rag(user_id: str, file_id: str, question: str):
  top_chunks = retrieve_relevant_chunks(
    user_id=user_id,
    file_id=file_id,
    question=question,
    top_k=4,
  )

  context_blocks = []
  citations = []

  for chunk in top_chunks:
    snippet = chunk["content"][:300]
    context_blocks.append(
      f"[Chunk {chunk['chunk_index']}]\n{chunk['content']}"
    )
    citations.append({
      "chunk_id": chunk["id"],
      "chunk_index": chunk["chunk_index"],
      "snippet": snippet,
    })

  context_text = "\n\n".join(context_blocks)

  prompt = f"""
    You are a document Q&A assistant.

    Answer the user's question only using the provided context.
    If the answer cannot be found in the context, say clearly that the document does not provide enough information.
    Be concise and practical.

    Question:
    {question}

    Context:
    {context_text}
    """

  # 获取历史对话记录
  history = build_chat_history(user_id=user_id, file_id=file_id, max_rounds=5)

  # 构建完整的 messages 数组：system + 历史对话 + 当前问题
  messages = [
    {"role": "system", "content": "You answer questions using retrieved document context."},
  ]
  messages.extend(history)  # 把历史对话加进去
  messages.append({"role": "user", "content": prompt})  # 当前问题放最后

  resp = llm_client.chat.completions.create(
    model=settings.LLM_MODEL,
    temperature=0.2,
    messages=messages,
  )

  answer = resp.choices[0].message.content or ""

  return {
    "answer": answer,
    "citations": citations,
  }


def answer_question_with_rag_stream(user_id: str, file_id: str, question: str):
  """
  流式版本 RAG问答
  - 调LLM时加了stream=True
  - 返回的是一个generator, 每次yield一小段文本 token
  - citations在第一次yield之前就准备好
  """
  # 1. 检索相关文档块
  top_chunks = retrieve_relevant_chunks(
    user_id=user_id,
    file_id=file_id,
    question=question,
    top_k=4,
  )

  context_blocks = []
  citations = []

  for chunk in top_chunks:
    snippet = chunk["content"][:300]
    context_blocks.append(
      f"[chunk {chunk['chunk_index']}]\n{chunk['content']}"
    )
    citations.append({
      "chunk_id": chunk["id"],
      "chunk_index": chunk["chunk_index"],
      "snippet": snippet,
    })

  context_text = "\n\n".join(context_blocks)

  prompt = f"""
    You are a document Q&A assistant.

    Answer the user's question only using the provided context.
    If the answer cannot be found in the context, say clearly that the document does not provide enough information.
    Be concise and practical.

    Question:
    {question}

    Context:
    {context_text}
  """

  # 获取历史对话记录
  history = build_chat_history(user_id=user_id, file_id=file_id, max_rounds=5)

  # 构建完整的 messages 数组：system + 历史对话 + 当前问题
  messages = [
    {"role": "system", "content": "You answer questions using retrieved document context."},
  ]
  messages.extend(history)
  messages.append({"role": "user", "content": prompt})

  # 2. 调用 LLM
  stream = llm_client.chat.completions.create(
    model=settings.LLM_MODEL,
    temperature=0.2,
    stream=True,
    messages=messages,
  )

  # 3. 返回一个 generator
  #    - 先 yield citations（前端需要知道引用了哪些文档块）
  #    - 然后逐个 yield LLM 生成的 token
  def generate():
    # 第一条消息：把 citations 发给前端
    yield {
      "type": "citations",
      "citations": citations,
    }

    full_answer = ""

    # 遍历 LLM 的流式响应，每个 chunk 包含一小段文本
    for chunk in stream:
      # chunk.choices[0].delta.content 就是这一小段新生成的文本
      delta = chunk.choices[0].delta
      if delta.content:
        full_answer += delta.content
        yield {
          "type": "token",
          "token": delta.content,
        }

    # 最后一条消息：告诉前端流结束了，附带完整答案
    yield {
      "type": "done",
      "answer": full_answer,
    }

  return generate(), citations



def save_qa_message(user_id: str, file_id: str, role: str, content: str, citations=None):
  with engine.begin() as conn:
    conn.execute(
      text("""
        insert into public.file_qa_messages (file_id, user_id, role, content, citations)
        values (:file_id, :user_id, :role, :content, :citations)
      """),
      {
        "file_id": file_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "citations": json.dumps(citations or []),
      },
    )


def list_qa_messages(user_id: str, file_id: str, limit: int = 50):
  with engine.begin() as conn:
    rows = conn.execute(
      text("""
        select id, file_id, user_id, role, content, citations, created_at
        from public.file_qa_messages
        where file_id = :file_id and user_id = :user_id
        order by created_at asc
        limit :limit
      """),
      {
        "file_id": file_id,
        "user_id": user_id,
        "limit": limit,
      },
    ).mappings().all()

  result = []
  for row in rows:
    result.append({
      "id": str(row["id"]),
      "file_id": str(row["file_id"]),
      "user_id": row["user_id"],
      "role": row["role"],
      "content": row["content"],
      "citations": row["citations"] or [],
      "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    })

  return result

