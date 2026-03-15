from pydantic import BaseModel


class CreateRunIn(BaseModel):
    file_id: str
    template: str


class RunOut(BaseModel):
    id: str
    user_id: str
    file_id: str
    template: str
    status: str
    result_json: dict | None = None
    error: str | None = None
    usage_tokens: int | None = None
    cost_usd: float | None = None
    share_id: str | None = None
    is_public: bool = False


class ShareRunOut(BaseModel):
    share_id: str
    share_url: str
    is_public: bool


class PublicRunOut(BaseModel):
    id: str
    template: str
    status: str
    result_json: dict | None = None
    error: str | None = None
    share_id: str | None = None