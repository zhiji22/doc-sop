import json
import uuid
from fastapi import HTTPException
from sqlalchemy import text

from app.db.database import engine
from app.services.storage_service import download_file_bytes
from app.services.document_service import parse_document, truncate_text
from app.services.llm_service import generate_structured_output


VALID_TEMPLATES = {"sop", "checklist", "summary"}


def create_run_record(user_id: str, file_id: str, template: str):
    if template not in VALID_TEMPLATES:
        raise HTTPException(status_code=400, detail="template must be one of: sop, checklist, summary")

    with engine.begin() as conn:
        file_row = conn.execute(
            text("""
                select id, user_id, filename, storage_key, mime, size, status
                from public.files
                where id = :file_id and user_id = :user_id
            """),
            {"file_id": file_id, "user_id": user_id},
        ).mappings().first()

    if not file_row:
        raise HTTPException(status_code=404, detail="File not found")

    run_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into public.runs (id, user_id, file_id, template, status)
                values (:id, :user_id, :file_id, :template, 'queued')
            """),
            {
                "id": run_id,
                "user_id": user_id,
                "file_id": file_id,
                "template": template,
            },
        )

    return {
        "id": run_id,
        "user_id": user_id,
        "file_id": file_id,
        "template": template,
        "status": "queued",
        "result_json": None,
        "error": None,
        "usage_tokens": None,
        "cost_usd": None,
    }


def process_run(run_id: str, user_id: str):
    # 1. 先把任务标记为 running，并取出文件信息
    with engine.begin() as conn:
        run_row = conn.execute(
            text("""
                select r.id, r.user_id, r.file_id, r.template, r.status,
                       f.filename, f.storage_key, f.mime, f.size
                from public.runs r
                join public.files f on r.file_id = f.id
                where r.id = :run_id and r.user_id = :user_id
            """),
            {"run_id": run_id, "user_id": user_id},
        ).mappings().first()

        if not run_row:
            return

        conn.execute(
            text("""
                update public.runs
                set status = 'running',
                    error = null
                where id = :run_id and user_id = :user_id
            """),
            {"run_id": run_id, "user_id": user_id},
        )

    try:
        # 2. 下载文件
        file_bytes = download_file_bytes(run_row["storage_key"])

        # 3. 解析文档
        raw_text = parse_document(
            filename=run_row["filename"],
            mime=run_row["mime"],
            file_bytes=file_bytes,
        ).strip()

        if not raw_text:
            raise HTTPException(status_code=400, detail="Document text is empty after parsing")

        # 4. 截断
        prompt_text = truncate_text(raw_text, max_chars=12000)

        # 5. 生成结构化结果
        result_json, usage_tokens = generate_structured_output(
            document_text=prompt_text,
            template=run_row["template"],
        )

        # 6. 粗略成本估算
        cost_usd = round((usage_tokens / 1000) * 0.001, 6)

        # 7. 写回 done
        with engine.begin() as conn:
            conn.execute(
                text("""
                    update public.runs
                    set status = 'done',
                        result_json = :result_json,
                        usage_tokens = :usage_tokens,
                        cost_usd = :cost_usd,
                        error = null
                    where id = :run_id and user_id = :user_id
                """),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "result_json": json.dumps(result_json, ensure_ascii=False),
                    "usage_tokens": usage_tokens,
                    "cost_usd": cost_usd,
                },
            )

    except HTTPException as e:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    update public.runs
                    set status = 'failed',
                        error = :error
                    where id = :run_id and user_id = :user_id
                """),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "error": e.detail,
                },
            )

    except Exception as e:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    update public.runs
                    set status = 'failed',
                        error = :error
                    where id = :run_id and user_id = :user_id
                """),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )


def get_run_for_user(user_id: str, run_id: str):
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                select id, user_id, file_id, template, status, result_json, error, usage_tokens, cost_usd, created_at
                from public.runs
                where id = :run_id and user_id = :user_id
            """),
            {"run_id": run_id, "user_id": user_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "id": str(row["id"]),
        "user_id": row["user_id"],
        "file_id": str(row["file_id"]),
        "template": row["template"],
        "status": row["status"],
        "result_json": row["result_json"],
        "error": row["error"],
        "usage_tokens": row["usage_tokens"],
        "cost_usd": float(row["cost_usd"]) if row["cost_usd"] is not None else None,
    }


def list_runs_for_user(user_id: str, limit: int = 20):
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                select id, user_id, file_id, template, status, result_json, error, usage_tokens, cost_usd, created_at
                from public.runs
                where user_id = :user_id
                order by created_at desc
                limit :limit
            """),
            {"user_id": user_id, "limit": limit},
        ).mappings().all()

    result = []
    for row in rows:
        result.append({
            "id": str(row["id"]),
            "user_id": row["user_id"],
            "file_id": str(row["file_id"]),
            "template": row["template"],
            "status": row["status"],
            "result_json": row["result_json"],
            "error": row["error"],
            "usage_tokens": row["usage_tokens"],
            "cost_usd": float(row["cost_usd"]) if row["cost_usd"] is not None else None,
        })
    return result