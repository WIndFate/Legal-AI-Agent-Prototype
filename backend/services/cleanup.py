import logging
from datetime import datetime, timezone

from sqlalchemy import delete, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session_factory
from backend.models.order import Order
from backend.models.report import Report

logger = logging.getLogger(__name__)


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


async def run_cleanup() -> None:
    """Run all cleanup tasks. Called by APScheduler."""
    await cleanup_expired_reports()
    await nullify_completed_contracts()
