import os
import time
import uuid
import json
from io import BytesIO

import jwt
from jwt import PyJWKClient
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import boto3
from pypdf import PdfReader
from docx import Document
from openai import OpenAI


load_dotenv(override=True)

DATABASE_URL = os.environ["DATABASE_URL"]
CLERK_JWKS_URL = os.environ["CLERK_JWKS_URL"]
WEB_ORIGIN = os.getenv("WEB_ORIGIN", "http://localhost:3000")

STORAGE_ENDPOINT = os.environ["STORAGE_ENDPOINT"]
STORAGE_ACCESS_KEY = os.environ["STORAGE_ACCESS_KEY"]
STORAGE_SECRET_KEY = os.environ["STORAGE_SECRET_KEY"]
STORAGE_BUCKET = os.environ["STORAGE_BUCKET"]
STORAGE_REGION = os.getenv("STORAGE_REGION", "us-east-1")

LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_BASE_URL = os.environ["LLM_BASE_URL"]
LLM_MODEL = os.environ["LLM_MODEL"]


engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="doc-sop-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEB_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()
jwks_client = PyJWKClient(CLERK_JWKS_URL)

llm_client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
)

def get_db():
    return engine

def verify_clerk_token(token: str) -> dict:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            # 本地开发环境下，允许客户端和服务器时间有最多 5 分钟偏差
            leeway=300,
        )

        return payload

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# 获取当前用户
def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_clerk_token(creds.credentials)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing sub in token")

    email = payload.get("email")
    # upsert user
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

# ---------- S3 client ----------
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY,
        aws_secret_access_key=STORAGE_SECRET_KEY,
        region_name=STORAGE_REGION,
    )

# 从S3下载文件
def download_file_bytes(storage_key: str) -> bytes:
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=STORAGE_BUCKET, Key=storage_key)
    return obj["Body"].read()

# 解析PDF
def parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages = []

    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append(f"[Page {idx}]\n{text}")

    return "\n\n".join(pages)

# 解析 DOCX
def parse_docx(file_bytes: bytes) -> str:
    doc = Document(BytesIO(file_bytes))
    paragraphs = []

    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)

# 统一解析入口
def parse_document(filename: str, mime: str | None, file_bytes: bytes) -> str:
    lower_name = filename.lower()
    mime = mime or ""

    if lower_name.endswith(".pdf") or mime == "application/pdf":
        return parse_pdf(file_bytes)

    if lower_name.endswith(".docx") or mime in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }:
        return parse_docx(file_bytes)

    raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX are supported for now.")

# 截断文本，避免文档太长
def truncate_text(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]

# sop prompt生成函数
def build_sop_prompt(document_text: str, template: str) -> str:
    if template == "checklist":
        instruction = """
            You are an expert operations analyst.
            Extract a practical checklist from the document.

            Return JSON with this exact structure:
            {
            "title": "string",
            "overview": "string",
            "checklist": ["string", "string"],
            "open_questions": ["string", "string"]
            }
            """
    elif template == "summary":
        instruction = """
            You are an expert document analyst.
            Summarize the document into a structured operational summary.

            Return JSON with this exact structure:
            {
            "title": "string",
            "overview": "string",
            "key_points": ["string", "string"],
            "risks": ["string", "string"],
            "open_questions": ["string", "string"]
            }
            """
    else:
        instruction = """
            You are an expert operations analyst.
            Convert the document into a practical SOP.

            Return JSON with this exact structure:
            {
            "title": "string",
            "overview": "string",
            "steps": [
                {
                "step": 1,
                "action": "string",
                "owner": "string",
                "inputs": "string",
                "outputs": "string",
                "risks": ["string", "string"]
                }
            ],
            "checklist": ["string", "string"],
            "open_questions": ["string", "string"]
            }
            """
    return f"""
        {instruction}
        Rules:
        1. Only use information from the document.
        2. If some information is missing, use "Unknown".
        3. Be practical and concise.
        4. Output valid JSON only. Do not wrap in markdown fences.

        Document:
        \"\"\"
        {document_text}
        \"\"\"
        """

# 调用LLM 生成JSON
def generate_structured_output(document_text: str, template: str) -> tuple[dict, int]:
    prompt = build_sop_prompt(document_text=document_text, template=template)

    resp = llm_client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You convert documents into structured JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    content = resp.choices[0].message.content
    usage_tokens = 0
    if getattr(resp, "usage", None):
        usage_tokens = getattr(resp.usage, "total_tokens", 0) or 0

    try:
        result = json.loads(content)
    except Exception:
        raise HTTPException(status_code=500, detail=f"Model did not return valid JSON: {content}")

    return result, usage_tokens


# ---------- API endpoints ----------
class PresignIn(BaseModel):
    filename: str
    mime: str | None = None
    size: int | None = None

