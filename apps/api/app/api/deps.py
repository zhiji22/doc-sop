"""
公共依赖注入模块
提供 get_current_user 依赖，用于路由中自动完成：JWT 验证 → 用户识别 → 用户同步入库。
"""
import os

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text

from app.core.security import verify_clerk_token
from app.db.database import engine

# HTTPBearer 会自动从请求头 Authorization: Bearer <token> 中提取 token
security = HTTPBearer()

# 开发环境：设置 DEV_SKIP_AUTH=1 跳过 Clerk JWT 验证
# 在 /docs 页面 Authorize 框随便填一个值即可（如 "dev"）
_DEV_SKIP_AUTH = os.getenv("DEV_SKIP_AUTH", "0") == "1"


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """
    FastAPI 依赖项：验证当前请求的用户身份。
    流程：
      1. 从请求头提取 Bearer token
      2. 调用 Clerk JWKS 验证 token → 得到 payload
      3. 从 payload 中取出 user_id (sub) 和 email
      4. upsert 到 users 表（首次登录自动创建用户记录）
      5. 返回 {"user_id": ..., "email": ...} 供路由使用

    开发环境：DEV_SKIP_AUTH=1 时跳过验证，使用固定 dev 用户。
    """
    # ── 开发环境跳过 JWT 验证 ──
    if _DEV_SKIP_AUTH:
        dev_user_id = "dev-user"
        dev_email = "dev@localhost"
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO public.users (id, email)
                    VALUES (:id, :email)
                    ON CONFLICT (id) DO UPDATE SET email = excluded.email
                """),
                {"id": dev_user_id, "email": dev_email},
            )
        return {"user_id": dev_user_id, "email": dev_email}

    # ── 正式验证流程 ──
    payload = verify_clerk_token(creds.credentials)
    user_id = payload.get("sub")  # Clerk 的 sub 字段就是用户唯一 ID
    if not user_id:
        raise Exception("Missing sub in token")

    email = payload.get("email")

    # upsert: 用户不存在则插入，已存在则更新 email（保持最新）
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO public.users (id, email)
                VALUES (:id, :email)
                ON CONFLICT (id) DO UPDATE SET email = excluded.email
            """),
            {"id": user_id, "email": email},
        )

    return {"user_id": user_id, "email": email}