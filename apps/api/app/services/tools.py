"""
工具定义模块
定义所有 LLM 可以调用的工具（函数）。

每个工具需要两部分：
1. tool_schema —— JSON Schema 格式的描述，告诉 LLM 这个工具是干什么的、需要什么参数
2. tool_function —— 实际执行逻辑
"""
import json



# 工具1：搜索文档

SEARCH_DOCUMENT_SCHEMA = {
  "type": "function",
  "function": {
    "name": "search_document",
    "description": "Search the uploaded document for information relevant to a query. Use this when you need to find specific information from the document to answer the user's question.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "The search query to find relevant content in the document. Be specific and descriptive.",
        },
      },
      "required": ["query"],
    },
  },
}

def execute_search_document(user_id: str, file_id: str, arguments: dict) -> str:
  """
  执行文档搜索工具。
  
  参数:
    - user_id, file_id: 确定搜索哪个用户的哪个文件
    - arguments: LLM 传过来的参数，包含 query 字段
  
  返回:
    - 搜索结果的文本（会被传回给 LLM 作为工具调用的结果）
  """
  from app.services.rag_service import retrieve_relevant_chunks
  
  query = arguments.get("query", "")

  chunks = retrieve_relevant_chunks(
    user_id=user_id,
    file_id=file_id,
    question=query,
    top_k=4,
  )

  if not chunks:
    return "No relevant content found in the document."

  # 把搜索到的文档块拼成文本返回给LLM
  result_parts = []
  for chunk in chunks:
    result_parts.append(
      f"[Chunk {chunk['chunk_index']}] (relevance: {chunk['score']:.2f})\n{chunk['content']}"
    )

  return "\n\n---\n\n".join(result_parts)


# ============================================================
# 工具 2：总结文本
# ============================================================

SUMMARIZE_TEXT_SCHEMA = {
  "type": "function",
  "function": {
    "name": "summarize_text",
    "description": "Summarize a piece of text into key points. Use this when the user asks for a summary or when you need to condense information.",
    "parameters": {
      "type": "object",
      "properties": {
        "text": {
          "type": "string",
          "description": "The text to summarize.",
        },
        "style": {
          "type": "string",
          "enum": ["bullet_points", "paragraph", "one_sentence"],
          "description": "The style of summary to generate.",
        },
      },
      "required": ["text"],
    },
  },
}

def execute_summarize_text(arguments: dict) -> str:
  """
  总结文本工具。
  注意：这个工具不调用 LLM，而是直接返回文本让 LLM 自己总结。
  这样设计是因为 LLM 本身就擅长总结，不需要再调一次 LLM。
  工具的价值在于"告诉 LLM 用户想要总结"，让 LLM 知道该怎么组织回答。
  """
  text = arguments.get("text", "")
  style = arguments.get("style", "bullet_points")

  # 直接返回文本和风格提示，让LLM在最终回答中总结
  return f"[Summarize the following text in {style} style]:\n\n{text}"

#============= 注册工具
ALL_TOOL_SCHEMAS = [
  SEARCH_DOCUMENT_SCHEMA,
  SUMMARIZE_TEXT_SCHEMA,
]

# 工具名 -> 函数
TOOL_EXECUTORS = {
  "search_document": execute_search_document,
  "summarize_text": execute_summarize_text,
}