class PresignOut(BaseModel):
    file_id: str
    storage_key: str
    upload_url: str

class CreateRunIn(BaseModel):
    file_id: str
    template: str  # sop | checklist | summary

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


@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}

@app.post("/v1/files/presign", response_model=PresignOut)
def presign_upload(body: PresignIn, user=Depends(get_current_user)):
    user_id = user["user_id"]
    file_id = str(uuid.uuid4())
    safe_name = body.filename.replace("\\", "_").replace("/", "_")
    storage_key = f"{user_id}/{file_id}/{safe_name}"

    # 1) 写files记录（状态upload/processing）先uploaded
    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into public.files (id, user_id, filename, storage_key, mime, size, status)
                values (:id, :user_id, :filename, :storage_key, :mime, :size, 'uploaded')
            """),
            {
                "id": file_id,
                "user_id": user_id,
                "filename": body.filename,
                "storage_key": storage_key,
                "mime": body.mime,
                "size": body.size,
            },
        )

    # 2)生成presigned PUT url
    s3 = get_s3_client()
    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": STORAGE_BUCKET,
            "Key": storage_key,
            "ContentType": body.mime or "application/octet-stream"
        },
        ExpiresIn=600,  # 10 min
    )

    return PresignOut(file_id=file_id, storage_key=storage_key, upload_url=upload_url)


@app.post("/v1/runs", response_model=RunOut)
def create_run(body: CreateRunIn, user=Depends(get_current_user)):
    user_id = user["user_id"]

    if body.template not in {"sop", "checklist", "summary"}:
        raise HTTPException(status_code=400, detail="template must be one of: sop, checklist, summary")

    # 1. 查文件是否属于当前用户
    with engine.begin() as conn:
        file_row = conn.execute(
            text("""
                select id, user_id, filename, storage_key, mime, size, status
                from public.files
                where id = :file_id and user_id = :user_id
            """),
            {"file_id": body.file_id, "user_id": user_id},
        ).mappings().first()

    if not file_row:
        raise HTTPException(status_code=404, detail="File not found")

    run_id = str(uuid.uuid4())

    # 2. 先插入 run
    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into public.runs (id, user_id, file_id, template, status)
                values (:id, :user_id, :file_id, :template, 'running')
            """),
            {
                "id": run_id,
                "user_id": user_id,
                "file_id": body.file_id,
                "template": body.template,
            },
        )
    
    try:
        # 3. 下载并解析文件
        file_bytes = download_file_bytes(file_row["storage_key"])
        raw_text = parse_document(
            filename=file_row["filename"],
            mime=file_row["mime"],
            file_bytes=file_bytes,
        ).strip()

        if not raw_text:
            raise HTTPException(status_code=400, detail="Document text is empty after parsing")

        # 4. 截断，避免太长
        prompt_text = truncate_text(raw_text, max_chars=12000)

        # 5. 调模型
        result_json, usage_tokens = generate_structured_output(
            document_text=prompt_text,
            template=body.template,
        )

        # 6. 粗糙的成本估算
        cost_usd = round((usage_tokens / 1000) * 0.001, 6)

        # 7. 写回成功结果
        with engine.begin() as conn:
            conn.execute(
                text("""
                    update public.runs
                    set status = 'done',
                        result_json = :result_json,
                        usage_tokens = :usage_tokens,
                        cost_usd = :cost_usd
                    where id = :run_id and user_id = :user_id
                """),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "result_json": json.dumps(result_json, ensure_ascii=False),
                    "usage_tokens": usage_tokens,
                    "cost_usd": cost_usd,
                },
            )

        return RunOut(
            id=run_id,
            user_id=user_id,
            file_id=body.file_id,
            template=body.template,
            status="done",
            result_json=result_json,
            error=None,
            usage_tokens=usage_tokens,
            cost_usd=cost_usd,
        )

    except HTTPException as e:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    update public.runs
                    set status = 'failed',
                        error = :error
                    where id = :run_id and user_id = :user_id
                """),
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
                text("""
                    update public.runs
                    set status = 'failed',
                        error = :error
                    where id = :run_id and user_id = :user_id
                """),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user=Depends(get_current_user)):
    user_id = user["user_id"]

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                select id, user_id, file_id, template, status, result_json, error, usage_tokens, cost_usd
                from public.runs
                where id = :run_id and user_id = :user_id
            """),
            {
                "run_id": run_id,
                "user_id": user_id,
            },
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunOut(
        id=str(row["id"]),
        user_id=row["user_id"],
        file_id=str(row["file_id"]),
        template=row["template"],
        status=row["status"],
        result_json=row["result_json"],
        error=row["error"],
        usage_tokens=row["usage_tokens"],
        cost_usd=float(row["cost_usd"]) if row["cost_usd"] is not None else None,
    )