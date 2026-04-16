from __future__ import annotations

import asyncio
import io
import logging

from google.cloud import vision
from pdf2image import convert_from_bytes

from backend.config import get_settings
from backend.services.costing import USD_TO_JPY_RATE

logger = logging.getLogger(__name__)


def _build_vision_snapshot(*, pages: int, text: str, mime_type: str) -> dict:
    settings = get_settings()
    cost_jpy = round(float(pages) * float(settings.GOOGLE_VISION_COST_PER_PAGE_JPY), 3)
    return {
        "ocr_model": settings.OCR_MODEL,
        "ocr_input_tokens": pages,
        "ocr_output_tokens": len(text),
        "ocr_cached_input_tokens": 0,
        "ocr_cost_usd": round(cost_jpy / USD_TO_JPY_RATE, 6),
        "ocr_cost_jpy": cost_jpy,
        "ocr_succeeded": True,
        "ocr_mime_type": mime_type,
        "ocr_pages": pages,
    }


def _extract_text_from_image_sync(image_bytes: bytes) -> str:
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise RuntimeError(f"Google Vision OCR failed: {response.error.message}")
    return (response.full_text_annotation.text or "").strip()


def _extract_text_from_pdf_sync(pdf_bytes: bytes) -> tuple[str, int]:
    pages = convert_from_bytes(pdf_bytes, dpi=200, fmt="png")
    extracted_pages: list[str] = []
    try:
        for page in pages:
            buffer = io.BytesIO()
            page.save(buffer, format="PNG")
            extracted_pages.append(_extract_text_from_image_sync(buffer.getvalue()))
            buffer.close()
            page.close()
    finally:
        for page in pages:
            try:
                page.close()
            except Exception:
                pass
    text = "\n\n".join(chunk for chunk in extracted_pages if chunk.strip()).strip()
    return text, len(pages)


async def extract_text_from_image_with_snapshot(image_bytes: bytes, mime_type: str) -> tuple[str, dict]:
    text = await asyncio.to_thread(_extract_text_from_image_sync, image_bytes)
    snapshot = _build_vision_snapshot(pages=1, text=text, mime_type=mime_type)
    logger.info("Google Vision OCR usage: %s", snapshot)
    return text, snapshot


async def extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
    text, _ = await extract_text_from_image_with_snapshot(image_bytes, mime_type)
    return text


async def extract_text_from_pdf_with_snapshot(pdf_bytes: bytes) -> tuple[str, dict]:
    text, page_count = await asyncio.to_thread(_extract_text_from_pdf_sync, pdf_bytes)
    snapshot = _build_vision_snapshot(
        pages=page_count,
        text=text,
        mime_type="application/pdf",
    )
    logger.info("Google Vision OCR usage: %s", snapshot)
    return text, snapshot


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    text, _ = await extract_text_from_pdf_with_snapshot(pdf_bytes)
    return text
