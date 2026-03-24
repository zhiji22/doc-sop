"""
文档解析服务
将上传的 PDF / DOCX 文件转换为纯文本，供 LLM 处理。
"""
from io import BytesIO
from fastapi import HTTPException
from pypdf import PdfReader
from docx import Document


def parse_pdf(file_bytes: bytes) -> str:
    """解析 PDF：逐页提取文本，每页标注页码 [Page N]"""
    reader = PdfReader(BytesIO(file_bytes))
    pages = []

    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[Page {idx}]\n{text}")

    return "\n\n".join(pages)


def parse_docx(file_bytes: bytes) -> str:
    """解析 DOCX：提取所有段落文本"""
    doc = Document(BytesIO(file_bytes))
    paragraphs = []

    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def parse_document(filename: str, mime: str | None, file_bytes: bytes) -> str:
    """
    统一入口：根据文件扩展名或 MIME 类型选择对应的解析器。
    目前支持 PDF 和 DOCX，其他格式返回 400 错误。
    """
    lower_name = filename.lower()
    mime = mime or ""

    if lower_name.endswith(".pdf") or mime == "application/pdf":
        raw = parse_pdf(file_bytes)
    elif lower_name.endswith(".docx") or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        raw = parse_docx(file_bytes)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX are supported for now.")

    # 去除 NUL 字节，PostgreSQL text 字段不允许 \x00
    return raw.replace("\x00", "")


def truncate_text(text: str, max_chars: int = 12000) -> str:
    """截断文本到指定长度，防止超出 LLM 上下文窗口限制"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]