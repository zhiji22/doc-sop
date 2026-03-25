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

# ============================================================
# 工具 3：获取文档大纲
# ============================================================

GET_DOCUMENT_OUTLINE_SCHEMA = {
  "type": "function",
  "function": {
    "name": "get_document_outline",
    "description": (
      "Get an outline/overview of the entire document. "
      "Returns the total number of chunks and a preview (first 80 characters) of each chunk. "
      "Use this FIRST when you need to understand the document's structure before diving into details."
    ),
    "parameters": {
      "type": "object",
      "properties": {},
      "required": [],
    },
  },
}

def execute_get_document_outline(user_id: str, file_id: str, arguments: dict) -> str:
  from app.services.rag_service import get_all_chunk_previews

  previews = get_all_chunk_previews(user_id=user_id, file_id=file_id)

  if not previews:
    return "No document chunks found. The document may not have been processed yet."

  lines = [f"Document has {len(previews)} chunks:\n"]
  for p in previews:
    lines.append(f"  [{p['chunk_index']}] {p['preview']}")

  return "\n".join(lines)


# ============================================================
# 工具 4：按索引读取指定段落
# ============================================================

READ_CHUNK_BY_INDEX_SCHEMA = {
  "type": "function",
  "function": {
    "name": "read_chunk_by_index",
    "description": (
      "Read the full content of a specific document chunk by its index number. "
      "Use this after get_document_outline to read specific sections in detail. "
      "The chunk_index is the number shown in square brackets in the outline."
    ),
    "parameters": {
      "type": "object",
      "properties": {
        "chunk_index": {
          "type": "integer",
          "description": "The index of the chunk to read (0-based).",
        },
      },
      "required": ["chunk_index"],
    },
  },
}

def execute_read_chunk_by_index(user_id: str, file_id: str, arguments: dict) -> str:
  from app.services.rag_service import get_chunk_by_index

  chunk_index = arguments.get("chunk_index", 0)
  chunk = get_chunk_by_index(user_id=user_id, file_id=file_id, chunk_index=chunk_index)

  if not chunk:
    return f"Chunk {chunk_index} not found."

  return f"[Chunk {chunk_index}]\n{chunk['content']}"


# ============================================================
# 工具 5：保存记忆
# ============================================================

SAVE_MEMORY_SCHEMA = {
  "type": "function",
  "function": {
    "name": "save_memory",
    "description": (
      "Save an important piece of information to long-term memory. "
      "Use this when the user explicitly asks you to remember something, "
      "or when you discover a key fact/insight during analysis that should be remembered for future conversations. "
      "Examples: user preferences, key findings, important facts about documents."
    ),
    "parameters": {
      "type": "object",
      "properties": {
        "content": {
          "type": "string",
          "description": "The information to remember. Be concise but complete.",
        },
        "category": {
          "type": "string",
          "enum": ["fact", "preference", "insight", "general"],
          "description": "Category of the memory. 'fact' for factual info, 'preference' for user preferences, 'insight' for analysis conclusions, 'general' for other.",
        },
      },
      "required": ["content"],
    },
  },
}

def execute_save_memory(user_id: str, file_id: str, arguments: dict) -> str:
  from app.services.memory_service import save_memory

  content = arguments.get("content", "")
  category = arguments.get("category", "general")

  result = save_memory(
    user_id=user_id,
    content=content,
    category=category,
    file_id=file_id,
  )
  return f"Memory saved successfully (category: {category}): {content}"


# ============================================================
# 工具 6：召回记忆
# ============================================================

RECALL_MEMORY_SCHEMA = {
  "type": "function",
  "function": {
    "name": "recall_memory",
    "description": (
      "Search your long-term memory for previously saved information. "
      "Use this when the user asks about something you discussed before, "
      "or when you need context from previous conversations. "
      "This searches across ALL past conversations and documents."
    ),
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "What to search for in memory. Be descriptive.",
        },
      },
      "required": ["query"],
    },
  },
}

def execute_recall_memory(user_id: str, file_id: str, arguments: dict) -> str:
  from app.services.memory_service import recall_memories

  query = arguments.get("query", "")
  memories = recall_memories(
    user_id=user_id,
    query=query,
    top_k=5,
    file_id=file_id,
  )
  
  if not memories:
    return "No relevant memories found."

  parts = []
  for m in memories:
    parts.append(f"[{m['category']}] (score: {m['score']:.2f}) {m['content']}")

  return "Found memories:\n" + "\n".join(parts)


ALL_TOOL_SCHEMAS = [
  SEARCH_DOCUMENT_SCHEMA,
  SUMMARIZE_TEXT_SCHEMA,
  GET_DOCUMENT_OUTLINE_SCHEMA,
  READ_CHUNK_BY_INDEX_SCHEMA,
  SAVE_MEMORY_SCHEMA,
  RECALL_MEMORY_SCHEMA,
]

TOOL_EXECUTORS = {
  "search_document": execute_search_document,
  "summarize_text": execute_summarize_text,
  "get_document_outline": execute_get_document_outline,
  "read_chunk_by_index": execute_read_chunk_by_index,
  "save_memory": execute_save_memory,
  "recall_memory": execute_recall_memory,
}