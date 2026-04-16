import logging
import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.agent.nodes import parse_model
from backend.config import get_settings
from backend.dependencies import get_redis
from backend.schemas.upload import UploadResponse
from backend.services.abuse_guard import (
    check_ocr_allowed,
    record_ocr_upload,
    rollback_ocr_upload,
)
from backend.services.analytics import capture as posthog_capture
from backend.services.cost_guard import check_budget_allowed, record_cost
from backend.services.costing import (
    estimate_cost_jpy,
    estimate_cost_usd,
    extract_usage,
)
from backend.services.ocr import extract_text_from_image_with_snapshot, extract_text_from_pdf_with_snapshot
from backend.services.pdf_extractor import (
    extract_text_from_pdf_text_layer,
    pdf_text_layer_is_sufficient,
    precheck_pdf_pages,
)
from backend.services.pii_detector import detect_pii
from backend.services.quote_guard import (
    allow_preview_generation,
    build_contract_content_hash,
    build_file_hash,
    build_quote_token,
    enforce_upload_rate_limit,
    extract_client_ip,
    load_cached_quote,
    load_ocr_result_cache,
    store_cached_quote,
    store_ocr_result_cache,
)
from backend.services.token_estimator import estimate_tokens_and_price
from backend.services.upload_validation import check_upload_file_size, detect_and_validate_mime
from backend.services.costing import log_model_usage

logger = logging.getLogger(__name__)

router = APIRouter()
preview_llm = ChatOpenAI(model=parse_model, temperature=0, timeout=10)


def _enforce_upload_limits(page_estimate: int, estimated_tokens: int) -> None:
    settings = get_settings()
    if page_estimate > settings.MAX_UPLOAD_PAGES:
        raise HTTPException(status_code=413, detail="upload_too_many_pages")
    if estimated_tokens > settings.MAX_CONTRACT_TOKENS:
        raise HTTPException(status_code=413, detail="upload_text_too_long")


