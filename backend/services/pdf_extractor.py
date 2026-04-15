import io
import logging

from fastapi import HTTPException
from pypdf import PdfReader

from backend.services.ocr import extract_text_from_pdf as extract_text_from_pdf_with_vision

logger = logging.getLogger(__name__)

# Minimum characters per page to consider text extraction successful
MIN_CHARS_PER_PAGE = 50


def precheck_pdf_pages(pdf_bytes: bytes) -> int:
    """Read page count from PDF metadata without extracting text.

    Raises 413 if the page count exceeds MAX_UPLOAD_PAGES.
    Returns the page count on success. Returns 0 if the count cannot be determined.
    """
    from backend.config import get_settings

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
    except Exception as exc:
        logger.warning("precheck_pdf_pages: could not read page count: %s", exc)
        return 0

    settings = get_settings()
    if page_count > settings.MAX_UPLOAD_PAGES:
        raise HTTPException(status_code=413, detail="upload_too_many_pages")

    return page_count


def extract_text_from_pdf_text_layer(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text from a PDF without OCR fallback."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)

    return "\n".join(pages_text), len(reader.pages)


def pdf_text_layer_is_sufficient(text: str, page_count: int) -> bool:
    """Return True when the embedded PDF text layer is likely usable."""
    avg_chars = len(text) / max(page_count, 1)
    return avg_chars >= MIN_CHARS_PER_PAGE


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF. Falls back to OCR for scanned PDFs."""
    total_text, page_count = extract_text_from_pdf_text_layer(pdf_bytes)
    if not pdf_text_layer_is_sufficient(total_text, page_count):
        logger.info("PDF text extraction yielded too few characters, falling back to Vision PDF OCR")
        return await extract_text_from_pdf_with_vision(pdf_bytes)

    return total_text
