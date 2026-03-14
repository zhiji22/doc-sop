"""
文件相关的请求/响应数据模型（Pydantic Schema）
用于 /v1/files/presign 接口的参数校验和返回值序列化。
"""
from pydantic import BaseModel


class PresignIn(BaseModel):
    """预签名上传 - 请求体"""
    filename: str              # 原始文件名，如 "报告.pdf"
    mime: str | None = None    # MIME 类型，如 "application/pdf"
    size: int | None = None    # 文件大小（字节）


class PresignOut(BaseModel):
    """预签名上传 - 响应体"""
    file_id: str       # 服务端生成的文件唯一 ID
    storage_key: str   # MinIO 中的存储路径
    upload_url: str    # 预签名上传 URL，前端用它 PUT 文件