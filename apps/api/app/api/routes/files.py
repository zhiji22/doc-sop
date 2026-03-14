"""
文件上传路由
实现「预签名上传」机制：后端不直接接收文件，而是生成一个临时 URL，前端直传 MinIO。
"""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.api.deps import get_current_user
from app.db.database import engine
from app.schemas.file import FileOut, PresignIn, PresignOut
from app.services.file_service import list_files_for_user
from app.services.storage_service import generate_upload_url

router = APIRouter(prefix="/v1/files", tags=["files"])


@router.post("/presign", response_model=PresignOut)
def presign_upload(body: PresignIn, user=Depends(get_current_user)):
    """
    预签名上传接口。
    流程：
      1. 生成唯一 file_id 和存储路径 storage_key
      2. 将文件元信息写入 files 表
      3. 向 MinIO 请求一个有效期 10 分钟的 PUT 预签名 URL
      4. 返回 file_id + upload_url → 前端拿 URL 直接 PUT 文件到 MinIO
    """
    user_id = user["user_id"]
    file_id = str(uuid.uuid4())
    # 防止文件名中的路径分隔符导致存储路径异常
    safe_name = body.filename.replace("\\", "_").replace("/", "_")
    # 存储路径格式: {用户ID}/{文件ID}/{安全文件名}，保证全局唯一
    storage_key = f"{user_id}/{file_id}/{safe_name}"

    # 先将文件元信息写入数据库（此时文件内容还没上传）
    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into public.files (id, user_id, filename, storage_key, mime, size, status)
                values (:id, :user_id, :filename, :storage_key, :mime, :size, 'uploaded')
            """),
            {
                "id": file_id,
                "user_id": user_id,
                "filename": body.filename,
                "storage_key": storage_key,
                "mime": body.mime,
                "size": body.size,
            },
        )

    # 生成 MinIO 预签名 URL，前端用这个 URL 直传文件
    upload_url = generate_upload_url(
        storage_key=storage_key,
        content_type=body.mime or "application/octet-stream",
    )

    return PresignOut(file_id=file_id, storage_key=storage_key, upload_url=upload_url)

@router.get("", response_model=list[FileOut])
def list_files(
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(get_current_user),
):
    return list_files_for_user(
        user_id=user["user_id"],
        limit=limit,
    )