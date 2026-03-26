import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_paddle_ocr():
    try:
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]
    except ImportError:
        return None

    return PaddleOCR(lang="japan", use_angle_cls=True, show_log=False)


def estimate_text_with_local_ocr(file_path: str) -> str:
    """Best-effort local OCR for pre-payment quote estimation.

    If PaddleOCR is unavailable, return an empty string so callers can fall back
    to page-count-based estimation without paying for formal OCR.
    """
    ocr = _get_paddle_ocr()
    if ocr is None:
        logger.info("PaddleOCR unavailable; falling back to non-OCR quote estimation")
        return ""

    try:
        result = ocr.ocr(file_path, cls=True)
    except Exception as exc:
        logger.warning("Local OCR estimate failed for %s: %s", file_path, exc)
        return ""

    lines: list[str] = []
    for page in result or []:
        for line in page or []:
            if len(line) > 1 and isinstance(line[1], (list, tuple)) and line[1]:
                text = str(line[1][0]).strip()
                if text:
                    lines.append(text)

    return "\n".join(lines)
