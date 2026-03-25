"""
Agent 长期记忆服务。

提供记忆的存储和语义检索功能。
记忆按用户隔离，可选关联到特定文件。
"""
import json
import math
from sqlalchemy import text
from app.db.database import engine
from app.services.embedding_service import get_embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
  if not a or not b or len(a) != len(b):
    return -1.0
  dot = sum(x * y for x, y in zip(a, b))
  norm_a = math.sqrt(sum(x * x for x in a))
  norm_b = math.sqrt(sum(y * y for y in b))
  if norm_a == 0 or norm_b == 0:
    return -1.0
  return dot / (norm_a * norm_b)


def save_memory(
  user_id: str,
  content: str,
  category: str = "general",
  file_id: str | None = None,
) -> dict:
  """
  保存一条长期记忆。
  
  参数:
    - content: 记忆内容
    - category: 分类 (fact / preference / insight / general)
    - file_id: 可选，关联的文件 ID
  """
  embedding = get_embedding(content)

  with engine.begin() as conn:
    row = conn.execute(
      text("""
        INSERT INTO public.agent_memories (user_id, file_id, content, category, embedding)
        VALUES (:user_id, :file_id, :content, :category, :embedding)
        RETURNING id, created_at
      """),
      {
        "user_id": user_id,
        "file_id": file_id,
        "content": content,
        "category": category,
        "embedding": json.dumps(embedding),
      },
    ).mappings().first()

  return {
    "id": str(row["id"]),
    "content": content,
    "category": category,
    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
  }


def recall_memories(
    user_id: str,
    query: str,
    top_k: int = 5,
    file_id: str | None = None,
) -> list[dict]:
  """
  语义搜索召回相关记忆。
  
  参数:
    - query: 搜索查询
    - top_k: 返回最相关的几条
    - file_id: 如果指定，优先搜索该文件相关的记忆，但也包含通用记忆
  """
  query_embedding = get_embedding(query)

  with engine.begin() as conn:
    # 搜索该用户的所有记忆（包括通用的和文件相关的）
    rows = conn.execute(
        text("""
          SELECT id, content, category, file_id, embedding, created_at
          FROM public.agent_memories
          WHERE user_id = :user_id
          ORDER BY created_at DESC
          LIMIT 100
        """),
      {"user_id": user_id},
    ).mappings().all()

  if not rows:
    return []

  scored = []
  for row in rows:
    emb = row["embedding"]
    if isinstance(emb, str):
      emb = json.loads(emb)

    score = cosine_similarity(query_embedding, emb)

    # 如果指定了 file_id，给同文件的记忆加分
    if file_id and row["file_id"] and str(row["file_id"]) == file_id:
      score += 0.05  # 小幅加分

    scored.append({
      "id": str(row["id"]),
      "content": row["content"],
      "category": row["category"],
      "file_id": str(row["file_id"]) if row["file_id"] else None,
      "score": score,
      "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    })

  scored.sort(key=lambda x: x["score"], reverse=True)
  return scored[:top_k]


def list_memories(user_id: str, limit: int = 20) -> list[dict]:
  """列出用户最近的记忆（用于调试/展示）。"""
  with engine.begin() as conn:
    rows = conn.execute(
      text("""
        SELECT id, content, category, file_id, created_at
        FROM public.agent_memories
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT :limit
      """),
      {"user_id": user_id, "limit": limit},
    ).mappings().all()

  return [
    {
      "id": str(row["id"]),
      "content": row["content"],
      "category": row["category"],
      "file_id": str(row["file_id"]) if row["file_id"] else None,
      "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
    for row in rows
  ]