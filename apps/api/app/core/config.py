import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.environ["DATABASE_URL"]

    CLERK_JWKS_URL: str = os.environ["CLERK_JWKS_URL"]
    WEB_ORIGIN: str = os.getenv("WEB_ORIGIN", "http://localhost:3000")

    STORAGE_ENDPOINT: str = os.environ["STORAGE_ENDPOINT"]
    STORAGE_ACCESS_KEY: str = os.environ["STORAGE_ACCESS_KEY"]
    STORAGE_SECRET_KEY: str = os.environ["STORAGE_SECRET_KEY"]
    STORAGE_BUCKET: str = os.environ["STORAGE_BUCKET"]
    STORAGE_REGION: str = os.getenv("STORAGE_REGION", "us-east-1")

    LLM_API_KEY: str = os.environ["LLM_API_KEY"]
    LLM_BASE_URL: str = os.environ["LLM_BASE_URL"]
    LLM_MODEL: str = os.environ["LLM_MODEL"]


settings = Settings()