from ast import arguments
import json
import math
from alembic.command import history
from sqlalchemy import text

from app.db.database import engine
from app.services.chunk_service import split_text_into_chunks
from app.services.embedding_service import get_embedding
from app.core.config import settings
from app.services.llm_service import llm_client

from app.services.tools import ALL_TOOL_SCHEMAS, TOOL_EXECUTORS


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


def get_all_chunk_previews(user_id: str, file_id: str) -> list[dict]:
  """获取文档所有 chunk 的预览（前 80 个字符），用于 get_document_outline 工具。"""
  with engine.begin() as conn:
    rows = conn.execute(
      text("""
        select chunk_index, content
        from public.file_chunks
        where file_id = :file_id and user_id = :user_id
        order by chunk_index asc
      """),
      {"file_id": file_id, "user_id": user_id},
    ).mappings().all()

    return [
      {
        "chunk_index": row["chunk_index"],
        "preview": row["content"][:80].replace("\n", " ") + "..."
      }
      for row in rows
    ]


def get_chunk_by_index(user_id: str, file_id: str, chunk_index: int) -> dict | None:
  """按索引精确读取某个 chunk 的完整内容。"""
  with engine.begin() as conn:
    row = conn.execute(
      text("""
        select chunk_index, content
        from public.file_chunks
        where file_id = :file_id and user_id = :user_id and chunk_index = :chunk_index
      """),
      {"file_id": file_id, "user_id": user_id, "chunk_index": chunk_index},
    ).mappings().first()

    if not row:
      return None

    return {
      "chunk_index": row["chunk_index"],
      "content": row["content"],
    }


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


# 带有tool的流式回答
def answer_with_tools_stream(user_id: str, file_id: str, question: str):
  """
  ReAct Agent 模式的流式问答。
  
  ReAct = Reasoning（思考） + Acting（行动）
  
  每一轮循环的结构：
  1. Thought — LLM 分析当前情况，解释接下来要做什么
  2. Action — LLM 决定调用哪个工具（或直接给出最终答案）
  3. Observation — 工具执行结果
  4. 回到 1，直到 LLM 给出最终答案
  
  SSE 消息类型：
  - thought: Agent 的思考过程
  - tool_call: 正在调用工具
  - tool_result: 工具执行结果
  - citations: 引用的文档块
  - token: 最终回答的文本片段
  - done: 流结束
  """
  # 获取历史对话
  history = build_chat_history(user_id=user_id, file_id=file_id, max_rounds=5)
  
  # ReAct 的关键：system prompt 要求 LLM 显式输出思考过程
  messages = [
    {
      "role": "system",
      "content": (
        "You are a document Q&A assistant that follows the ReAct pattern.\n\n"
        "You have access to tools to search the uploaded document.\n"
        "You do NOT have the document content in memory — you MUST use search_document to retrieve it.\n\n"
        "For EVERY question about the document, follow this process:\n"
        "1. First, think about what information you need (your thinking will be shown to the user)\n"
        "2. Use the appropriate tool to get that information\n"
        "3. After getting the tool result, think about whether you have enough information\n"
        "4. Either use another tool or provide your final answer\n\n"
        "When you decide to think, output your reasoning as regular text content.\n"
        "When you decide to act, use the tool_calls mechanism.\n"
        "When you have enough information, provide your final answer as regular text.\n\n"
        "IMPORTANT:\n"
        "- Always respond in the same language as the user's question.\n"
        "- If the user is just greeting or chatting, respond directly without tools.\n"
        "- Be concise and practical in your final answer."
      ),
    },
  ]
  messages.extend(history)
  messages.append({"role": "user", "content": question})
  
  all_citations = []
  
  def generate():
    nonlocal all_citations
    
    yield {
      "type": "citations",
      "citations": [],
    }
    
    # ReAct 循环
    max_iterations = 8  # 比之前多一些，因为每轮可能有 thought + action 两步
    iteration = 0
    
    while iteration < max_iterations:
      iteration += 1
      
      # 调用 LLM
      response = llm_client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=0.2,
        messages=messages,
        tools=ALL_TOOL_SCHEMAS,
        tool_choice="auto",
      )
      
      assistant_message = response.choices[0].message
      content = assistant_message.content or ""
      has_tool_calls = bool(assistant_message.tool_calls)
      
      # ★ ReAct 的核心：LLM 可能同时返回 content（思考）和 tool_calls（行动）
      # 也可能只返回其中一个
      
      # 如果有 content 且还有 tool_calls → 这是 Thought（思考步骤）
      if content and has_tool_calls:
        yield {
          "type": "thought",
          "content": content,
        }
      
      # 如果有 tool_calls → 执行工具（Action 步骤）
      if has_tool_calls:
        messages.append(assistant_message)
        
        for tool_call in assistant_message.tool_calls:
          tool_name = tool_call.function.name
          tool_args = json.loads(tool_call.function.arguments)
          
          yield {
            "type": "tool_call",
            "tool_name": tool_name,
            "tool_args": tool_args,
          }
          
          # 执行工具
          # 需要 user_id/file_id 的工具
          if tool_name in ("search_document", "get_document_outline", "read_chunk_by_index"):
            tool_result = TOOL_EXECUTORS[tool_name](
              user_id=user_id,
              file_id=file_id,
              arguments=tool_args,
            )

            # 如果是搜索工具，提取 citations
            if tool_name == "search_document":
              search_chunks = retrieve_relevant_chunks(
                user_id=user_id,
                file_id=file_id,
                question=tool_args.get("query", ""),
                top_k=4,
              )
              for chunk in search_chunks:
                citation = {
                  "chunk_id": chunk["id"],
                  "chunk_index": chunk["chunk_index"],
                  "snippet": chunk["content"][:300],
                }
                if citation not in all_citations:
                  all_citations.append(citation)
          else:
            # 不需要 user_id/file_id 的工具（如 summarize_text）
            tool_result = TOOL_EXECUTORS[tool_name](arguments=tool_args)
          
          # Observation — 工具结果
          yield {
            "type": "tool_result",
            "tool_name": tool_name,
            "result_preview": tool_result[:200] + "..." if len(tool_result) > 200 else tool_result,
          }
          
          messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": tool_result,
          })
        
        yield {
          "type": "citations",
          "citations": all_citations,
        }
        
        continue  # 回到循环顶部，让 LLM 继续思考
      
      # 如果只有 content 没有 tool_calls → 这是最终回答
      else:
        # 流式输出最终回答
        chunk_size = 5
        for i in range(0, len(content), chunk_size):
          yield {
            "type": "token",
            "token": content[i:i + chunk_size],
          }
        
        yield {
          "type": "done",
          "answer": content,
        }
        return
    
    # 超过最大迭代次数
    yield {
      "type": "token",
      "token": "I've reached the maximum number of reasoning steps.",
    }
    yield {
      "type": "done",
      "answer": "I've reached the maximum number of reasoning steps.",
    }
  
  return generate(), all_citations


