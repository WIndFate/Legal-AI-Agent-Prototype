import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.order import Order
from backend.schemas.order import ReviewStreamRequest
from backend.agent.graph import run_review_stream

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
        return {"error": "Order not found"}
    if order.payment_status != "paid":
        return {"error": "Payment required"}
    if order.analysis_status != "waiting":
        return {"error": "Analysis already started or completed"}

    # Mark as processing
    order.analysis_status = "processing"
    await db.commit()

    async def generate():
        try:
            async for evt in run_review_stream(
                order.contract_text,
                target_language=order.target_language,
            ):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Review stream error for order {order.id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
