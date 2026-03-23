import base64
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


async def extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
    """Send image to GPT-4o Vision for Japanese contract OCR."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    message = HumanMessage(
        content=[
            {"type": "text", "text": "Extract all Japanese text from this contract image exactly as written. Output only the extracted text, no commentary."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    )

    response = await llm.ainvoke([message])
    return response.content
