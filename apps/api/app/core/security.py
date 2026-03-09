import jwt
from jwt import PyJWKClient
from fastapi import HTTPException
from app.core.config import settings

jwks_client = PyJWKClient(settings.CLERK_JWKS_URL)


def verify_clerk_token(token: str) -> dict:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")