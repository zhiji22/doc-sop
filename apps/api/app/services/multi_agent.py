"""
Multi-Agent 协作模块。

三个 Agent 各司其职：
1. Planner  — 分析用户需求，制定执行计划
2. Executor — 按计划逐步执行，调用工具收集信息
3. Reviewer — 审查执行结果，判断是否需要补充

协作流程：
  用户请求 → Planner 制定计划 → Executor 执行 → Reviewer 审查
  → 如果审查不通过 → Executor 补充执行 → Reviewer 再审查
  → 审查通过 → 输出最终回答
"""
import json
from app.core.config import settings
from app.services.llm_service import llm_client
from app.services.rag_service import (
    build_chat_history,
    retrieve_relevant_chunks,
)
from app.services.tools import ALL_TOOL_SCHEMAS, TOOL_EXECUTORS


# ============================================================
# Agent 1: Planner（规划者）
# ============================================================

def run_planner(question: str, history: list[dict], memory_context: str = "") -> str:
  """
  规划 Agent：分析用户需求，输出一个结构化的执行计划。
  
  不调用任何工具，只做"思考"。
  返回一段文本描述的执行计划。
  """
  messages = [
    {
      "role": "system",
      "content": (
        "You are a Planning Agent. Your job is to analyze the user's request "
        "and create a clear, step-by-step execution plan.\n\n"
        "You do NOT execute anything yourself. You only create the plan.\n\n"
        "Available tools that the Executor can use:\n"
        "- search_document(query): Search the document for relevant content\n"
        "- get_document_outline(): Get an overview of the document structure\n"
        "- read_chunk_by_index(chunk_index): Read a specific section\n"
        "- save_memory(content, category): Save important info to memory\n"
        "- recall_memory(query): Search past memories\n\n"
        "Output your plan as a numbered list of steps. Each step should specify:\n"
        "1. What tool to use (or 'synthesize' for the final answer)\n"
        "2. What parameters to pass\n"
        "3. What information you expect to get\n\n"
        "Keep the plan concise (3-6 steps). Always respond in the same language as the user."
        + memory_context
      ),
    },
  ]
  messages.extend(history[-4:])  # 只用最近 2 轮历史
  messages.append({"role": "user", "content": question})

  response = llm_client.chat.completions.create(
    model=settings.LLM_MODEL,
    temperature=0.3,
    messages=messages,
  )

  return response.choices[0].message.content or ""

# ============================================================
# Agent 2: Executor（执行者）
# ============================================================

def run_executor(
  plan: str,
  question: str,
  user_id: str,
  file_id: str,
  history: list[dict],
):
  """
  执行 Agent：按照 Planner 的计划，逐步调用工具收集信息。
  
  这是一个 generator，会 yield SSE 消息（tool_call, tool_result 等）。
  最终 yield 一个包含所有收集到的信息的汇总。
  """
  messages = [
    {
      "role": "system",
      "content": (
        "You are an Executor Agent. You have been given a plan to follow.\n\n"
        "Your job is to execute the plan step by step using the available tools.\n"
        "After executing all steps, provide a comprehensive answer based on the information gathered.\n\n"
        "IMPORTANT:\n"
        "- Follow the plan closely\n"
        "- Use tools to gather information\n"
        "- After gathering all information, provide your answer\n"
        "- Always respond in the same language as the user's question\n\n"
        f"=== PLAN ===\n{plan}\n=== END PLAN ==="
      ),
    },
  ]
  messages.extend(history[-4:])
  messages.append({"role": "user", "content": question})
  
  all_citations = []
  collected_info = []

  max_iterations = 10
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
      yield {"type": "thought", "content": f"[Executor] {content}"}

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
        if tool_name in ("search_document", "get_document_outline", "read_chunk_by_index", "save_memory", "recall_memory"):
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

        collected_info.append(f"[{tool_name}] {tool_result[:500]}")

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
      # Executor 给出了最终回答
      yield {
        "type": "executor_done",
        "answer": content,
        "citations": all_citations,
      }
      return

  yield {
    "type": "executor_done",
    "answer": "Executor reached maximum iterations.",
    "citations": all_citations,
  }


# ============================================================
# Agent 3: Reviewer（审查者）
# ============================================================

