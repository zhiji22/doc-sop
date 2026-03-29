"""
Agent 安全护栏模块。

三层防护：
1. 输入护栏（Input Guard） — 在 LLM 调用之前拦截危险/无效输入
2. 执行护栏（Execution Guard） — 在 Agent 执行过程中限制资源消耗
3. 输出护栏（Output Guard） — 在返回用户之前检查输出内容
"""
import re
import time


# ============================================================
# 配置常量
# ============================================================

MAX_INPUT_LENGTH = 10000          # 用户输入最大字符数
MAX_OUTPUT_LENGTH = 50000         # 输出最大字符数
MAX_TOOL_CALLS = 20               # 单次请求最大工具调用次数
MAX_REQUEST_TIMEOUT = 120         # 单次请求最大耗时（秒）
MAX_TOKENS_PER_REQUEST = 30000   # 单次请求最大 token 用量

# Prompt Injection 检测模式
INJECTION_PATTERNS = [
  r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
  r"disregard\s+(all\s+)?(previous|above|prior)",
  r"forget\s+(all\s+)?(previous|above|prior)\s+(instructions?|context)",
  r"you\s+are\s+now\s+(a|an)\s+",
  r"new\s+instructions?\s*:",
  r"system\s*prompt\s*:",
  r"act\s+as\s+(if\s+)?(you\s+are\s+)?",
  r"pretend\s+(to\s+be|you\s+are)",
  r"reveal\s+(your|the)\s+(system\s+)?(prompt|instructions?)",
  r"show\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions?)",
  r"what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions?|rules?)",
  r"output\s+(your|the)\s+(system|initial)\s+(prompt|message)",
  r"repeat\s+(the\s+)?(above|system)\s+(text|prompt|instructions?)",
]

# 敏感词列表（输入 + 输出通用）
# 你可以根据业务场景自行扩展
SENSITIVE_WORDS = [
  # 这里放你业务场景中需要过滤的词
  # 示例（可按需添加或清空）：
]

# ============================================================
# 第 1 层：输入护栏
# ============================================================

class InputGuardError(Exception):
  """输入护栏拦截异常"""
  pass


def check_input(question: str) -> str:
  """
  检查用户输入，通过则返回清理后的文本，不通过则抛 InputGuardError。
  
  检查项：
  1. 空输入
  2. 长度超限
  3. Prompt Injection 检测
  4. 敏感词检测
  """
  # 1. 空输入检查
  cleaned = question.strip()
  if not cleaned:
    raise InputGuardError("输入不能为空。")
  
  # 2. 长度检查
  if len(cleaned) > MAX_INPUT_LENGTH:
    raise InputGuardError(
      f"输入过长（{len(cleaned)} 字符），最大允许 {MAX_INPUT_LENGTH} 字符。"
      f"请精简你的问题。"
    )
  
  # 3. Prompt Injection 检测
  lower_text = cleaned.lower()
  for pattern in INJECTION_PATTERNS:
    if re.search(pattern, lower_text):
      raise InputGuardError(
        "检测到潜在的 prompt injection 攻击，请求已被拦截。"
        "请正常提问。"
      )
  
  # 4. 敏感词检测
  for word in SENSITIVE_WORDS:
    if word.lower() in lower_text:
      raise InputGuardError(
        "输入中包含敏感内容，请修改后重试。"
      )
  
  return cleaned


# ============================================================
# 第 2 层：执行护栏
# ============================================================

class ExecutionGuardError(Exception):
  """执行护栏拦截异常"""
  pass


class ExecutionGuard:
  """
  执行过程中的资源限制器。
  
  用法：
    guard = ExecutionGuard()
    
    # 每次工具调用前：
    guard.check_tool_call()
    
    # 每次 LLM 调用后：
    guard.add_tokens(usage_tokens)
    guard.check_tokens()
    
    # 每轮循环中：
    guard.check_timeout()
  """
  
  def __init__(
    self,
    max_tool_calls: int = MAX_TOOL_CALLS,
    max_timeout: int = MAX_REQUEST_TIMEOUT,
    max_tokens: int = MAX_TOKENS_PER_REQUEST,
  ):
    self.max_tool_calls = max_tool_calls
    self.max_timeout = max_timeout
    self.max_tokens = max_tokens
    
    self.tool_call_count = 0
    self.total_tokens = 0
    self.start_time = time.time()
  
  def check_tool_call(self):
    """工具调用前检查：是否超出调用次数上限"""
    self.tool_call_count += 1
    if self.tool_call_count > self.max_tool_calls:
      raise ExecutionGuardError(
        f"工具调用次数超出上限（{self.max_tool_calls} 次）。"
        f"Agent 可能陷入了循环，已自动终止。"
      )
  
  def add_tokens(self, tokens: int):
    """累计 token 用量"""
    self.total_tokens += tokens
  
  def check_tokens(self):
    """检查 token 用量是否超出上限"""
    if self.total_tokens > self.max_tokens:
      raise ExecutionGuardError(
        f"Token 用量超出上限（{self.total_tokens}/{self.max_tokens}）。"
        f"请缩短问题或减少分析范围。"
      )
  
  def check_timeout(self):
    """检查是否超时"""
    elapsed = time.time() - self.start_time
    if elapsed > self.max_timeout:
      raise ExecutionGuardError(
        f"请求超时（已运行 {int(elapsed)} 秒，上限 {self.max_timeout} 秒）。"
        f"请简化你的问题。"
      )


# ============================================================
# 第 3 层：输出护栏
# ============================================================

class OutputGuardError(Exception):
  """输出护栏拦截异常"""
  pass


def check_output(content: str) -> str:
  """
  检查 LLM 输出内容。
  通过则返回（可能裁剪后的）内容，不通过则返回替代内容。
  
  注意：输出护栏不抛异常（因为已经消耗了 token），而是替换内容。
  """
  if not content:
    return content
  
  # 1. 长度限制：截断过长的输出
  if len(content) > MAX_OUTPUT_LENGTH:
    content = content[:MAX_OUTPUT_LENGTH] + "\n\n⚠️ [输出过长，已截断]"
  
  # 2. 敏感词过滤
  lower_content = content.lower()
  for word in SENSITIVE_WORDS:
    if word.lower() in lower_content:
      return "⚠️ 回答中包含敏感内容，已被过滤。请换一个方式提问。"
  
  # 3. System Prompt 泄露检测
  # 如果 LLM 输出中包含了 system prompt 的关键片段，说明可能被 injection 攻击成功
  leakage_indicators = [
    "you are a document",
    "you are a planning agent",
    "you are a review agent",
    "your job is to analyze",
    "available tools that the executor",
  ]
  
  leaked_count = 0
  for indicator in leakage_indicators:
    if indicator in lower_content:
      leaked_count += 1
  
  # 如果匹配了 2 个以上的指示词，很可能是 system prompt 泄露
  if leaked_count >= 2:
    return "⚠️ 检测到异常输出，已被拦截。请正常提问。"
  
  return content