def _extract_clause_preview(
    contract_text: str,
) -> tuple[list[dict[str, str]] | None, int | None, dict | None, bool | None]:
    text = contract_text.strip()
    if not text:
        return None, None, None, None
    text_is_short = len(text) < 100

    messages = [
        SystemMessage(
            content=(
                "あなたは日本語契約書の構造を短く整理するアシスタントです。"
                "まず文書が契約書かどうかを判定し、契約書であれば条項番号と短い見出しを抽出してください。"
                "文書が短すぎて条項抽出に向かない場合でも、契約書かどうかの判定は必ず行ってください。"
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
                "- 氏名だけ、キャプションだけ、ポスターやゲーム画面の文字断片だけのように契約本文として成立しないものは is_contract=false\n"
                "- is_contract=false の場合、clauses は空配列にしてください\n"
                "- 条項番号が不明でも、見出しが推定できる場合は短く付けてください\n"
                "- 文書が短すぎる場合や条項構造が見えない場合は、is_contract を返したうえで clauses は空配列にしてください\n"
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

        if text_is_short or not preview:
            return None, None, preview_snapshot, is_contract
        return preview, len(preview), preview_snapshot, is_contract
    except Exception as exc:
        logger.warning("Clause preview extraction failed: %s", exc)
        return None, None, None, None


def _merge_prepayment_snapshot(
    *,
    ocr_snapshot: dict | None = None,
    preview_snapshot: dict | None = None,
    content_hash: str | None = None,
    cache_hit: bool = False,
) -> dict | None:
    if not ocr_snapshot and not preview_snapshot:
        return None

    merged: dict[str, object] = {
        "cache_hit": cache_hit,
    }
    if content_hash:
        merged["content_hash"] = content_hash
    if ocr_snapshot:
        merged.update(ocr_snapshot)
    if preview_snapshot:
        merged.update(preview_snapshot)
    return merged


@router.post("/api/upload", response_model=UploadResponse)
async def upload_contract(
    raw_request: Request,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    input_type: str = Form("text"),
):
    """Upload a contract via image, PDF, or text. Returns token estimate, pricing, and PII warnings."""
    settings = get_settings()
    redis = await get_redis()
    client_ip = extract_client_ip(raw_request)
    await enforce_upload_rate_limit(redis, client_ip)

    contract_text = ""
    quote_mode = "exact"
    estimate_source = "raw_text"
    quote_token: str | None = None
    upload_token: str | None = None
    upload_name: str | None = None
    upload_mime_type: str | None = None
    pii_warnings = []
    clause_preview: list[dict[str, str]] | None = None
    clause_count: int | None = None
    is_contract: bool | None = None
    preview_snapshot: dict | None = None
    ocr_snapshot: dict | None = None
    estimation = {
        "estimated_tokens": 0,
        "page_estimate": 0,
        "pricing_model": "token_linear",
        "price_jpy": 0,
    }

    if input_type == "text" and text:
        # Text char limit check (pre-payment cost is negligible for text)
        if len(text) > settings.MAX_UPLOAD_TEXT_CHARS:
            raise HTTPException(status_code=413, detail="upload_text_too_long")
        contract_text = text
        estimation = estimate_tokens_and_price(contract_text)
        pii_warnings = detect_pii(contract_text)

    elif input_type == "pdf" and file:
        pdf_bytes = await file.read()

        # MIME validation (P0-5): detect real type from magic bytes
        actual_mime = detect_and_validate_mime(pdf_bytes)

        # File size check (P0-1)
        check_upload_file_size(pdf_bytes, actual_mime, settings)

        # Page count precheck BEFORE any OCR (P0-1)
        page_count = precheck_pdf_pages(pdf_bytes)

        upload_mime_type = actual_mime

        # Try text layer first (free — pypdf, no abuse guard needed)
        extracted_text, page_count = extract_text_from_pdf_text_layer(pdf_bytes)
        if pdf_text_layer_is_sufficient(extracted_text, page_count):
            contract_text = extracted_text
            estimate_source = "pdf_text_layer"
            estimation = estimate_tokens_and_price(contract_text)
            pii_warnings = detect_pii(contract_text)
        else:
            # Scanned PDF needs Vision OCR — apply abuse guard
            file_hash = build_file_hash(pdf_bytes)
            cached_ocr = await load_ocr_result_cache(redis, file_hash)
            if cached_ocr:
                contract_text = cached_ocr["text"]
                ocr_snapshot = cached_ocr.get("snapshot")
            else:
                if not await check_ocr_allowed(redis, client_ip):
                    raise HTTPException(status_code=429, detail="upload_banned")
                await record_ocr_upload(redis, client_ip)
                try:
                    budget_allowed = await check_budget_allowed(
                        redis,
                        float(page_count) * float(settings.GOOGLE_VISION_COST_PER_PAGE_JPY),
                    )
                    if not budget_allowed:
                        await rollback_ocr_upload(redis, client_ip)
                        raise HTTPException(status_code=503, detail="daily_budget_exhausted")
                    contract_text, ocr_snapshot = await extract_text_from_pdf_with_snapshot(pdf_bytes)
                    await record_cost(redis, float((ocr_snapshot or {}).get("ocr_cost_jpy", 0.0)))
                    # Only cache non-empty OCR results: an empty result indicates a
                    # blank/unreadable scan, and caching it would permanently serve
                    # zero-price responses for anyone uploading the same file.
                    if contract_text.strip():
                        await store_ocr_result_cache(redis, file_hash, contract_text, ocr_snapshot)
                except Exception:
                    await rollback_ocr_upload(redis, client_ip)
                    raise
            estimate_source = "vision_ocr"
            if contract_text.strip():
                estimation = estimate_tokens_and_price(contract_text)
                pii_warnings = detect_pii(contract_text)

    elif input_type == "image" and file:
        image_bytes = await file.read()

        # MIME validation (P0-5)
        actual_mime = detect_and_validate_mime(image_bytes)

        # File size check (P0-1)
        check_upload_file_size(image_bytes, actual_mime, settings)

        upload_mime_type = actual_mime

        # OCR cache check by raw file hash — same file = no new OCR cost, no waste recorded
        file_hash = build_file_hash(image_bytes)
        cached_ocr = await load_ocr_result_cache(redis, file_hash)
        if cached_ocr:
            contract_text = cached_ocr["text"]
            ocr_snapshot = cached_ocr.get("snapshot")
        else:
            # New file — apply abuse guard before Vision OCR
            if not await check_ocr_allowed(redis, client_ip):
                raise HTTPException(status_code=429, detail="upload_banned")
            await record_ocr_upload(redis, client_ip)
            try:
                budget_allowed = await check_budget_allowed(
                    redis,
                    float(settings.GOOGLE_VISION_COST_PER_PAGE_JPY),
                )
                if not budget_allowed:
                    await rollback_ocr_upload(redis, client_ip)
                    raise HTTPException(status_code=503, detail="daily_budget_exhausted")
                contract_text, ocr_snapshot = await extract_text_from_image_with_snapshot(
                    image_bytes, actual_mime
                )
                await record_cost(redis, float((ocr_snapshot or {}).get("ocr_cost_jpy", 0.0)))
                # Skip caching empty OCR results — see PDF branch rationale above.
                if contract_text.strip():
                    await store_ocr_result_cache(redis, file_hash, contract_text, ocr_snapshot)
            except Exception:
                await rollback_ocr_upload(redis, client_ip)
                raise

        estimate_source = "vision_ocr"
        if contract_text.strip():
            estimation = estimate_tokens_and_price(contract_text)
            pii_warnings = detect_pii(contract_text)

    else:
        contract_text = text or ""
        if contract_text.strip():
            estimation = estimate_tokens_and_price(contract_text)
            pii_warnings = detect_pii(contract_text)

    # Enforce token / page limits BEFORE the preview LLM runs so that oversize
    # contracts don't pay preview cost on top of the OCR cost already incurred.
    if contract_text.strip():
        _enforce_upload_limits(estimation["page_estimate"], estimation["estimated_tokens"])

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
            prepayment_snapshot = _merge_prepayment_snapshot(
                ocr_snapshot=ocr_snapshot,
                preview_snapshot=preview_snapshot,
                content_hash=content_hash,
                cache_hit=False,
            )
            quote_token = build_quote_token()
            await store_cached_quote(
                redis,
                content_hash=content_hash,
                quote_token=quote_token,
                upload_token=upload_token,
                payload={
                    "quote_token": quote_token,
                    "content_hash": content_hash,
                    "clause_preview": clause_preview,
                    "clause_count": clause_count,
                    "is_contract": is_contract,
                    "prepayment_snapshot": prepayment_snapshot,
                    # Authoritative price / token count. Payment endpoint
                    # verifies the client-submitted price_jpy against these.
                    "price_jpy": estimation["price_jpy"],
                    "estimated_tokens": estimation["estimated_tokens"],
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
            clause_preview=clause_preview,
            clause_count=clause_count,
            is_contract=is_contract,
            upload_token=upload_token,
            upload_name=upload_name,
            upload_mime_type=upload_mime_type,
            pii_warnings=[],
        )

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
        clause_preview=clause_preview,
        clause_count=clause_count,
        is_contract=is_contract,
        upload_token=upload_token,
        upload_name=upload_name,
        upload_mime_type=upload_mime_type,
        pii_warnings=pii_warnings,
    )
