import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select

from backend.agent.graph import run_review_stream
from backend.agent.nodes import NON_CONTRACT_ERROR_CODE, NonContractDocumentError
from backend.db.session import get_session_factory
from backend.models.analysis_event import AnalysisEvent
from backend.models.analysis_job import AnalysisJob
from backend.models.order import Order
from backend.models.order_cost_estimate import OrderCostEstimate
from backend.services.analytics import capture as posthog_capture
from backend.services.analytics import capture_exception as sentry_capture_exception
from backend.services.costing import (
    clear_order_cost_summary,
    get_order_cost_summary,
    reset_cost_order_context,
    set_cost_order_context,
)
from backend.services.email import send_report_email
from backend.services.event_bus import event_bus
from backend.services.order_cost_estimate import (
    build_order_cost_actual_snapshot,
    build_order_cost_comparison_snapshot,
    clear_order_cost_actuals,
    upsert_order_cost_estimate,
)
from backend.services.report_cache import cache_report
from backend.services.report_persistence import ensure_contract_text, finalize_order, save_report, strip_clause_originals

logger = logging.getLogger(__name__)

_running_tasks: dict[str, asyncio.Task] = {}

STEP_BY_NODE = {
    "parse_contract": "parsing",
    "analyze_risks": "analyzing",
    "generate_report": "generating",
}


def _normalize_step(event: dict, fallback: str | None = None) -> str | None:
    node = event.get("node")
    if node in STEP_BY_NODE:
        return STEP_BY_NODE[node]
    return fallback


def _build_cost_summary_snapshot(order_id: str, order: Order | None = None, report_data: dict | None = None) -> dict | None:
    cost_summary = get_order_cost_summary(order_id)
    if not cost_summary:
        return None

    if order is not None:
        cost_summary.update(
            {
                "input_type": order.input_type,
                "quote_mode": order.quote_mode,
                "estimate_source": order.estimate_source,
                "page_estimate": order.page_estimate,
                "estimated_tokens": order.estimated_tokens,
                "target_language": order.target_language,
            }
        )

    if report_data is not None:
        cost_summary.update(
            {
                "total_clauses": report_data.get("total_clauses", 0),
                "high_risk_count": report_data.get("high_risk_count", 0),
                "medium_risk_count": report_data.get("medium_risk_count", 0),
                "low_risk_count": report_data.get("low_risk_count", 0),
            }
        )

    return cost_summary


def _error_payload(exc: Exception) -> tuple[str, dict]:
    if isinstance(exc, NonContractDocumentError):
        return NON_CONTRACT_ERROR_CODE, {
            "type": "error",
            "message": str(exc),
            "error_code": NON_CONTRACT_ERROR_CODE,
        }
    return "analysis_failed", {
        "type": "error",
        "message": str(exc),
    }


