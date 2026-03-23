import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.report import Report

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/report/{order_id}")
async def get_report(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get analysis report by order ID. Returns 404 if expired or not found."""
    result = await db.execute(select(Report).where(Report.order_id == order_id))
    report = result.scalar_one_or_none()

    if report is None:
        return {"error": "Report not found or expired", "status": 404}

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
