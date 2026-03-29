import logging
import re
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LocalOcrEstimate:
    text: str
    provider: str


_JP_CHAR_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff々ー]")


@lru_cache(maxsize=1)
def _get_paddle_ocr():
    try:
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]
    except ImportError:
        return None

    return PaddleOCR(lang="japan", use_angle_cls=True, show_log=False)


def estimate_text_with_local_ocr(file_path: str) -> LocalOcrEstimate:
    """Best-effort local OCR for pre-payment quote estimation.

    If PaddleOCR is unavailable, return an empty string so callers can fall back
    to page-count-based estimation without paying for formal OCR.
    """
    ocr = _get_paddle_ocr()
    if ocr is None:
        logger.info("PaddleOCR unavailable; falling back to non-OCR quote estimation")
        return LocalOcrEstimate(text="", provider="disabled")

    try:
        result = ocr.ocr(file_path, cls=True)
    except Exception as exc:
        logger.warning("Local OCR estimate failed for %s: %s", file_path, exc)
        return LocalOcrEstimate(text="", provider="error")

    lines: list[str] = []
    for page in result or []:
        for line in page or []:
            if len(line) > 1 and isinstance(line[1], (list, tuple)) and line[1]:
                text = str(line[1][0]).strip()
                if text:
                    lines.append(text)

    return LocalOcrEstimate(text="\n".join(lines), provider="paddleocr")


def assess_ocr_confidence(
    extracted_text: str,
    page_estimate: int,
    provider: str,
) -> tuple[str | None, list[str]]:
    normalized_pages = max(page_estimate, 1)
    compact_text = extracted_text.strip()

    if provider != "paddleocr" and not compact_text:
        return None, ["upload.ocr_post_payment_notice"]

    if not compact_text:
        return "low", ["upload.ocr_low_quality"]

    char_count = len(compact_text)
    chars_per_page = char_count / normalized_pages
    japanese_chars = len(_JP_CHAR_PATTERN.findall(compact_text))
    visible_char_count = len(re.findall(r"\S", compact_text))
    japanese_ratio = japanese_chars / max(visible_char_count, 1)

    if chars_per_page < 50 or japanese_ratio < 0.30:
        return "low", ["upload.ocr_low_quality"]
    if chars_per_page < 120 or japanese_ratio < 0.55:
        return "medium", ["upload.ocr_medium_quality"]
    return "high", []
