from io import BytesIO
from fastapi import HTTPException
from pypdf import PdfReader
from docx import Document


def parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages = []

    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[Page {idx}]\n{text}")

    return "\n\n".join(pages)


def parse_docx(file_bytes: bytes) -> str:
    doc = Document(BytesIO(file_bytes))
    paragraphs = []

    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def parse_document(filename: str, mime: str | None, file_bytes: bytes) -> str:
    lower_name = filename.lower()
    mime = mime or ""

    if lower_name.endswith(".pdf") or mime == "application/pdf":
        return parse_pdf(file_bytes)

    if lower_name.endswith(".docx") or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return parse_docx(file_bytes)

    raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX are supported for now.")


def truncate_text(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]