import logging
import json
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.agent.nodes import parse_model
from backend.config import get_settings
from backend.dependencies import get_redis
from backend.schemas.upload import UploadResponse
from backend.services.analytics import capture as posthog_capture
from backend.services.costing import (
    estimate_cost_jpy,
    estimate_cost_usd,
    extract_usage,
    log_local_ocr_estimate,
)
from backend.services.local_ocr import assess_ocr_confidence, estimate_text_with_local_ocr
from backend.services.pdf_extractor import extract_text_from_pdf_text_layer, pdf_text_layer_is_sufficient
from backend.services.pii_detector import detect_pii
from backend.services.quote_guard import (
    allow_preview_generation,
    build_contract_content_hash,
    build_quote_token,
    enforce_upload_rate_limit,
    extract_client_ip,
    load_cached_quote,
    store_cached_quote,
)
from backend.services.temp_uploads import delete_temp_upload, get_temp_upload_path, stage_temp_upload
from backend.services.token_estimator import estimate_price_from_page_count, estimate_tokens_and_price
from backend.services.costing import log_model_usage

logger = logging.getLogger(__name__)

router = APIRouter()
preview_llm = ChatOpenAI(model=parse_model, temperature=0, timeout=10)


def _enforce_upload_limits(page_estimate: int, estimated_tokens: int) -> None:
    settings = get_settings()
    if page_estimate > settings.MAX_UPLOAD_PAGES:
        raise HTTPException(status_code=413, detail="Contract exceeds maximum supported page count")
    if estimated_tokens > settings.MAX_CONTRACT_TOKENS:
        raise HTTPException(status_code=413, detail="Contract exceeds maximum supported length")


def _estimate_with_local_ocr(upload_token: str, page_estimate: int) -> tuple[str, int, str | None, list[str]]:
    settings = get_settings()
    if not settings.ENABLE_LOCAL_OCR_ESTIMATE:
        log_local_ocr_estimate(
            provider="disabled",
            page_estimate=page_estimate,
            estimated_tokens=0,
            duration_ms=0,
            used_fallback=True,
        )
        return "", 0, None, ["upload.ocr_post_payment_notice"]

    started = time.perf_counter()
    local_ocr_result = estimate_text_with_local_ocr(str(get_temp_upload_path(upload_token)))
    duration_ms = int((time.perf_counter() - started) * 1000)
    local_ocr_text = local_ocr_result.text
    estimated_tokens = estimate_tokens_and_price(local_ocr_text)["estimated_tokens"] if local_ocr_text.strip() else 0
    log_local_ocr_estimate(
        provider=local_ocr_result.provider if local_ocr_result.provider == "paddleocr" else "fallback",
        page_estimate=page_estimate,
        estimated_tokens=estimated_tokens,
        duration_ms=duration_ms,
        used_fallback=not local_ocr_text.strip(),
    )
    confidence, warnings = assess_ocr_confidence(local_ocr_text, page_estimate, local_ocr_result.provider)
    return local_ocr_text, estimated_tokens, confidence, warnings


def _extract_clause_preview(
    contract_text: str,
) -> tuple[list[dict[str, str]] | None, int | None, dict | None, bool | None]:
    if len(contract_text.strip()) < 100:
        return None, None, None, None

    messages = [
        SystemMessage(
            content=(
                "あなたは日本語契約書の構造を短く整理するアシスタントです。"
                "まず文書が契約書かどうかを判定し、契約書であれば条項番号と短い見出しを抽出してください。"
            )
        ),
        HumanMessage(
            content=(
                "以下の文書が契約書かどうかを判定し、条項を抽出してください。\n"
                "必ず JSON オブジェクトのみを返してください。\n\n"
                '出力形式: {"is_contract": true, "clauses": [{"number":"第1条","title":"目的"}]}\n\n'
                "判定ルール:\n"
                "- 契約書・合意書・利用規約・覚書・申込契約など、当事者間の権利義務を定める文書なら is_contract=true\n"
                "- メール、案内文、ニュース記事、説明文、履歴書、メモ、請求書なら is_contract=false\n"
                "- is_contract=false の場合、clauses は空配列にしてください\n"
                "- 条項番号が不明でも、見出しが推定できる場合は短く付けてください\n"
                "- 本文全文は返さないでください\n\n"
                f"文書:\n{contract_text}"
            )
        ),
    ]

    try:
        response = preview_llm.invoke(messages)
        log_model_usage("parse_contract_preview", parse_model, response)
        usage = extract_usage(response)
        preview_snapshot = {
            "preview_model": parse_model,
            "preview_input_tokens": usage["input_tokens"],
            "preview_output_tokens": usage["output_tokens"],
            "preview_cached_input_tokens": usage["cached_input_tokens"],
            "preview_cost_usd": round(estimate_cost_usd(parse_model, **usage), 6),
            "preview_cost_jpy": round(estimate_cost_jpy(parse_model, **usage), 3),
            "preview_succeeded": True,
        }
        content = str(response.content).strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        payload = json.loads(content)

        if isinstance(payload, list):
            clauses_raw = payload
            is_contract: bool | None = True
        elif isinstance(payload, dict):
            clauses_raw = payload.get("clauses") or []
            is_contract = bool(payload.get("is_contract", True))
        else:
            return None, None, preview_snapshot, None

        if not is_contract:
            return None, None, preview_snapshot, False

        preview: list[dict[str, str]] = []
        for item in clauses_raw:
            if not isinstance(item, dict):
                continue
            number = str(item.get("number") or "").strip()
            title = str(item.get("title") or "").strip()
            if not number and not title:
                continue
            preview.append({"number": number or "条項", "title": title or "内容"})

        if not preview:
            return None, None, preview_snapshot, is_contract
        return preview, len(preview), preview_snapshot, is_contract
    except Exception as exc:
        logger.warning("Clause preview extraction failed: %s", exc)
        return None, None, None, None


