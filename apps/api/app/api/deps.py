from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text

from app.core.security import verify_clerk_token
from app.db.database import engine

security = HTTPBearer()


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_clerk_token(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise Exception("Missing sub in token")

    email = payload.get("email")

    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into public.users (id, email)
                values (:id, :email)
                on conflict (id) do update set email = excluded.email
            """),
            {"id": user_id, "email": email},
        )

    return {"user_id": user_id, "email": email}