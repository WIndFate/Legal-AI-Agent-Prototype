import io
import logging

from pypdf import PdfReader

from backend.services.ocr import extract_text_from_image

logger = logging.getLogger(__name__)

# Minimum characters per page to consider text extraction successful
MIN_CHARS_PER_PAGE = 50


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
        # Scanned PDF - fall back to OCR (page by page would be ideal but costly)
        logger.info("PDF text extraction yielded too few characters, falling back to OCR")
        return await extract_text_from_image(pdf_bytes, "application/pdf")

    return total_text