def run_reviewer(
  question: str,
  executor_answer: str,
) -> dict:
  """
  审查 Agent：检查 Executor 的回答质量。
  
  返回:
    - approved: bool — 是否通过审查
    - feedback: str — 审查意见（如果不通过，说明需要补充什么）
    - improved_answer: str — 如果通过，可能会润色后的最终回答
  """
  messages = [
    {
      "role": "system",
      "content": (
        "You are a Reviewer Agent. Your job is to review an answer and decide if it's good enough.\n\n"
        "Evaluate the answer on these criteria:\n"
        "1. Completeness — Does it fully address the user's question?\n"
        "2. Accuracy — Is the information consistent and well-supported?\n"
        "3. Clarity — Is it well-organized and easy to understand?\n\n"
        "You MUST respond in this exact JSON format:\n"
        '{"approved": true/false, "feedback": "your feedback", "improved_answer": "the final answer (improved if needed)"}\n\n'
        "If the answer is good (score >= 7/10 on all criteria), set approved=true and put the "
        "(optionally polished) answer in improved_answer.\n"
        "If the answer needs significant improvement, set approved=false and explain what's missing in feedback.\n\n"
        "Always respond in the same language as the user's question.\n"
        "IMPORTANT: Your response must be valid JSON and nothing else."
      ),
    },
    {
      "role": "user",
      "content": (
        f"User's original question:\n{question}\n\n"
        f"Executor's answer:\n{executor_answer}"
      ),
    },
  ]

  response = llm_client.chat.completions.create(
    model=settings.LLM_MODEL,
    temperature=0.1,
    messages=messages,
  )

  raw = response.choices[0].message.content or ""

  try:
    # 尝试解析 JSON
    # 有些 LLM 会在 JSON 外面包 ```json ... ```，需要清理
    cleaned = raw.strip()
    if cleaned.startswith("```"):
      cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]

      if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
      cleaned = cleaned.strip()
    result = json.loads(cleaned)

    return {
      "approved": result.get("approved", True),
      "feedback": result.get("feedback", ""),
      "improved_answer": result.get("improved_answer", executor_answer),
    }
  except (json.JSONDecodeError, KeyError):
    # JSON 解析失败，默认通过
    return {
      "approved": True,
      "feedback": "",
      "improved_answer": executor_answer,
    }

# ============================================================
# 协作编排：把 3 个 Agent 串起来
# ============================================================

def multi_agent_stream(user_id: str, file_id: str, question: str):
  """
  Multi-Agent 协作流式问答。
  
  流程：
  1. Planner 制定计划
  2. Executor 按计划执行
  3. Reviewer 审查结果
  4. 如果审查不通过，Executor 根据反馈补充执行（最多重试 1 次）
  5. 输出最终回答
  """
  history = build_chat_history(user_id=user_id, file_id=file_id, max_rounds=3)

  # 召回长期记忆
  from app.services.memory_service import recall_memories

  relevant_memories = recall_memories(
    user_id=user_id,
    query=question,
    top_k=3,
    file_id=file_id,
  )
  memory_context = ""

  if relevant_memories:
    memory_parts = [f"- [{m['category']}] {m['content']}" for m in relevant_memories]
    memory_context = (
      "\n\nRelevant memories:\n"
      + "\n".join(memory_parts)
    )

  all_citations = []

  def generate():
    nonlocal all_citations

    yield {"type": "citations", "citations": []}

    # ── Phase 1: Planner ──
    yield {"type": "thought", "content": "🧠 [Planner] Analyzing request and creating execution plan..."}

    plan = run_planner(
      question=question,
      history=history,
      memory_context=memory_context,
    )

    yield {"type": "thought", "content": f"📋 [Plan]\n{plan}"}

    # ── Phase 2: Executor ──
    yield {"type": "thought", "content": "⚡ [Executor] Starting execution..."}

    executor_answer = ""
    max_review_rounds = 2  # 最多审查 2 轮

    for review_round in range(max_review_rounds):
      # 如果是重试，把 reviewer 的反馈加到问题里
      executor_question = question
      if review_round > 0:
        executor_question = (
          f"{question}\n\n"
          f"[REVIEWER FEEDBACK - Please address these issues]\n{reviewer_feedback}"
        )

      for event in run_executor(
        plan=plan,
        question=executor_question,
        user_id=user_id,
        file_id=file_id,
        history=history,
      ):
        if event["type"] == "executor_done":
          executor_answer = event["answer"]
          all_citations = event.get("citations", [])

        elif event["type"] == "citations":
          all_citations = event["citations"]
          yield event

        else:
          yield event

      # ── Phase 3: Reviewer ──
      yield {"type": "thought", "content": "🔍 [Reviewer] Reviewing the answer..."}

      review = run_reviewer(
        question=question,
        executor_answer=executor_answer,
      )

      if review["approved"]:
        yield {"type": "thought", "content": "✅ [Reviewer] Answer approved!"}
        final_answer = review["improved_answer"]
        break

      else:
        reviewer_feedback = review["feedback"]
        yield {
          "type": "thought",
          "content": f"⚠️ [Reviewer] Needs improvement: {reviewer_feedback}",
        }
        # 继续循环，让 Executor 根据反馈补充
        if review_round < max_review_rounds - 1:
          yield {"type": "thought", "content": "🔄 [Executor] Addressing reviewer feedback..."}
    else:
      # 审查轮次用完，使用最后一次的回答
      final_answer = review.get("improved_answer", executor_answer)

    # ── 输出最终回答 ──
    yield {"type": "citations", "citations": all_citations}

    chunk_size = 5
    for i in range(0, len(final_answer), chunk_size):
      yield {"type": "token", "token": final_answer[i:i + chunk_size]}

    yield {"type": "done", "answer": final_answer}

  return generate(), all_citations