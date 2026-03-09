import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.api.deps import get_current_user
from app.db.database import engine
from app.schemas.file import PresignIn, PresignOut
from app.services.storage_service import generate_upload_url

router = APIRouter(prefix="/v1/files", tags=["files"])


@router.post("/presign", response_model=PresignOut)
def presign_upload(body: PresignIn, user=Depends(get_current_user)):
    user_id = user["user_id"]
    file_id = str(uuid.uuid4())
    safe_name = body.filename.replace("\\", "_").replace("/", "_")
    storage_key = f"{user_id}/{file_id}/{safe_name}"

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

    upload_url = generate_upload_url(
        storage_key=storage_key,
        content_type=body.mime or "application/octet-stream",
    )

    return PresignOut(file_id=file_id, storage_key=storage_key, upload_url=upload_url)