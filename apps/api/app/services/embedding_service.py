from openai import OpenAI
from app.core.config import settings

embedding_client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
)

EMBEDDING_MODEL = settings.EMBEDDING_MODEL


def get_embedding(text: str) -> list[float]:
    resp = embedding_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return resp.data[0].embedding