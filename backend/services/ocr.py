import base64
import logging

from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from backend.config import get_settings
from backend.services.costing import estimate_cost_jpy, estimate_cost_usd, extract_usage, log_model_usage

logger = logging.getLogger(__name__)


def _build_ocr_snapshot(model: str, response, *, mime_type: str) -> dict:
    usage = extract_usage(response)
    return {
        "ocr_model": model,
        "ocr_input_tokens": usage["input_tokens"],
        "ocr_output_tokens": usage["output_tokens"],
        "ocr_cached_input_tokens": usage["cached_input_tokens"],
        "ocr_cost_usd": round(estimate_cost_usd(model, **usage), 6),
        "ocr_cost_jpy": round(estimate_cost_jpy(model, **usage), 3),
        "ocr_succeeded": True,
        "ocr_mime_type": mime_type,
    }


async def extract_text_from_image_with_snapshot(image_bytes: bytes, mime_type: str) -> tuple[str, dict]:
    """Send image to GPT-4o Vision for Japanese contract OCR and return cost snapshot."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    model = get_settings().OCR_MODEL
    llm = ChatOpenAI(model=model, temperature=0)
    message = HumanMessage(
        content=[
            {"type": "text", "text": "Extract all Japanese text from this contract image exactly as written. Output only the extracted text, no commentary."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    )

    response = await llm.ainvoke([message])
    log_model_usage("ocr_formal", model, response, mime_type=mime_type)
    return response.content, _build_ocr_snapshot(model, response, mime_type=mime_type)


async def extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
    text, _ = await extract_text_from_image_with_snapshot(image_bytes, mime_type)
    return text


async def extract_text_from_pdf_with_snapshot(pdf_bytes: bytes) -> tuple[str, dict]:
    """Send PDF bytes to the OpenAI Responses API for OCR and return cost snapshot."""
    model = get_settings().OCR_MODEL
    client = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    response = await client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Extract all Japanese text from this contract PDF exactly as written. Output only the extracted text, no commentary.",
                    },
                    {
                        "type": "input_file",
                        "filename": "contract.pdf",
                        "file_data": b64,
                    },
                ],
            }
        ],
    )
    log_model_usage("ocr_formal", model, response, mime_type="application/pdf")
    return (getattr(response, "output_text", "") or "").strip(), _build_ocr_snapshot(
        model,
        response,
        mime_type="application/pdf",
    )


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    text, _ = await extract_text_from_pdf_with_snapshot(pdf_bytes)
    return text