async def _append_event(
    session,
    job: AnalysisJob,
    event: dict,
    *,
    terminal_status: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict:
    next_seq = job.progress_seq + 1
    step = _normalize_step(event, job.current_step)
    message = event.get("label") or event.get("text") or event.get("message")
    now = datetime.now(timezone.utc)

    record = AnalysisEvent(
        job_id=job.id,
        seq=next_seq,
        event_type=event["type"],
        step=step,
        message=message,
        payload_json=event,
        created_at=now,
    )
    session.add(record)

    job.progress_seq = next_seq
    job.current_step = step
    job.progress_message = message
    job.last_event_at = now
    if terminal_status == "completed":
        job.status = "completed"
        job.finished_at = now
        job.error_code = None
        job.error_message = None
    elif terminal_status == "failed":
        job.status = "failed"
        job.failed_at = now
        job.error_code = error_code
        job.error_message = error_message or message

    await session.commit()
    payload = {
        "seq": next_seq,
        "event_type": event["type"],
        "step": step,
        "message": message,
        "payload_json": event,
        "created_at": now.isoformat(),
    }
    await event_bus.publish(str(job.order_id), payload)
    return payload


async def _run_analysis(job_id: str, order_id: str) -> None:
    factory = get_session_factory()
    final_report = None
    email = None
    target_language = "ja"
    cost_context = None

    try:
        async with factory() as session:
            result = await session.execute(
                select(AnalysisJob, Order).join(Order, AnalysisJob.order_id == Order.id).where(AnalysisJob.id == job_id)
            )
            row = result.first()
            if row is None:
                logger.warning("Analysis executor missing job: job_id=%s", job_id)
                return
            job, order = row
            email = order.email
            target_language = order.target_language

            cost_context = set_cost_order_context(order_id)
            await ensure_contract_text(order, session)
            if not order.contract_text:
                job.cost_summary = _build_cost_summary_snapshot(order_id, order)
                estimate_record = (
                    await session.execute(select(OrderCostEstimate).where(OrderCostEstimate.order_id == order.id))
                ).scalar_one_or_none()
                actual_snapshot = build_order_cost_actual_snapshot(
                    order,
                    job.cost_summary,
                    estimate_snapshot=estimate_record.estimate_snapshot if estimate_record else None,
                )
                estimate_record = await upsert_order_cost_estimate(
                    session,
                    order=order,
                    actual_snapshot=actual_snapshot,
                )
                comparison_snapshot = build_order_cost_comparison_snapshot(
                    estimate_record.estimate_snapshot,
                    actual_snapshot,
                )
                if comparison_snapshot is not None:
                    await upsert_order_cost_estimate(
                        session,
                        order=order,
                        comparison_snapshot=comparison_snapshot,
                    )
                await _append_event(
                    session,
                    job,
                    {"type": "error", "message": "No contract text associated with this order"},
                    terminal_status="failed",
                    error_message="No contract text associated with this order",
                )
                order.analysis_status = "failed"
                await session.commit()
                clear_order_cost_summary(order_id)
                return

            now = datetime.now(timezone.utc)
            job.status = "processing"
            job.started_at = job.started_at or now
            job.last_event_at = now
            order.analysis_status = "processing"
            await session.commit()
            contract_text = order.contract_text

        try:
            async for evt in run_review_stream(contract_text, target_language=target_language):
                if evt["type"] == "token":
                    continue
                async with factory() as session:
                    job = await session.get(AnalysisJob, job_id)
                    if job is None:
                        return
                    await _append_event(session, job, evt)
                if evt["type"] == "complete" and "report" in evt:
                    final_report = evt["report"]
        except Exception as exc:
            async with factory() as session:
                job = await session.get(AnalysisJob, job_id)
                order = await session.get(Order, order_id)
                if job is not None and order is not None:
                    error_code, error_event = _error_payload(exc)
                    job.cost_summary = _build_cost_summary_snapshot(order_id, order)
                    estimate_record = (
                        await session.execute(select(OrderCostEstimate).where(OrderCostEstimate.order_id == order.id))
                    ).scalar_one_or_none()
                    actual_snapshot = build_order_cost_actual_snapshot(
                        order,
                        job.cost_summary,
                        estimate_snapshot=estimate_record.estimate_snapshot if estimate_record else None,
                    )
                    estimate_record = await upsert_order_cost_estimate(
                        session,
                        order=order,
                        actual_snapshot=actual_snapshot,
                    )
                    comparison_snapshot = build_order_cost_comparison_snapshot(
                        estimate_record.estimate_snapshot,
                        actual_snapshot,
                    )
                    if comparison_snapshot is not None:
                        await upsert_order_cost_estimate(
                            session,
                            order=order,
                            comparison_snapshot=comparison_snapshot,
                        )
                    await _append_event(
                        session,
                        job,
                        error_event,
                        terminal_status="failed",
                        error_code=error_code,
                        error_message=str(exc),
                    )
                if order is not None:
                    order.analysis_status = "failed"
                    await session.commit()
                clear_order_cost_summary(order_id)
            logger.exception("Analysis executor failed: job_id=%s order_id=%s", job_id, order_id)
            posthog_capture(email or order_id, "analysis_failed", {"order_id": order_id, "job_id": job_id, "error": str(exc)})
            # NonContractDocumentError is an expected business outcome, not an
            # incident — only forward unexpected failures to Sentry.
            if not isinstance(exc, NonContractDocumentError):
                sentry_capture_exception(
                    exc,
                    tags={"component": "analysis_executor", "order_id": order_id, "job_id": job_id},
                )
            return
        finally:
            reset_cost_order_context(cost_context)

        if final_report is None:
            async with factory() as session:
                job = await session.get(AnalysisJob, job_id)
                order = await session.get(Order, order_id)
                if job is not None and order is not None:
                    job.cost_summary = _build_cost_summary_snapshot(order_id, order)
                    estimate_record = (
                        await session.execute(select(OrderCostEstimate).where(OrderCostEstimate.order_id == order.id))
                    ).scalar_one_or_none()
                    actual_snapshot = build_order_cost_actual_snapshot(
                        order,
                        job.cost_summary,
                        estimate_snapshot=estimate_record.estimate_snapshot if estimate_record else None,
                    )
                    estimate_record = await upsert_order_cost_estimate(
                        session,
                        order=order,
                        actual_snapshot=actual_snapshot,
                    )
                    comparison_snapshot = build_order_cost_comparison_snapshot(
                        estimate_record.estimate_snapshot,
                        actual_snapshot,
                    )
                    if comparison_snapshot is not None:
                        await upsert_order_cost_estimate(
                            session,
                            order=order,
                            comparison_snapshot=comparison_snapshot,
                        )
                    await _append_event(
                        session,
                        job,
                        {"type": "error", "message": "Analysis finished without a report"},
                        terminal_status="failed",
                        error_message="Analysis finished without a report",
                    )
                if order is not None:
                    order.analysis_status = "failed"
                    await session.commit()
                clear_order_cost_summary(order_id)
            return

        async with factory() as session:
            job = await session.get(AnalysisJob, job_id)
            order = await session.get(Order, order_id)
            if job is None or order is None:
                return

            persisted_report = strip_clause_originals(final_report)
            cost_summary = _build_cost_summary_snapshot(order_id, order, persisted_report)
            if cost_summary:
                job.cost_summary = cost_summary
            estimate_record = (
                await session.execute(select(OrderCostEstimate).where(OrderCostEstimate.order_id == order.id))
            ).scalar_one_or_none()
            actual_snapshot = build_order_cost_actual_snapshot(
                order,
                cost_summary,
                persisted_report,
                estimate_record.estimate_snapshot if estimate_record else None,
            )
            comparison_snapshot = None
            if actual_snapshot is not None:
                estimate_record = await upsert_order_cost_estimate(session, order=order, actual_snapshot=actual_snapshot)
                comparison_snapshot = build_order_cost_comparison_snapshot(
                    estimate_record.estimate_snapshot,
                    actual_snapshot,
                )
                if comparison_snapshot is not None:
                    await upsert_order_cost_estimate(
                        session,
                        order=order,
                        comparison_snapshot=comparison_snapshot,
                    )
            report_payload = await save_report(order_id, persisted_report, target_language, session, cost_summary=cost_summary)
            await cache_report(order_id, report_payload)
            email_sent = await send_report_email(email, order_id, target_language, order.access_token)
            await finalize_order(order_id, session)

            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            job.progress_message = "Analysis completed"
            await session.commit()
            await _append_event(session, job, {"type": "complete", "report_ready": True}, terminal_status="completed")

            if cost_summary:
                logger.info("Order cost summary: %s", cost_summary)
                clear_order_cost_summary(order_id)
            posthog_capture(
                email or order_id,
                "analysis_completed",
                {
                    "order_id": order_id,
                    "job_id": job_id,
                    "overall_risk": persisted_report.get("overall_risk_level"),
                    "total_clauses": persisted_report.get("total_clauses", 0),
                    "email_sent": email_sent,
                },
            )
    finally:
        if cost_context is not None:
            reset_cost_order_context(cost_context)
        _running_tasks.pop(order_id, None)


async def launch_analysis(job_id: str, order_id: str) -> asyncio.Task:
    task = _running_tasks.get(order_id)
    if task and not task.done():
        return task
    task = asyncio.create_task(_run_analysis(job_id, order_id), name=f"analysis:{order_id}")
    _running_tasks[order_id] = task
    return task


def is_analysis_running(order_id: str) -> bool:
    task = _running_tasks.get(order_id)
    return task is not None and not task.done()


async def reset_failed_job(job_id: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        job = await session.get(AnalysisJob, job_id)
        if job is None:
            return
        await session.execute(delete(AnalysisEvent).where(AnalysisEvent.job_id == job.id))
        job.status = "queued"
        job.current_step = None
        job.progress_message = None
        job.progress_seq = 0
        job.cost_summary = None
        job.error_code = None
        job.error_message = None
        job.failed_at = None
        clear_order_cost_summary(str(job.order_id))
        await clear_order_cost_actuals(session, str(job.order_id))
        job.finished_at = None
        job.last_event_at = None
        order = await session.get(Order, job.order_id)
        if order is not None:
            order.analysis_status = "waiting"
        await session.commit()
