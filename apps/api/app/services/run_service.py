import json
import uuid
from fastapi import HTTPException
from sqlalchemy import text

from app.db.database import engine
from app.services.storage_service import download_file_bytes
from app.services.document_service import parse_document, truncate_text
from app.services.llm_service import generate_structured_output


def create_run_for_user(user_id: str, file_id: str, template: str):
    if template not in {"sop", "checklist", "summary"}:
        raise HTTPException(status_code=400, detail="template must be one of: sop, checklist, summary")

    with engine.begin() as conn:
        file_row = conn.execute(
            text(
                """
                select id, user_id, filename, storage_key, mime, size, status
                from public.files
                where id = :file_id and user_id = :user_id
                """
            ),
            {"file_id": file_id, "user_id": user_id},
        ).mappings().first()

    if not file_row:
        raise HTTPException(status_code=404, detail="File not found")

    run_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                insert into public.runs (id, user_id, file_id, template, status)
                values (:id, :user_id, :file_id, :template, 'running')
                """
            ),
            {
                "id": run_id,
                "user_id": user_id,
                "file_id": file_id,
                "template": template,
            },
        )

    try:
        file_bytes = download_file_bytes(file_row["storage_key"])
        raw_text = parse_document(
            filename=file_row["filename"],
            mime=file_row["mime"],
            file_bytes=file_bytes,
        ).strip()

        if not raw_text:
            raise HTTPException(status_code=400, detail="Document text is empty after parsing")

        prompt_text = truncate_text(raw_text, max_chars=12000)
        result_json, usage_tokens = generate_structured_output(prompt_text, template)

        cost_usd = round((usage_tokens / 1000) * 0.001, 6)

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    update public.runs
                    set status = 'done',
                        result_json = :result_json,
                        usage_tokens = :usage_tokens,
                        cost_usd = :cost_usd
                    where id = :run_id and user_id = :user_id
                    """
                ),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "result_json": json.dumps(result_json, ensure_ascii=False),
                    "usage_tokens": usage_tokens,
                    "cost_usd": cost_usd,
                },
            )

        return {
            "id": run_id,
            "user_id": user_id,
            "file_id": file_id,
            "template": template,
            "status": "done",
            "result_json": result_json,
            "error": None,
            "usage_tokens": usage_tokens,
            "cost_usd": cost_usd,
        }

    except HTTPException as e:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    update public.runs
                    set status = 'failed',
                        error = :error
                    where id = :run_id and user_id = :user_id
                    """
                ),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "error": e.detail,
                },
            )
        raise e

    except Exception as e:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    update public.runs
                    set status = 'failed',
                        error = :error
                    where id = :run_id and user_id = :user_id
                    """
                ),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )
        raise HTTPException(status_code=500, detail=str(e))


def get_run_for_user(user_id: str, run_id: str):
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                select id, user_id, file_id, template, status, result_json, error, usage_tokens, cost_usd
                from public.runs
                where id = :run_id and user_id = :user_id
                """
            ),
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