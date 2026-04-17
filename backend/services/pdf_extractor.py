import io
import logging

from fastapi import HTTPException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)

# Minimum characters per page to consider text extraction successful
MIN_CHARS_PER_PAGE = 50


def precheck_pdf_pages(pdf_bytes: bytes) -> int:
    """Read page count from PDF metadata without extracting text.

    - Raises 413 `upload_too_many_pages` when page count exceeds MAX_UPLOAD_PAGES.
    - Raises 415 `upload_encrypted_pdf` when the PDF is password-protected.
    - Raises 422 `upload_corrupt_pdf` when the file cannot be parsed as a PDF.

    Rejecting these cases here prevents corrupt / encrypted PDFs from falling
    through to the expensive Vision OCR fallback.
    """
    from backend.config import get_settings

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except PdfReadError as exc:
        logger.warning("precheck_pdf_pages: PDF is corrupt or invalid: %s", exc)
        raise HTTPException(status_code=422, detail="upload_corrupt_pdf") from exc
    except Exception as exc:
        logger.warning("precheck_pdf_pages: unexpected PDF parse error: %s", exc)
        raise HTTPException(status_code=422, detail="upload_corrupt_pdf") from exc

    if reader.is_encrypted:
        logger.warning("precheck_pdf_pages: rejecting encrypted PDF")
        raise HTTPException(status_code=415, detail="upload_encrypted_pdf")

    try:
        page_count = len(reader.pages)
    except Exception as exc:
        logger.warning("precheck_pdf_pages: could not enumerate pages: %s", exc)
        raise HTTPException(status_code=422, detail="upload_corrupt_pdf") from exc

    if page_count == 0:
        raise HTTPException(status_code=422, detail="upload_corrupt_pdf")

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
