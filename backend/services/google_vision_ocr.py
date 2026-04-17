from __future__ import annotations

import asyncio
import io
import logging
import os

from fastapi import HTTPException
from google.api_core import exceptions as google_exceptions
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import vision
from pdf2image import convert_from_bytes
from pypdf import PdfReader

from backend.config import get_settings
from backend.services.costing import USD_TO_JPY_RATE

logger = logging.getLogger(__name__)
_vision_client: vision.ImageAnnotatorClient | None = None


def _ensure_google_vision_configured() -> None:
    settings = get_settings()
    if settings.GOOGLE_APPLICATION_CREDENTIALS_JSON.strip():
        return
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip():
        return
    raise HTTPException(status_code=503, detail="google_vision_not_configured")


def _classify_google_vision_error(message: str) -> str:
    normalized = (message or "").lower()
    if "billing" in normalized and "enable" in normalized:
        return "google_vision_billing_disabled"
    if "service has not been used" in normalized or "api has not been used" in normalized:
        return "google_vision_api_disabled"
    if "permission denied" in normalized or "does not have permission" in normalized:
        return "google_vision_permission_denied"
    if "unauthenticated" in normalized or "authentication" in normalized:
        return "google_vision_auth_failed"
    if "credentials" in normalized and (
        "determine" in normalized or "not found" in normalized or "invalid" in normalized
    ):
        return "google_vision_not_configured"
    return "google_vision_unavailable"


def _raise_google_vision_http_error(message: str, *, cause: Exception | None = None) -> None:
    error_code = _classify_google_vision_error(message)
    logger.warning("Google Vision OCR failed with %s: %s", error_code, message)
    if cause is not None:
        raise HTTPException(status_code=503, detail=error_code) from cause
    raise HTTPException(status_code=503, detail=error_code)


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


def _get_vision_client() -> vision.ImageAnnotatorClient:
    global _vision_client

    _ensure_google_vision_configured()
    if _vision_client is None:
        try:
            _vision_client = vision.ImageAnnotatorClient()
        except DefaultCredentialsError as exc:
            _raise_google_vision_http_error(str(exc), cause=exc)
    return _vision_client


def _extract_text_from_image_sync(image_bytes: bytes) -> str:
    client = _get_vision_client()
    image = vision.Image(content=image_bytes)
    try:
        response = client.document_text_detection(image=image)
    except (
        google_exceptions.PermissionDenied,
        google_exceptions.Unauthenticated,
        google_exceptions.GoogleAPICallError,
    ) as exc:
        _raise_google_vision_http_error(str(exc), cause=exc)

    if response.error.message:
        _raise_google_vision_http_error(response.error.message)
    return (response.full_text_annotation.text or "").strip()


def _extract_text_from_pdf_sync_with_page_count(
    pdf_bytes: bytes,
    page_count: int | None = None,
) -> tuple[str, int]:
    if page_count is None:
        page_count = len(PdfReader(io.BytesIO(pdf_bytes)).pages)
    extracted_pages: list[str] = []
    for page_number in range(1, page_count + 1):
        pages = convert_from_bytes(
            pdf_bytes,
            dpi=200,
            fmt="png",
            first_page=page_number,
            last_page=page_number,
        )
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
    return text, page_count


async def extract_text_from_image_with_snapshot(image_bytes: bytes, mime_type: str) -> tuple[str, dict]:
    text = await asyncio.to_thread(_extract_text_from_image_sync, image_bytes)
    snapshot = _build_vision_snapshot(pages=1, text=text, mime_type=mime_type)
    logger.info("Google Vision OCR usage: %s", snapshot)
    return text, snapshot


async def extract_text_from_pdf_with_snapshot(pdf_bytes: bytes) -> tuple[str, dict]:
    text, page_count = await asyncio.to_thread(_extract_text_from_pdf_sync_with_page_count, pdf_bytes)
    snapshot = _build_vision_snapshot(
        pages=page_count,
        text=text,
        mime_type="application/pdf",
    )
    logger.info("Google Vision OCR usage: %s", snapshot)
    return text, snapshot


async def extract_text_from_pdf_with_snapshot_using_page_count(
    pdf_bytes: bytes,
    page_count: int,
) -> tuple[str, dict]:
    text, _ = await asyncio.to_thread(_extract_text_from_pdf_sync_with_page_count, pdf_bytes, page_count)
    snapshot = _build_vision_snapshot(
        pages=page_count,
        text=text,
        mime_type="application/pdf",
    )
    logger.info("Google Vision OCR usage: %s", snapshot)
    return text, snapshot
