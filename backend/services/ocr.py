import base64
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from backend.config import get_settings
from backend.services.costing import log_model_usage

logger = logging.getLogger(__name__)


async def extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
    """Send image to GPT-4o Vision for Japanese contract OCR."""
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
    return response.content
