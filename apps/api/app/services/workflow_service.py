import uuid
import json
from sqlalchemy import text
from app.db.database import engine

import time as _time
from app.core.config import settings
from app.services.llm_service import llm_client
from app.services.tools import ALL_TOOL_SCHEMAS, TOOL_EXECUTORS
from app.services.rag_service import retrieve_relevant_chunks, build_chat_history
from app.services.trace_service import create_trace, finish_trace, record_span


def create_workflow(user_id: str, name: str, description: str, config: dict) -> dict:
  """创建一个新的 Workflow"""
  workflow_id = str(uuid.uuid4())

  with engine.begin() as conn:
    conn.execute(
      text("""
        INSERT INTO agent_workflows (id, user_id, name, description, config)
        VALUES (:id, :user_id, :name, :description, :config)
      """),
      {
        "id": workflow_id,
        "user_id": user_id,
        "name": name,
        "description": description,
        "config": json.dumps(config, ensure_ascii=False),
      },
    )

  return {"id": workflow_id, "name": name, "description": description, "config": config}


def list_workflows(user_id: str) -> list[dict]:
  """列出用户自己的 + 公开的工作流"""
  with engine.connect() as conn:
    rows = conn.execute(
      text("""
        SELECT id, user_id, name, description, config, is_public, created_at, updated_at
        FROM agent_workflows
        WHERE user_id = :user_id OR is_public = TRUE
        ORDER BY created_at DESC
      """),
      {"user_id": user_id},
    ).mappings().all()

  result = []
  for r in rows:
    row_dict = dict(r)
    # config 可能是字符串也可能已经是 dict（取决于驱动）
    if isinstance(row_dict["config"], str):
        row_dict["config"] = json.loads(row_dict["config"])
    result.append(row_dict)

  return result


def get_workflow(workflow_id: str) -> dict | None:
  """获取单个工作流的详情"""
  with engine.connect() as conn:
    row = conn.execute(
      text("SELECT * FROM agent_workflows WHERE id = :id"),
      {"id": workflow_id},
    ).mappings().first()

  if not row:
    return None

  row_dict = dict(row)
  if isinstance(row_dict["config"], str):
    row_dict["config"] = json.loads(row_dict["config"])
  return row_dict


def update_workflow(workflow_id: str, user_id: str, updates: dict) -> bool:
  """
  更新工作流。只有创建者才能更新。
  updates 可包含 name, description, config。
  """
  set_parts = []
  params = {"id": workflow_id, "user_id": user_id}

  if "name" in updates and updates["name"] is not None:
    set_parts.append("name = :name")
    params["name"] = updates["name"]

  if "description" in updates and updates["description"] is not None:
    set_parts.append("description = :description")
    params["description"] = updates["description"]

  if "config" in updates and updates["config"] is not None:
    set_parts.append("config = :config")
    params["config"] = json.dumps(updates["config"], ensure_ascii=False)

  if not set_parts:
    return False

  set_parts.append("updated_at = NOW()")

  with engine.begin() as conn:
    result = conn.execute(
      text(f"""
        UPDATE agent_workflows
        SET {', '.join(set_parts)}
        WHERE id = :id AND user_id = :user_id
      """),
      params,
    )

  return result.rowcount > 0


def delete_workflow(workflow_id: str, user_id: str) -> bool:
  """删除工作流。只有创建者才能删除。"""
  with engine.begin() as conn:
    result = conn.execute(
      text("DELETE FROM agent_workflows WHERE id = :id AND user_id = :user_id"),
      {"id": workflow_id, "user_id": user_id},
    )

  return result.rowcount > 0


