from pydantic import BaseModel


class WorkflowStepConfig(BaseModel):
  """工作流中的一个步骤"""
  tool: str = ""                    # 要调用的工具名，如 "search_document"
  description: str = ""             # 这一步的描述
  query_template: str = ""          # 搜索模板（用于 search_document）
  chunk_index: int | None = None    # 段落索引（用于 read_chunk_by_index）
  synthesize: bool = False          # 是否是汇总步骤（最后一步）


class WorkflowConfig(BaseModel):
  """完整的工作流配置"""
  system_prompt: str = ""                       # 自定义 system prompt
  steps: list[WorkflowStepConfig] = []          # 执行步骤列表
  temperature: float = 0.2                      # LLM 温度
  max_iterations: int = 10                      # 最大循环次数


class CreateWorkflowIn(BaseModel):
  """创建工作流的请求"""
  name: str
  description: str = ""
  config: WorkflowConfig


class UpdateWorkflowIn(BaseModel):
  """更新工作流的请求"""
  name: str | None = None
  description: str | None = None
  config: WorkflowConfig | None = None


class RunWorkflowIn(BaseModel):
  """执行工作流的请求"""
  file_id: str
  workflow_id: str
  question: str = ""    # 可选的额外问题/指令