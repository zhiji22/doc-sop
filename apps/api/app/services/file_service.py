from sqlalchemy import text
from app.db.database import engine

def list_files_for_user(user_id: str, limit: int = 20):
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                select id, user_id, filename, storage_key, mime, size, status, created_at
                from public.files
                where user_id = :user_id
                order by created_at desc
                limit :limit
            """),
            {
                "user_id": user_id,
                "limit": limit,
            },
        ).mappings().all()

    result = []
    for row in rows:
        result.append({
            "id": str(row["id"]),
            "user_id": row["user_id"],
            "filename": row["filename"],
            "storage_key": row["storage_key"],
            "mime": row["mime"],
            "size": row["size"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })

    return result