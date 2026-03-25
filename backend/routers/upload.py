import logging
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.config import get_settings
from backend.schemas.upload import UploadResponse
from backend.services.analytics import capture as posthog_capture
from backend.services.costing import log_local_ocr_estimate
from backend.services.local_ocr import estimate_text_with_local_ocr
from backend.services.pdf_extractor import extract_text_from_pdf_text_layer, pdf_text_layer_is_sufficient
from backend.services.pii_detector import detect_pii
from backend.services.temp_uploads import delete_temp_upload, get_temp_upload_path, stage_temp_upload
from backend.services.token_estimator import estimate_price_from_page_count, estimate_tokens_and_price

logger = logging.getLogger(__name__)

router = APIRouter()


def _enforce_upload_limits(page_estimate: int, estimated_tokens: int) -> None:
    settings = get_settings()
    if page_estimate > settings.MAX_UPLOAD_PAGES:
        raise HTTPException(status_code=413, detail="Contract exceeds maximum supported page count")
    if estimated_tokens > settings.MAX_CONTRACT_TOKENS:
        raise HTTPException(status_code=413, detail="Contract exceeds maximum supported length")


def _estimate_with_local_ocr(upload_token: str, page_estimate: int) -> tuple[str, int]:
    settings = get_settings()
    if not settings.ENABLE_LOCAL_OCR_ESTIMATE:
        log_local_ocr_estimate(
            provider="disabled",
            page_estimate=page_estimate,
            estimated_tokens=0,
            duration_ms=0,
            used_fallback=True,
        )
        return "", 0

    started = time.perf_counter()
    local_ocr_text = estimate_text_with_local_ocr(str(get_temp_upload_path(upload_token)))
    duration_ms = int((time.perf_counter() - started) * 1000)
    estimated_tokens = estimate_tokens_and_price(local_ocr_text)["estimated_tokens"] if local_ocr_text.strip() else 0
    log_local_ocr_estimate(
        provider="paddleocr" if local_ocr_text.strip() else "fallback",
        page_estimate=page_estimate,
        estimated_tokens=estimated_tokens,
        duration_ms=duration_ms,
        used_fallback=not local_ocr_text.strip(),
    )
    return local_ocr_text, estimated_tokens


@router.post("/api/upload", response_model=UploadResponse)
async def upload_contract(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    input_type: str = Form("text"),
):
    """Upload a contract via image, PDF, or text. Returns token estimate, pricing, and PII warnings."""
    contract_text = ""
    quote_mode = "exact"
    estimate_source = "raw_text"
    ocr_required = False
    upload_token: str | None = None
    upload_name: str | None = None
    upload_mime_type: str | None = None
    pii_warnings = []
    estimation = {
        "estimated_tokens": 0,
        "page_estimate": 0,
        "price_tier": "basic",
        "price_jpy": 0,
    }

    if input_type == "text" and text:
        contract_text = text
        estimation = estimate_tokens_and_price(contract_text)
        pii_warnings = detect_pii(contract_text)
    elif input_type == "pdf" and file:
        pdf_bytes = await file.read()
        extracted_text, page_count = extract_text_from_pdf_text_layer(pdf_bytes)
        if pdf_text_layer_is_sufficient(extracted_text, page_count):
            contract_text = extracted_text
            estimate_source = "pdf_text_layer"
            estimation = estimate_tokens_and_price(contract_text)
            pii_warnings = detect_pii(contract_text)
        else:
            upload_token = stage_temp_upload(pdf_bytes, file.filename)
            upload_name = file.filename
            upload_mime_type = file.content_type or "application/pdf"
            quote_mode = "estimated_pre_ocr"
            estimate_source = "page_count_fallback"
            ocr_required = True
            local_ocr_text, _ = _estimate_with_local_ocr(upload_token, page_count)
            if local_ocr_text.strip():
                estimation = estimate_tokens_and_price(local_ocr_text)
                estimation["page_estimate"] = max(estimation["page_estimate"], page_count)
                estimate_source = "local_ocr"
                pii_warnings = detect_pii(local_ocr_text)
            else:
                estimation = estimate_price_from_page_count(page_count)
    elif input_type == "image" and file:
        image_bytes = await file.read()
        upload_token = stage_temp_upload(image_bytes, file.filename)
        upload_name = file.filename
        upload_mime_type = file.content_type or "image/jpeg"
        quote_mode = "estimated_pre_ocr"
        estimate_source = "page_count_fallback"
        ocr_required = True
        local_ocr_text, _ = _estimate_with_local_ocr(upload_token, 1)
        if local_ocr_text.strip():
            estimation = estimate_tokens_and_price(local_ocr_text)
            estimate_source = "local_ocr"
            pii_warnings = detect_pii(local_ocr_text)
        else:
            estimation = estimate_price_from_page_count(1)
    else:
        contract_text = text or ""
        if contract_text.strip():
            estimation = estimate_tokens_and_price(contract_text)
            pii_warnings = detect_pii(contract_text)

    if not contract_text.strip() and estimation["price_jpy"] == 0:
        return UploadResponse(
            contract_text="",
            estimated_tokens=0,
            page_estimate=0,
            price_tier="basic",
            price_jpy=0,
            quote_mode=quote_mode,
            estimate_source=estimate_source,
            ocr_required=ocr_required,
            upload_token=upload_token,
            upload_name=upload_name,
            upload_mime_type=upload_mime_type,
            pii_warnings=[],
        )

    try:
        _enforce_upload_limits(estimation["page_estimate"], estimation["estimated_tokens"])
    except HTTPException:
        delete_temp_upload(upload_token)
        raise

    posthog_capture(
        "anonymous",
        "contract_uploaded",
        {
            "input_type": input_type,
            "estimated_tokens": estimation["estimated_tokens"],
            "quote_mode": quote_mode,
            "estimate_source": estimate_source,
            "price_tier": estimation["price_tier"],
            "price_jpy": estimation["price_jpy"],
            "has_pii": len(pii_warnings) > 0,
        },
    )

    return UploadResponse(
        contract_text=contract_text,
        estimated_tokens=estimation["estimated_tokens"],
        page_estimate=estimation["page_estimate"],
        price_tier=estimation["price_tier"],
        price_jpy=estimation["price_jpy"],
        quote_mode=quote_mode,
        estimate_source=estimate_source,
        ocr_required=ocr_required,
        upload_token=upload_token,
        upload_name=upload_name,
        upload_mime_type=upload_mime_type,
        pii_warnings=pii_warnings,
    )
