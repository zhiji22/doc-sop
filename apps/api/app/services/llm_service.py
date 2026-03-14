"""
LLM 服务模块
调用大语言模型（兼容 OpenAI 接口），将文档文本转换为结构化 JSON。
支持三种模板：SOP（标准操作流程）、Checklist（检查清单）、Summary（摘要）。
"""
import json
from fastapi import HTTPException
from openai import OpenAI
from app.core.config import settings

# 初始化 OpenAI 兼容客户端（实际可对接阿里 Dashscope、本地 LLM 等）
llm_client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
)


def build_sop_prompt(document_text: str, template: str) -> str:
    """
    根据模板类型构建 prompt。
    每种模板定义了不同的 JSON 输出结构，引导 LLM 生成对应格式的结果。
    """
    if template == "checklist":
        # 检查清单模板：提取可操作的检查项
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
        # 摘要模板：提炼关键信息和风险点
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
        # SOP 模板（默认）：生成分步操作流程
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

    # 组合完整 prompt：指令 + 规则 + 文档内容
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
    """
    调用 LLM 生成结构化输出。
    参数:
      - document_text: 文档纯文本（已截断到 12000 字符以内）
      - template: 模板类型
    返回:
      - (result_dict, usage_tokens): 解析后的 JSON 字典 + token 消耗量
    """
    prompt = build_sop_prompt(document_text=document_text, template=template)

    # 调用 LLM，指定 response_format 强制返回 JSON
    resp = llm_client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=0.2,  # 低温度 → 更确定性的输出
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You convert documents into structured JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    content = resp.choices[0].message.content

    # 统计 token 消耗（用于计费）
    usage_tokens = 0
    if getattr(resp, "usage", None):
        usage_tokens = getattr(resp.usage, "total_tokens", 0) or 0

    # 将 LLM 返回的 JSON 字符串解析为字典
    try:
        result = json.loads(content)
    except Exception:
        raise HTTPException(status_code=500, detail=f"Model did not return valid JSON: {content}")

    return result, usage_tokens