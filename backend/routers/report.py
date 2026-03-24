import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.report import Report
from backend.services.report_cache import get_cached_report
from backend.services.analytics import capture as posthog_capture

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/report/{order_id}")
async def get_report(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get analysis report by order ID. Checks Redis cache first, then DB."""
    posthog_capture("anonymous", "report_viewed", {"order_id": order_id})

    # Try Redis cache first
    cached = await get_cached_report(order_id)
    if cached:
        return cached

    # Fallback to DB
    result = await db.execute(select(Report).where(Report.order_id == order_id))
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or expired")

    # Check expiry
    if report.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Report expired")

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
