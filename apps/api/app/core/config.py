"""
全局配置模块
从 .env 文件和环境变量中读取所有配置项，统一通过 settings 单例访问。
"""
import os
from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件到环境变量
load_dotenv()


class Settings:
    # ── 数据库 ──
    DATABASE_URL: str = os.environ["DATABASE_URL"]  # PostgreSQL 连接串，格式: postgresql+psycopg://user:pass@host:port/db

    # ── Clerk 认证 ──
    CLERK_JWKS_URL: str = os.environ["CLERK_JWKS_URL"]  # Clerk JWKS 端点，用于验证 JWT 签名
    WEB_ORIGIN: str = os.getenv("WEB_ORIGIN", "http://localhost:3000")  # 前端地址，用于 CORS 白名单

    # ── MinIO / S3 对象存储 ──
    STORAGE_ENDPOINT: str = os.environ["STORAGE_ENDPOINT"]  # MinIO 服务地址，如 http://localhost:9000
    STORAGE_ACCESS_KEY: str = os.environ["STORAGE_ACCESS_KEY"]
    STORAGE_SECRET_KEY: str = os.environ["STORAGE_SECRET_KEY"]
    STORAGE_BUCKET: str = os.environ["STORAGE_BUCKET"]  # 存储桶名称，如 doc-sop
    STORAGE_REGION: str = os.getenv("STORAGE_REGION", "us-east-1")

    # ── LLM 大模型 ──
    LLM_API_KEY: str = os.environ["LLM_API_KEY"]
    LLM_BASE_URL: str = os.environ["LLM_BASE_URL"]  # 兼容 OpenAI 格式的 API 地址（可对接阿里 Dashscope 等）
    LLM_MODEL: str = os.environ["LLM_MODEL"]  # 模型名称，如 qwen-plus

    PUBLIC_WEB_BASE_URL: str = os.getenv("PUBLIC_WEB_BASE_URL", "http://localhost:3000")

# 全局单例，其他模块通过 from app.core.config import settings 使用
settings = Settings()