def _run_steps_workflow(
  user_id, file_id, system_prompt, steps, temperature,
  question, history, trace_id, trace_start, workflow_name,
):
  """
  按预定义步骤依次执行工具，最后让 LLM 汇总所有结果。
  """
  all_citations = []
  total_tokens = 0
  span_count = 0

  def generate():
    nonlocal all_citations, total_tokens, span_count

    yield {"type": "citations", "citations": []}
    yield {"type": "trace_id", "trace_id": trace_id}
    yield {"type": "thought", "content": f"📋 Running workflow: {workflow_name}"}

    # 收集每一步的结果
    step_results = []

    for i, step in enumerate(steps):
      # 如果是汇总步骤，跳过工具执行
      if step.get("synthesize"):
        yield {"type": "thought", "content": f"Step {i+1}: Synthesizing results..."}
        continue

      tool_name = step.get("tool", "")
      description = step.get("description", f"Step {i+1}")

      yield {"type": "thought", "content": f"Step {i+1}: {description}"}

      if tool_name not in TOOL_EXECUTORS:
        step_results.append(f"[Step {i+1}] Unknown tool: {tool_name}")
        continue

      # 构造工具参数
      tool_args = {}
      if tool_name == "search_document":
        # 用模板中的查询，或用用户的 question
        query = step.get("query_template", question or "document content")
        tool_args = {"query": query}

      elif tool_name == "read_chunk_by_index":
        tool_args = {"chunk_index": step.get("chunk_index", 0)}
      # get_document_outline 不需要参数

      yield {"type": "tool_call", "tool_name": tool_name, "tool_args": tool_args}

      tool_start = _time.time()

      if tool_name in ("search_document", "get_document_outline", "read_chunk_by_index", "save_memory", "recall_memory"):
        tool_result = TOOL_EXECUTORS[tool_name](
          user_id=user_id, file_id=file_id, arguments=tool_args,
        )

        if tool_name == "search_document":
          search_chunks = retrieve_relevant_chunks(
            user_id=user_id, file_id=file_id,
            question=tool_args.get("query", ""), top_k=4,
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

      tool_duration = int((_time.time() - tool_start) * 1000)
      span_count += 1
      record_span(
        trace_id=trace_id, span_type="tool_call", name=tool_name,
        input_data=json.dumps(tool_args, ensure_ascii=False),
        output_data=tool_result[:2000],
        duration_ms=tool_duration,
      )

      yield {
        "type": "tool_result", "tool_name": tool_name,
        "result_preview": tool_result[:200] + "..." if len(tool_result) > 200 else tool_result,
      }

      step_results.append(f"[Step {i+1}: {tool_name}]\n{tool_result}")

    # 所有步骤执行完，让 LLM 汇总
    yield {"type": "thought", "content": "Synthesizing all results..."}
    yield {"type": "citations", "citations": all_citations}

    # 构建汇总消息
    gathered_info = "\n\n---\n\n".join(step_results)

    synth_prompt = system_prompt or (
      "You are a document analysis assistant. "
      "Synthesize the following information into a clear, comprehensive answer. "
      "Always respond in the same language as the user."
    )

    synth_messages = [
      {"role": "system", "content": synth_prompt},
      {
        "role": "user",
        "content": (
          f"User's request: {question}\n\n"
          f"Information gathered from the document:\n\n{gathered_info}\n\n"
          "Please provide a comprehensive answer based on all the information above."
        ),
      },
    ]

    llm_start = _time.time()
    response = llm_client.chat.completions.create(
      model=settings.LLM_MODEL,
      temperature=temperature,
      messages=synth_messages,
    )
    llm_duration = int((_time.time() - llm_start) * 1000)

    usage_tokens = 0
    if getattr(response, "usage", None):
      usage_tokens = getattr(response.usage, "total_tokens", 0) or 0
    total_tokens += usage_tokens
    span_count += 1

    content = response.choices[0].message.content or ""

    record_span(
      trace_id=trace_id, span_type="llm_call", name=f"synthesize/{settings.LLM_MODEL}",
      input_data=f"Synthesize {len(step_results)} step results",
      output_data=content[:3000],
      duration_ms=llm_duration, token_count=usage_tokens,
    )

    chunk_size = 5
    for j in range(0, len(content), chunk_size):
      yield {"type": "token", "token": content[j:j + chunk_size]}

    total_duration = int((_time.time() - trace_start) * 1000)
    finish_trace(trace_id, total_duration, total_tokens, span_count)

    yield {"type": "done", "answer": content}

  return generate(), all_citations


def _run_free_agent_workflow(
  user_id, file_id, system_prompt, temperature,
  max_iterations, question, history, trace_id, trace_start, workflow_name,
):
  """
  用用户自定义的 system_prompt，但让 Agent 自由决定用哪些工具。
  本质上就是 answer_with_tools_stream 的一个变体，只是 system_prompt 不同。
  """
  all_citations = []
  total_tokens = 0
  span_count = 0

  messages = [
    {
      "role": "system",
      "content": (
        system_prompt
        + "\n\nYou have access to tools to search and read the document. "
        "Use them as needed to fulfill the user's request. "
        "Always respond in the same language as the user."
      ),
    },
  ]
  messages.extend(history[-4:])
  if question:
    messages.append({"role": "user", "content": question})

  def generate():
    nonlocal all_citations, total_tokens, span_count

    yield {"type": "citations", "citations": []}
    yield {"type": "trace_id", "trace_id": trace_id}
    yield {"type": "thought", "content": f"📋 Running workflow: {workflow_name}"}

    iteration = 0
    while iteration < max_iterations:
      iteration += 1

      llm_start = _time.time()
      response = llm_client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=temperature,
        messages=messages,
        tools=ALL_TOOL_SCHEMAS,
        tool_choice="auto",
      )
      llm_duration = int((_time.time() - llm_start) * 1000)

      usage_tokens = 0
      if getattr(response, "usage", None):
          usage_tokens = getattr(response.usage, "total_tokens", 0) or 0
      total_tokens += usage_tokens
      span_count += 1

      assistant_message = response.choices[0].message
      content = assistant_message.content or ""
      has_tool_calls = bool(assistant_message.tool_calls)

      record_span(
        trace_id=trace_id, span_type="llm_call", name=settings.LLM_MODEL,
        input_data=json.dumps(messages[-1], ensure_ascii=False)[:3000],
        output_data=content[:3000],
        duration_ms=llm_duration, token_count=usage_tokens,
        meta={"iteration": iteration, "has_tool_calls": has_tool_calls},
      )

      if content and has_tool_calls:
        yield {"type": "thought", "content": content}

      if has_tool_calls:
        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
          tool_name = tool_call.function.name
          tool_args = json.loads(tool_call.function.arguments)

          yield {"type": "tool_call", "tool_name": tool_name, "tool_args": tool_args}

          tool_start = _time.time()
          if tool_name in ("search_document", "get_document_outline", "read_chunk_by_index", "save_memory", "recall_memory"):
            tool_result = TOOL_EXECUTORS[tool_name](
              user_id=user_id, file_id=file_id, arguments=tool_args,
            )
            if tool_name == "search_document":
              search_chunks = retrieve_relevant_chunks(
                user_id=user_id, file_id=file_id,
                question=tool_args.get("query", ""), top_k=4,
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

          tool_duration = int((_time.time() - tool_start) * 1000)
          span_count += 1
          record_span(
            trace_id=trace_id, span_type="tool_call", name=tool_name,
            input_data=json.dumps(tool_args, ensure_ascii=False),
            output_data=tool_result[:2000],
            duration_ms=tool_duration,
          )

          yield {
            "type": "tool_result", "tool_name": tool_name,
            "result_preview": tool_result[:200] + "..." if len(tool_result) > 200 else tool_result,
          }

          messages.append({
            "role": "tool", "tool_call_id": tool_call.id, "content": tool_result,
          })

        yield {"type": "citations", "citations": all_citations}
        continue

      else:
          chunk_size = 5
          for j in range(0, len(content), chunk_size):
            yield {"type": "token", "token": content[j:j + chunk_size]}

          total_duration = int((_time.time() - trace_start) * 1000)
          finish_trace(trace_id, total_duration, total_tokens, span_count)

          yield {"type": "done", "answer": content}
          return

    total_duration = int((_time.time() - trace_start) * 1000)
    finish_trace(trace_id, total_duration, total_tokens, span_count)

    yield {"type": "token", "token": "Workflow reached maximum iterations."}
    yield {"type": "done", "answer": "Workflow reached maximum iterations."}

  return generate(), all_citations


def run_workflow_stream(user_id: str, file_id: str, workflow_id: str, question: str = ""):
  """
  执行一个自定义 Workflow，返回 (generator, citations)。

  逻辑：
  1. 从数据库加载 workflow config
  2. 如果 config 有 steps → 按步骤执行
  3. 如果 config 没有 steps → 用自定义 system_prompt 做自由 Agent
  """
  workflow = get_workflow(workflow_id)

  if not workflow:
    def error_gen():
      yield {"type": "token", "token": "Workflow not found."}
      yield {"type": "done", "answer": "Workflow not found."}
    return error_gen(), []

  config = workflow["config"]
  system_prompt = config.get("system_prompt", "")
  steps = config.get("steps", [])
  temperature = config.get("temperature", 0.2)
  max_iterations = config.get("max_iterations", 10)

  # 创建 Trace
  trace_id = create_trace(
    user_id=user_id, file_id=file_id,
    question=f"[Workflow: {workflow['name']}] {question}",
    agent_mode="workflow",
  )
  trace_start = _time.time()
  total_tokens = 0
  span_count = 0

  history = build_chat_history(user_id=user_id, file_id=file_id, max_rounds=3)

  all_citations = []

  if steps:
    # ── 方式 A：按预定义步骤执行 ──
    return _run_steps_workflow(
      user_id=user_id, file_id=file_id,
      system_prompt=system_prompt, steps=steps,
      temperature=temperature, question=question,
      history=history, trace_id=trace_id,
      trace_start=trace_start, workflow_name=workflow["name"],
    )
  else:
    # ── 方式 B：自由 Agent 模式 ──
    return _run_free_agent_workflow(
      user_id=user_id, file_id=file_id,
      system_prompt=system_prompt, temperature=temperature,
      max_iterations=max_iterations, question=question,
      history=history, trace_id=trace_id,
      trace_start=trace_start, workflow_name=workflow["name"],
    )