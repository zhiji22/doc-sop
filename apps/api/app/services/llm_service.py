import json
from fastapi import HTTPException
from openai import OpenAI
from app.core.config import settings

llm_client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
)


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


def generate_structured_output(document_text: str, template: str) -> tuple[dict, int]:
    prompt = build_sop_prompt(document_text=document_text, template=template)

    resp = llm_client.chat.completions.create(
        model=settings.LLM_MODEL,
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