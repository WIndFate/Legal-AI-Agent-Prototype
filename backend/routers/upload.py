import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from backend.schemas.upload import UploadResponse
from backend.services.token_estimator import estimate_tokens_and_price
from backend.services.pii_detector import detect_pii
from backend.services.ocr import extract_text_from_image
from backend.services.pdf_extractor import extract_text_from_pdf
from backend.services.analytics import capture as posthog_capture

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/upload", response_model=UploadResponse)
async def upload_contract(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    input_type: str = Form("text"),
):
    """Upload a contract via image, PDF, or text. Returns token estimate, pricing, and PII warnings."""
    contract_text = ""

    if input_type == "text" and text:
        contract_text = text
    elif input_type == "image" and file:
        image_bytes = await file.read()
        contract_text = await extract_text_from_image(image_bytes, file.content_type or "image/jpeg")
    elif input_type == "pdf" and file:
        pdf_bytes = await file.read()
        contract_text = await extract_text_from_pdf(pdf_bytes)
    else:
        contract_text = text or ""

    if not contract_text.strip():
        return UploadResponse(
            contract_text="",
            estimated_tokens=0,
            page_estimate=0,
            price_tier="basic",
            price_jpy=0,
            pii_warnings=[],
        )

    # Estimate tokens and price
    estimation = estimate_tokens_and_price(contract_text)

    # Detect PII
    pii_warnings = detect_pii(contract_text)

    posthog_capture(
        "anonymous",
        "contract_uploaded",
        {
            "input_type": input_type,
            "estimated_tokens": estimation["estimated_tokens"],
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
        pii_warnings=pii_warnings,
    )
