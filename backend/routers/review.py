import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.order import Order
from backend.models.report import Report
from backend.schemas.order import ReviewStreamRequest
from backend.agent.graph import run_review_stream
from backend.services.analytics import capture as posthog_capture
from backend.services.costing import clear_order_cost_summary, get_order_cost_summary, reset_cost_order_context, set_cost_order_context
from backend.services.email import send_report_email
from backend.services.ocr import extract_text_from_image
from backend.services.pdf_extractor import extract_text_from_pdf
from backend.services.report_cache import cache_report
from backend.services.temp_uploads import delete_temp_upload, read_temp_upload

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

router = APIRouter()


def _strip_clause_originals(report_data: dict) -> dict:
    """Remove original clause text before persistence or sharing."""
    sanitized = {
        **report_data,
        "clause_analyses": [
            {
                key: value
                for key, value in clause.items()
                if key != "original_text"
            }
            for clause in report_data.get("clause_analyses", [])
        ],
    }
    return sanitized


@router.post("/api/review/stream")
async def review_contract_stream(
    request: ReviewStreamRequest,
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming contract review. Requires a paid order."""
    # Look up order
    result = await db.execute(select(Order).where(Order.id == request.order_id))
    order = result.scalar_one_or_none()

    if order is None:
        logger.warning("Review rejected: order_id=%s reason=order_not_found", request.order_id)
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status != "paid":
        logger.warning("Review rejected: order_id=%s reason=payment_required status=%s", order.id, order.payment_status)
        posthog_capture(
            order.email or str(order.id),
            "review_rejected",
            {"order_id": str(order.id), "reason": "payment_required", "payment_status": order.payment_status},
        )
        raise HTTPException(status_code=402, detail="Payment required")
    if order.analysis_status != "waiting":
        logger.warning("Review rejected: order_id=%s reason=analysis_not_waiting status=%s", order.id, order.analysis_status)
        posthog_capture(
            order.email or str(order.id),
            "review_rejected",
            {"order_id": str(order.id), "reason": "analysis_not_waiting", "analysis_status": order.analysis_status},
        )
        raise HTTPException(status_code=409, detail="Analysis already started or completed")
    preload_cost_context = set_cost_order_context(str(order.id))
    try:
        await _ensure_contract_text(order, db)
    finally:
        reset_cost_order_context(preload_cost_context)
    if not order.contract_text:
        logger.warning("Review rejected: order_id=%s reason=missing_contract_text", order.id)
        posthog_capture(
            order.email or str(order.id),
            "review_rejected",
            {"order_id": str(order.id), "reason": "missing_contract_text"},
        )
        raise HTTPException(status_code=422, detail="No contract text associated with this order")

    # Mark as processing
    order.analysis_status = "processing"
    await db.commit()
    logger.info("Review started: order_id=%s target_language=%s", order.id, order.target_language)

    posthog_capture(
        order.email or str(order.id),
        "review_started",
        {"order_id": str(order.id), "target_language": order.target_language},
    )

    contract_text = order.contract_text
    target_language = order.target_language
    order_id = str(order.id)
    email = order.email

    async def generate():
        final_report = None
        cost_context = set_cost_order_context(order_id)
        try:
            async for evt in run_review_stream(
                contract_text,
                target_language=target_language,
            ):
                if evt.get("type") == "complete" and "report" in evt:
                    final_report = evt["report"]
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("Review stream error for order %s: %s", order_id, e)
            if sentry_sdk:
                sentry_sdk.set_tag("order_id", order_id)
                sentry_sdk.capture_exception(e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            reset_cost_order_context(cost_context)

        # Post-analysis: save report, cache, email, clean up contract
        if final_report:
            try:
                persisted_report = _strip_clause_originals(final_report)
                cost_summary = get_order_cost_summary(order_id)
                if cost_summary:
                    cost_summary.update(
                        {
                            "input_type": order.input_type,
                            "quote_mode": order.quote_mode,
                            "estimate_source": order.estimate_source,
                            "page_estimate": order.page_estimate,
                            "estimated_tokens": order.estimated_tokens,
                            "target_language": target_language,
                            "total_clauses": persisted_report.get("total_clauses", 0),
                            "high_risk_count": persisted_report.get("high_risk_count", 0),
                            "medium_risk_count": persisted_report.get("medium_risk_count", 0),
                            "low_risk_count": persisted_report.get("low_risk_count", 0),
                        }
                    )
                report_payload = await _save_report(
                    order_id,
                    persisted_report,
                    target_language,
                    db,
                    cost_summary=cost_summary,
                )
                await cache_report(order_id, report_payload)
                email_sent = await send_report_email(email, order_id, target_language)
                await _finalize_order(order_id, db)
                if cost_summary:
                    logger.info("Order cost summary: %s", cost_summary)
                    clear_order_cost_summary(order_id)
                posthog_capture(
                    email or order_id,
                    "review_completed",
                    {
                        "order_id": order_id,
                        "overall_risk": persisted_report.get("overall_risk_level"),
                        "total_clauses": persisted_report.get("total_clauses", 0),
                        "email_sent": email_sent,
                    },
                )
                logger.info(
                    "Review completed: order_id=%s overall_risk=%s total_clauses=%s email_sent=%s",
                    order_id,
                    persisted_report.get("overall_risk_level"),
                    persisted_report.get("total_clauses", 0),
                    email_sent,
                )
            except Exception as e:
                logger.error("Post-analysis error for order %s: %s", order_id, e)
                posthog_capture(
                    email or order_id,
                    "review_post_analysis_failed",
                    {"order_id": order_id, "error": str(e)},
                )
                if sentry_sdk:
                    sentry_sdk.set_tag("order_id", order_id)
                    sentry_sdk.capture_exception(e)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _save_report(
    order_id: str,
    report_data: dict,
    language: str,
    db: AsyncSession,
    cost_summary: dict | None = None,
) -> dict:
    """Persist the analysis report to the database."""
    now = datetime.now(timezone.utc)
    report = Report(
        order_id=order_id,
        overall_risk_level=report_data.get("overall_risk_level", ""),
        summary=report_data.get("summary", ""),
        clause_analyses=report_data.get("clause_analyses", []),
        cost_summary=cost_summary,
        high_risk_count=report_data.get("high_risk_count", 0),
        medium_risk_count=report_data.get("medium_risk_count", 0),
        low_risk_count=report_data.get("low_risk_count", 0),
        total_clauses=report_data.get("total_clauses", 0),
        language=language,
        created_at=now,
        expires_at=now + timedelta(hours=24),
    )
    db.add(report)
    await db.commit()
    logger.info("Report saved: order_id=%s language=%s total_clauses=%s", order_id, language, report.total_clauses)
    return {
        "order_id": str(report.order_id),
        "report": {
            "overall_risk_level": report.overall_risk_level,
            "summary": report.summary,
            "clause_analyses": report.clause_analyses,
            "high_risk_count": report.high_risk_count,
            "medium_risk_count": report.medium_risk_count,
            "low_risk_count": report.low_risk_count,
            "total_clauses": report.total_clauses,
        },
        "language": report.language,
        "created_at": report.created_at.isoformat(),
        "expires_at": report.expires_at.isoformat(),
    }


async def _finalize_order(order_id: str, db: AsyncSession) -> None:
    """Mark order as completed and null out contract text."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order:
        temp_upload_token = order.temp_upload_token
        order.analysis_status = "completed"
        order.contract_text = None
        order.contract_deleted_at = datetime.now(timezone.utc)
        order.temp_upload_token = None
        order.temp_upload_name = None
        order.temp_upload_mime_type = None
        delete_temp_upload(temp_upload_token)
        await db.commit()
        logger.info("Order finalized: order_id=%s contract_text_deleted=true", order_id)


async def _ensure_contract_text(order: Order, db: AsyncSession) -> None:
    """Materialize contract text from staged uploads after payment and before analysis."""
    if order.contract_text or not order.temp_upload_token:
        return

    try:
        file_bytes = read_temp_upload(order.temp_upload_token)
    except FileNotFoundError:
        logger.warning("Staged upload missing before review: order_id=%s token=%s", order.id, order.temp_upload_token)
        return

    if order.input_type == "image":
        contract_text = await extract_text_from_image(file_bytes, order.temp_upload_mime_type or "image/jpeg")
    elif order.input_type == "pdf":
        contract_text = await extract_text_from_pdf(file_bytes)
    else:
        contract_text = ""

    if contract_text.strip():
        order.contract_text = contract_text
        await db.commit()
        logger.info(
            "Contract text materialized before review: order_id=%s input_type=%s quote_mode=%s",
            order.id,
            order.input_type,
            order.quote_mode,
        )
