"""
生成任务（Run）核心业务逻辑
这是整个系统最关键的模块，串联了：文件下载 → 文档解析 → LLM 生成 → 结果持久化。
"""
import json
import uuid
from fastapi import HTTPException
from sqlalchemy import text

from app.db.database import engine
from app.services.storage_service import download_file_bytes
from app.services.document_service import parse_document, truncate_text
from app.services.llm_service import generate_structured_output


def create_run_for_user(user_id: str, file_id: str, template: str):
    """
    创建并执行一次生成任务（同步）。
    完整流程：
      1. 校验模板类型
      2. 查询文件记录，确认文件属于当前用户
      3. 在 runs 表中创建一条 status='running' 的记录
      4. 从 MinIO 下载文件 → 解析为纯文本 → 截断 → 送入 LLM
      5. 成功 → 更新 runs 状态为 'done'，保存结果
      6. 失败 → 更新 runs 状态为 'failed'，记录错误信息
    """

    # ── 第 1 步：校验模板 ──
    if template not in {"sop", "checklist", "summary"}:
        raise HTTPException(status_code=400, detail="template must be one of: sop, checklist, summary")

    # ── 第 2 步：查询文件记录（同时校验归属权） ──
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

    # ── 第 3 步：创建 run 记录，初始状态为 running ──
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
        # ── 第 4 步：下载文件 → 解析 → 截断 ──
        file_bytes = download_file_bytes(file_row["storage_key"])
        raw_text = parse_document(
            filename=file_row["filename"],
            mime=file_row["mime"],
            file_bytes=file_bytes,
        ).strip()

        if not raw_text:
            raise HTTPException(status_code=400, detail="Document text is empty after parsing")

        # 截断到 12000 字符，防止超出 LLM 上下文限制
        prompt_text = truncate_text(raw_text, max_chars=12000)

        # ── 第 5 步：调用 LLM 生成结构化结果 ──
        result_json, usage_tokens = generate_structured_output(prompt_text, template)

        # 简单估算费用：每 1000 token 按 $0.001 计算
        cost_usd = round((usage_tokens / 1000) * 0.001, 6)

        # ── 第 6 步：成功，更新 run 状态为 done ──
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

    # ── 异常处理：将 run 标记为 failed 并记录错误 ──
    except HTTPException as e:
        # 业务异常（如文档为空），保留原始状态码
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
        # 未预期的异常（如 LLM 超时），统一返回 500
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
    """查询某次 run 的详情，仅返回属于当前用户的记录"""
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