import io
import logging

from PyPDF2 import PdfReader

from backend.services.ocr import extract_text_from_image

logger = logging.getLogger(__name__)

# Minimum characters per page to consider text extraction successful
MIN_CHARS_PER_PAGE = 50


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF. Falls back to OCR for scanned PDFs."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)

    # Check if text extraction was successful
    total_text = "\n".join(pages_text)
    avg_chars = len(total_text) / max(len(reader.pages), 1)

    if avg_chars < MIN_CHARS_PER_PAGE:
        # Scanned PDF - fall back to OCR (page by page would be ideal but costly)
        logger.info("PDF text extraction yielded too few characters, falling back to OCR")
        return await extract_text_from_image(pdf_bytes, "application/pdf")

    return total_text
