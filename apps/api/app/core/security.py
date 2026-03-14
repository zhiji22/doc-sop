"""
Clerk JWT 验证模块
前端登录后，Clerk 会在请求头中附带 JWT token；
后端通过 JWKS（JSON Web Key Set）公钥验证 token 的合法性，提取用户信息。
"""
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException
from app.core.config import settings

# 初始化 JWKS 客户端，自动从 Clerk 拉取公钥并缓存
jwks_client = PyJWKClient(settings.CLERK_JWKS_URL)


def verify_clerk_token(token: str) -> dict:
    """
    验证 Clerk 签发的 JWT token。
    成功 → 返回 payload（包含 sub=用户ID, email 等）
    失败 → 抛出 401 异常
    """
    try:
        # 根据 token header 中的 kid 找到对应的签名公钥
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        # 用 RS256 算法解码并验证 token
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk token 不含 aud，跳过验证
        )
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")