"""
生成任务（Run）相关的请求/响应数据模型
用于 /v1/runs 接口的参数校验和返回值序列化。
"""
from pydantic import BaseModel


class CreateRunIn(BaseModel):
    """创建生成任务 - 请求体"""
    file_id: str    # 要处理的文件 ID（来自 presign 接口返回的 file_id）
    template: str   # 模板类型：sop | checklist | summary


class RunOut(BaseModel):
    """生成任务 - 响应体"""
    id: str                             # 任务 ID
    user_id: str                        # 所属用户
    file_id: str                        # 关联的文件 ID
    template: str                       # 使用的模板类型
    status: str                         # 任务状态：running | done | failed
    result_json: dict | None = None     # LLM 生成的结构化 JSON 结果
    error: str | None = None            # 失败时的错误信息
    usage_tokens: int | None = None     # LLM 消耗的 token 数
    cost_usd: float | None = None       # 估算费用（美元）