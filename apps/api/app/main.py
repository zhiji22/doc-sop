"""
FastAPI 应用入口
负责：应用初始化、中间件配置、路由挂载、启动时资源初始化。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.files import router as files_router
from app.api.routes.runs import router as runs_router
from app.api.routes.qa import router as qa_router
from app.api.routes.traces import router as traces_router
from app.services.storage_service import get_s3_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：
    - 启动时：自动检查并创建 MinIO 存储桶
    - 关闭时：yield 之后可放清理逻辑（当前无需）
    """
    try:
        s3 = get_s3_client()
        s3.head_bucket(Bucket=settings.STORAGE_BUCKET)
        print(f"[startup] Bucket '{settings.STORAGE_BUCKET}' is ready.")
    except s3.exceptions.NoSuchBucket:
        try:
            s3.create_bucket(Bucket=settings.STORAGE_BUCKET)
            print(f"[startup] Created bucket: {settings.STORAGE_BUCKET}")
        except Exception as e:
            print(f"[startup] WARNING: Failed to create bucket: {e}")
    except Exception as e:
        print(f"[startup] WARNING: MinIO not available, skipping bucket check: {e}")
    yield


app = FastAPI(title="doc-sop-api", lifespan=lifespan)

# CORS 中间件：允许前端（localhost:3000）跨域访问后端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEB_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """健康检查接口，用于确认服务是否正常运行"""
    return {"ok": True}


# 挂载业务路由
app.include_router(files_router)   # /v1/files/*  文件上传相关
app.include_router(runs_router)    # /v1/runs/*   生成任务相关
app.include_router(qa_router)      # /v1/qa/*    问答相关
app.include_router(traces_router)  # /v1/traces/*  Agent可观察性
