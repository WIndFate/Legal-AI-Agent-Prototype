import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.analysis_event import AnalysisEvent
from backend.models.analysis_job import AnalysisJob
from backend.models.order import Order
from backend.models.report import Report
from backend.routers._helpers import parse_order_id
from backend.schemas.analysis import (
    AnalysisEventItem,
    AnalysisEventsResponse,
    AnalysisStartRequest,
    AnalysisStartResponse,
    OrderStatusResponse,
)
from backend.services.analysis_executor import is_analysis_running, launch_analysis, reset_failed_job
from backend.services.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/analysis/start", response_model=AnalysisStartResponse)
async def start_analysis(
    request: AnalysisStartRequest,
    db: AsyncSession = Depends(get_db),
):
    order_uuid = parse_order_id(request.order_id)
    order = await db.get(Order, order_uuid)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status != "paid":
        raise HTTPException(status_code=402, detail="Payment required")

    result = await db.execute(select(AnalysisJob).where(AnalysisJob.order_id == order.id))
    job = result.scalar_one_or_none()

    if job is None:
        job = AnalysisJob(order_id=order.id, status="queued", target_language=order.target_language)
        db.add(job)
        order.analysis_status = "waiting"
        await db.commit()
        await db.refresh(job)
    elif job.status == "failed":
        await reset_failed_job(str(job.id))
        await db.refresh(job)
    elif job.status in {"queued", "processing", "completed"}:
        if job.status in {"queued", "processing"} and not is_analysis_running(str(order.id)):
            await launch_analysis(str(job.id), str(order.id))
        return AnalysisStartResponse(job_id=str(job.id), order_id=str(order.id), status=job.status)

    await launch_analysis(str(job.id), str(order.id))
    return AnalysisStartResponse(job_id=str(job.id), order_id=str(order.id), status=job.status)


@router.get("/api/orders/{order_id}/status", response_model=OrderStatusResponse)
async def get_order_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    order_uuid = parse_order_id(order_id)
    order = await db.get(Order, order_uuid)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    job_result = await db.execute(select(AnalysisJob).where(AnalysisJob.order_id == order.id))
    job = job_result.scalar_one_or_none()
    report_result = await db.execute(select(Report.id).where(Report.order_id == order.id))
    report_ready = report_result.scalar_one_or_none() is not None

    if job is None:
        return OrderStatusResponse(
            order_id=str(order.id),
            payment_status=order.payment_status,
            analysis_status=order.analysis_status,
            report_ready=report_ready,
        )

    return OrderStatusResponse(
        order_id=str(order.id),
        payment_status=order.payment_status,
        analysis_status=job.status,
        current_step=job.current_step,
        progress_message=job.progress_message,
        progress_seq=job.progress_seq,
        report_ready=report_ready,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.get("/api/orders/{order_id}/events", response_model=AnalysisEventsResponse)
async def get_analysis_events(
    order_id: str,
    after_seq: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    order_uuid = parse_order_id(order_id)
    order = await db.get(Order, order_uuid)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.order_id == order.id))
    job = result.scalar_one_or_none()
    if job is None:
        return AnalysisEventsResponse(order_id=str(order.id), events=[])

    events_result = await db.execute(
        select(AnalysisEvent)
        .where(AnalysisEvent.job_id == job.id, AnalysisEvent.seq > after_seq)
        .order_by(AnalysisEvent.seq.asc())
        .limit(200)
    )
    events = [
        AnalysisEventItem(
            seq=event.seq,
            event_type=event.event_type,
            step=event.step,
            message=event.message,
            payload_json=event.payload_json,
            created_at=event.created_at,
        )
        for event in events_result.scalars().all()
    ]
    return AnalysisEventsResponse(order_id=str(order.id), events=events)


@router.get("/api/orders/{order_id}/stream")
async def stream_analysis_events(
    order_id: str,
    after_seq: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    order_uuid = parse_order_id(order_id)
    order = await db.get(Order, order_uuid)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.order_id == order.id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    events_result = await db.execute(
        select(AnalysisEvent)
        .where(AnalysisEvent.job_id == job.id, AnalysisEvent.seq > after_seq)
        .order_by(AnalysisEvent.seq.asc())
        .limit(200)
    )
    replay_events = list(events_result.scalars().all())
    terminal = job.status in {"completed", "failed"}

    async def generate():
        for event in replay_events:
            payload = {
                "seq": event.seq,
                "event_type": event.event_type,
                "step": event.step,
                "message": event.message,
                "payload_json": event.payload_json,
                "created_at": event.created_at.isoformat(),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        if terminal:
            return

        queue = await event_bus.subscribe(str(order.id))
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if payload["event_type"] in {"complete", "error"}:
                    return
        finally:
            await event_bus.unsubscribe(str(order.id), queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
