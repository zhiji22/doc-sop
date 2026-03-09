from pydantic import BaseModel


class PresignIn(BaseModel):
    filename: str
    mime: str | None = None
    size: int | None = None


class PresignOut(BaseModel):
    file_id: str
    storage_key: str
    upload_url: str