def analyze_document_stream(user_id: str, file_id: str, task: str):
  """
  多步骤文档分析模式。
  和 answer_with_tools_stream 的区别：
  - system prompt 要求 Agent 先制定分析计划，再逐步执行
  - 适合复杂任务如"完整分析"、"对比章节"、"提取所有要点"
  """
  history = build_chat_history(user_id=user_id, file_id=file_id, max_rounds=3)

  messages = [
    {
      "role": "system",
      "content": (
        "You are a document analysis agent. You perform thorough, multi-step analysis.\n\n"
        "You have access to tools to explore and analyze the document.\n"
        "You do NOT have the document content in memory.\n\n"
        "For EVERY analysis task, follow this process:\n"
        "1. PLAN: First use get_document_outline to understand the document structure\n"
        "2. GATHER: Use read_chunk_by_index and search_document to collect relevant information\n"
        "3. ANALYZE: After gathering enough data, provide a comprehensive analysis\n\n"
        "Always be thorough — read multiple sections, don't rely on a single search.\n"
        "Always respond in the same language as the user's request.\n"
        "Structure your final answer with clear headings and sections."
      ),
    },
  ]
  messages.extend(history)
  messages.append({"role": "user", "content": task})

  all_citations = []

  def generate():
    nonlocal all_citations

    yield {"type": "citations", "citations": []}

    max_iterations = 12  # 分析任务需要更多轮
    iteration = 0

    while iteration < max_iterations:
      iteration += 1

      response = llm_client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=0.2,
        messages=messages,
        tools=ALL_TOOL_SCHEMAS,
        tool_choice="auto",
      )

      assistant_message = response.choices[0].message
      content = assistant_message.content or ""
      has_tool_calls = bool(assistant_message.tool_calls)

      if content and has_tool_calls:
        yield {"type": "thought", "content": content}

      if has_tool_calls:
        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
          tool_name = tool_call.function.name
          tool_args = json.loads(tool_call.function.arguments)

          yield {
            "type": "tool_call",
            "tool_name": tool_name,
            "tool_args": tool_args,
          }

          if tool_name in ("search_document", "get_document_outline", "read_chunk_by_index"):
              tool_result = TOOL_EXECUTORS[tool_name](
                user_id=user_id,
                file_id=file_id,
                arguments=tool_args,
              )
              if tool_name == "search_document":
                search_chunks = retrieve_relevant_chunks(
                  user_id=user_id,
                  file_id=file_id,
                  question=tool_args.get("query", ""),
                  top_k=4,
                )
                for chunk in search_chunks:
                  citation = {
                    "chunk_id": chunk["id"],
                    "chunk_index": chunk["chunk_index"],
                    "snippet": chunk["content"][:300],
                  }
                  if citation not in all_citations:
                    all_citations.append(citation)
          else:
            tool_result = TOOL_EXECUTORS[tool_name](arguments=tool_args)

          yield {
            "type": "tool_result",
            "tool_name": tool_name,
            "result_preview": tool_result[:200] + "..." if len(tool_result) > 200 else tool_result,
          }

          messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": tool_result,
          })

        yield {"type": "citations", "citations": all_citations}
        continue

      else:
        chunk_size = 5
        for i in range(0, len(content), chunk_size):
          yield {"type": "token", "token": content[i:i + chunk_size]}

        yield {"type": "done", "answer": content}
        return

    yield {"type": "token", "token": "已达到最大分析步数。"}
    yield {"type": "done", "answer": "已达到最大分析步数。"}

  return generate(), all_citations



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

