import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.order import Order
from backend.models.report import Report

logger = logging.getLogger(__name__)
settings = get_settings()


def strip_clause_originals(report_data: dict) -> dict:
    """Normalize persisted clause payload while keeping report-scoped clause excerpts."""
    return {
        **report_data,
        "clause_analyses": [
            {
                **clause,
                "original_text": clause.get("original_text", ""),
            }
            for clause in report_data.get("clause_analyses", [])
        ],
    }


async def save_report(
    order_id: str,
    report_data: dict,
    language: str,
    db: AsyncSession,
    cost_summary: dict | None = None,
) -> dict:
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
        expires_at=now + timedelta(hours=settings.REPORT_TTL_HOURS),
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


async def finalize_order(order_id: str, db: AsyncSession) -> None:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        return
    order.analysis_status = "completed"
    order.contract_text = None
    order.contract_deleted_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("Order finalized: order_id=%s contract_text_deleted=true", order_id)


async def ensure_contract_text(order: Order, db: AsyncSession) -> None:
    """Confirm the order already has contract_text before analysis.

    Google Vision OCR runs pre-payment, so `contract_text` is always populated
    by the time the order reaches this function. If it's missing, the caller
    must fail immediately — there is no longer a staged-upload re-OCR path.
    """
    if not order.contract_text:
        logger.warning("Order missing contract_text before analysis: order_id=%s", order.id)
        raise RuntimeError("No contract text associated with this order")