@router.post("/api/upload", response_model=UploadResponse)
async def upload_contract(
    raw_request: Request,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    input_type: str = Form("text"),
):
    """Upload a contract via image, PDF, or text. Returns token estimate, pricing, and PII warnings."""
    redis = await get_redis()
    client_ip = extract_client_ip(raw_request)
    await enforce_upload_rate_limit(redis, client_ip)

    contract_text = ""
    quote_mode = "exact"
    estimate_source = "raw_text"
    quote_token: str | None = None
    ocr_required = False
    ocr_confidence: str | None = None
    ocr_warnings: list[str] = []
    upload_token: str | None = None
    upload_name: str | None = None
    upload_mime_type: str | None = None
    pii_warnings = []
    clause_preview: list[dict[str, str]] | None = None
    clause_count: int | None = None
    is_contract: bool | None = None
    preview_snapshot: dict | None = None
    estimation = {
        "estimated_tokens": 0,
        "page_estimate": 0,
        "pricing_model": "token_linear",
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
            local_ocr_text, _, ocr_confidence, ocr_warnings = _estimate_with_local_ocr(upload_token, page_count)
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
        local_ocr_text, _, ocr_confidence, ocr_warnings = _estimate_with_local_ocr(upload_token, 1)
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

    if quote_mode == "exact" and contract_text.strip():
        content_hash = build_contract_content_hash(contract_text)
        cached_quote = await load_cached_quote(redis, content_hash)
        if cached_quote is not None:
            clause_preview = cached_quote.get("clause_preview")
            clause_count = cached_quote.get("clause_count")
            is_contract = cached_quote.get("is_contract")
            preview_snapshot = (cached_quote.get("prepayment_snapshot") or {}) | {"cache_hit": True}
            quote_token = cached_quote.get("quote_token")
        else:
            preview_allowed = await allow_preview_generation(redis, client_ip)
            if preview_allowed:
                clause_preview, clause_count, preview_snapshot, is_contract = _extract_clause_preview(contract_text)
            if preview_snapshot is None:
                preview_snapshot = {
                    "preview_model": parse_model,
                    "preview_input_tokens": 0,
                    "preview_output_tokens": 0,
                    "preview_cached_input_tokens": 0,
                    "preview_cost_usd": 0.0,
                    "preview_cost_jpy": 0.0,
                    "preview_succeeded": False,
                    "blocked_by_rate_limit": not preview_allowed,
                }
            preview_snapshot["content_hash"] = content_hash
            preview_snapshot["cache_hit"] = False
            quote_token = build_quote_token()
            await store_cached_quote(
                redis,
                content_hash=content_hash,
                quote_token=quote_token,
                payload={
                    "quote_token": quote_token,
                    "content_hash": content_hash,
                    "clause_preview": clause_preview,
                    "clause_count": clause_count,
                    "is_contract": is_contract,
                    "prepayment_snapshot": preview_snapshot,
                },
            )

    if not contract_text.strip() and estimation["price_jpy"] == 0:
        return UploadResponse(
            contract_text="",
            estimated_tokens=0,
            price_jpy=0,
            quote_mode=quote_mode,
            estimate_source=estimate_source,
            quote_token=quote_token,
            ocr_required=ocr_required,
            ocr_confidence=ocr_confidence,
            ocr_warnings=ocr_warnings,
            clause_preview=clause_preview,
            clause_count=clause_count,
            is_contract=is_contract,
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
            "client_ip": client_ip,
            "estimated_tokens": estimation["estimated_tokens"],
            "quote_mode": quote_mode,
            "estimate_source": estimate_source,
            "has_clause_preview": clause_preview is not None,
            "quote_token_present": quote_token is not None,
            "pricing_model": estimation["pricing_model"],
            "price_jpy": estimation["price_jpy"],
            "has_pii": len(pii_warnings) > 0,
        },
    )

    return UploadResponse(
        contract_text=contract_text,
        estimated_tokens=estimation["estimated_tokens"],
        price_jpy=estimation["price_jpy"],
        quote_mode=quote_mode,
        estimate_source=estimate_source,
        quote_token=quote_token,
        ocr_required=ocr_required,
        ocr_confidence=ocr_confidence,
        ocr_warnings=ocr_warnings,
        clause_preview=clause_preview,
        clause_count=clause_count,
        is_contract=is_contract,
        upload_token=upload_token,
        upload_name=upload_name,
        upload_mime_type=upload_mime_type,
        pii_warnings=pii_warnings,
    )
