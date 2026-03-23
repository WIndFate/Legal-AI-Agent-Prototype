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
from backend.services.report_cache import cache_report
from backend.services.email import send_report_email

logger = logging.getLogger(__name__)

router = APIRouter()


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
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status != "paid":
        raise HTTPException(status_code=402, detail="Payment required")
    if order.analysis_status != "waiting":
        raise HTTPException(status_code=409, detail="Analysis already started or completed")
    if not order.contract_text:
        raise HTTPException(status_code=422, detail="No contract text associated with this order")

    # Mark as processing
    order.analysis_status = "processing"
    await db.commit()

    contract_text = order.contract_text
    target_language = order.target_language
    order_id = str(order.id)
    email = order.email

    async def generate():
        final_report = None
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
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        # Post-analysis: save report, cache, email, clean up contract
        if final_report:
            try:
                await _save_report(order_id, final_report, target_language, db)
                await cache_report(order_id, final_report)
                await send_report_email(email, order_id, target_language)
                await _finalize_order(order_id, db)
            except Exception as e:
                logger.error("Post-analysis error for order %s: %s", order_id, e)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _save_report(
    order_id: str, report_data: dict, language: str, db: AsyncSession
) -> None:
    """Persist the analysis report to the database."""
    now = datetime.now(timezone.utc)
    report = Report(
        order_id=order_id,
        overall_risk_level=report_data.get("overall_risk_level", ""),
        summary=report_data.get("summary", ""),
        clause_analyses=report_data.get("clause_analyses", []),
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
    logger.info("Report saved to DB for order %s", order_id)


async def _finalize_order(order_id: str, db: AsyncSession) -> None:
    """Mark order as completed and null out contract text."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order:
        order.analysis_status = "completed"
        order.contract_text = None
        order.contract_deleted_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("Order %s finalized: contract text deleted", order_id)
