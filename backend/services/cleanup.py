import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session_factory
from backend.models.analysis_event import AnalysisEvent
from backend.models.analysis_job import AnalysisJob
from backend.models.order import Order
from backend.models.order_cost_estimate import OrderCostEstimate
from backend.models.report import Report
from backend.config import get_settings
from backend.services.costing import clear_order_cost_summary, get_order_cost_summary
from backend.services.order_cost_estimate import (
    build_order_cost_actual_snapshot,
    build_order_cost_comparison_snapshot,
    upsert_order_cost_estimate,
)
from backend.services.temp_uploads import delete_temp_upload

logger = logging.getLogger(__name__)
settings = get_settings()


async def cleanup_expired_reports() -> int:
    """Delete reports past their expires_at timestamp. Returns count deleted."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            delete(Report).where(Report.expires_at < datetime.now(timezone.utc))
        )
        await session.commit()
        count = result.rowcount
        if count:
            logger.info("Deleted %d expired reports", count)
        return count


async def nullify_completed_contracts() -> int:
    """Null out contract_text for completed orders (privacy compliance)."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            update(Order)
            .where(
                and_(
                    Order.analysis_status == "completed",
                    Order.contract_text.isnot(None),
                )
            )
            .values(contract_text=None, contract_deleted_at=datetime.now(timezone.utc))
        )
        await session.commit()
        count = result.rowcount
        if count:
            logger.info("Nullified contract_text for %d completed orders", count)
        return count


async def cleanup_staged_uploads() -> int:
    """Delete staged uploads once they are no longer needed."""
    factory = get_session_factory()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.REPORT_TTL_HOURS)
    async with factory() as session:
        result = await session.execute(
            select(Order).where(
                Order.temp_upload_token.isnot(None),
                or_(
                    Order.analysis_status == "completed",
                    and_(
                        Order.payment_status != "paid",
                        Order.created_at < cutoff,
                    ),
                ),
            )
        )
        orders = list(result.scalars().all())
        for order in orders:
            delete_temp_upload(order.temp_upload_token)
            order.temp_upload_token = None
            order.temp_upload_name = None
            order.temp_upload_mime_type = None
        await session.commit()
        if orders:
            logger.info("Deleted %d staged upload files", len(orders))
        return len(orders)


async def fail_stale_analysis_jobs() -> int:
    """Mark long-stuck processing jobs as failed."""
    factory = get_session_factory()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    async with factory() as session:
        result = await session.execute(
            select(AnalysisJob, Order)
            .join(Order, AnalysisJob.order_id == Order.id)
            .where(
                AnalysisJob.status == "processing",
                or_(
                    AnalysisJob.last_event_at.is_(None),
                    AnalysisJob.last_event_at < cutoff,
                ),
            )
        )
        rows = list(result.all())
        now = datetime.now(timezone.utc)
        for job, order in rows:
            cost_summary = get_order_cost_summary(str(order.id))
            if cost_summary:
                job.cost_summary = cost_summary
                estimate_record = (
                    await session.execute(select(OrderCostEstimate).where(OrderCostEstimate.order_id == order.id))
                ).scalar_one_or_none()
                actual_snapshot = build_order_cost_actual_snapshot(
                    order,
                    cost_summary,
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
            job.status = "failed"
            job.error_message = "Analysis timed out"
            job.failed_at = now
            order.analysis_status = "failed"
        await session.commit()
        for _, order in rows:
            clear_order_cost_summary(str(order.id))
        if rows:
            logger.info("Marked %d stale analysis jobs as failed", len(rows))
        return len(rows)


async def cleanup_expired_analysis_events() -> int:
    """Delete old analysis events after report/event retention window."""
    factory = get_session_factory()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.REPORT_TTL_HOURS)
    async with factory() as session:
        result = await session.execute(
            delete(AnalysisEvent).where(AnalysisEvent.created_at < cutoff)
        )
        await session.commit()
        count = result.rowcount
        if count:
            logger.info("Deleted %d expired analysis events", count)
        return count


async def run_cleanup() -> None:
    """Run all cleanup tasks. Called by APScheduler."""
    await fail_stale_analysis_jobs()
    await cleanup_expired_reports()
    await cleanup_expired_analysis_events()
    await nullify_completed_contracts()
    await cleanup_staged_uploads()
