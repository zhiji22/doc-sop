import uuid
import json
from datetime import datetime
from sqlalchemy import text
from app.db.database import engine


def create_trace(user_id: str, file_id: str, question: str, agent_mode: str) -> str:
  """
  创建一个新的 Trace 记录，状态为 running。
  返回 trace_id（一个 UUID 字符串）。
  """
  trace_id = str(uuid.uuid4())

  with engine.begin() as conn:
    conn.execute(
      text("""
        INSERT INTO agent_traces (id, user_id, file_id, question, agent_mode, status)
        VALUES (:id, :user_id, :file_id, :question, :agent_mode, 'running')
      """),
      {
        "id": trace_id,
        "user_id": user_id,
        "file_id": file_id,
        "question": question[:2000],   # 截断，防止太长
        "agent_mode": agent_mode,
      },
    )

  return trace_id


def finish_trace(trace_id: str, total_duration_ms: int, total_tokens: int, span_count: int):
  """
  Trace 结束时调用。
  更新状态为 completed，记录总耗时、总 token、span 数量。
  """
  with engine.begin() as conn:
    conn.execute(
      text("""
        UPDATE agent_traces
        SET status = 'completed',
          total_duration_ms = :duration,
          total_tokens = :tokens,
          span_count = :spans,
          finished_at = NOW()
        WHERE id = :id
      """),
      {
        "id": trace_id,
        "duration": total_duration_ms,
        "tokens": total_tokens,
        "spans": span_count,
      },
    )


def record_span(
  trace_id: str,
  span_type: str,       # "llm_call" | "tool_call" | "agent_phase"
  name: str,            # 如 "qwen-plus" 或 "search_document" 或 "Planner"
  input_data: str = "",
  output_data: str = "",
  duration_ms: int = 0,
  token_count: int = 0,
  meta: dict | None = None,
):
  """
  记录一个 Span（一个步骤）。
  """
  span_id = str(uuid.uuid4())

  with engine.begin() as conn:
    conn.execute(
      text("""
        INSERT INTO agent_trace_spans
          (id, trace_id, span_type, name, input_data, output_data,
            duration_ms, token_count, meta)
        VALUES
          (:id, :trace_id, :span_type, :name, :input_data, :output_data,
            :duration_ms, :token_count, :meta)
    """),
      {
        "id": span_id,
        "trace_id": trace_id,
        "span_type": span_type,
        "name": name,
        "input_data": (input_data or "")[:3000],     # 截断
        "output_data": (output_data or "")[:3000],   # 截断
        "duration_ms": duration_ms,
        "token_count": token_count,
        "meta": json.dumps(meta or {}, ensure_ascii=False),
      },
  )


def list_traces(user_id: str, limit: int = 20) -> list[dict]:
  """
  列出某用户最近的Trace记录
  """
  with engine.connect() as conn:
    rows = conn.execute(
      text("""
        SELECT id, file_id, question, agent_mode, status,
          total_duration_ms, total_tokens, span_count, created_at
        FROM agent_traces
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT :limit
    """),
    {"user_id": user_id, "limit": limit},
  ).mappings().all()

  return [dict(r) for r in rows]


def get_trace_details(trace_id: str) -> dict | None:
  """
  获取某个Trace的详情，包括所有的Span
  """
  with engine.connect() as conn:
    # 获取 trace 主信息
    trace_row = conn.execute(
      text("SELECT * FROM agent_traces WHERE id = :id"),
      {"id": trace_id},
    ).mappings().first()

    if not trace_row:
      return None

    # 获取所有 span
    span_rows = conn.execute(
      text("""
        SELECT id, span_type, name, input_data, output_data,
          duration_ms, token_count, meta, created_at
        FROM agent_trace_spans
        WHERE trace_id = :trace_id
        ORDER BY created_at ASC
      """),
      {"trace_id": trace_id},
    ).mappings().all()

    return {
      "trace": dict(trace_row),
      "spans": [dict(s) for s in span_rows],
    }
