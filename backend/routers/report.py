import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.report import Report
from backend.services.analytics import capture as posthog_capture
from backend.services.report_cache import get_cached_report
from backend.services.report_pdf import renderer as report_pdf_renderer

logger = logging.getLogger(__name__)

router = APIRouter()


async def _load_report_row(order_id: str, db: AsyncSession) -> Report:
    result = await db.execute(select(Report).where(Report.order_id == order_id))
    report = result.scalar_one_or_none()

    if report is None:
        logger.warning("Report lookup failed: order_id=%s reason=not_found", order_id)
        posthog_capture("anonymous", "report_lookup_failed", {"order_id": order_id, "reason": "not_found"})
        raise HTTPException(status_code=404, detail="Report not found or expired")

    if report.expires_at < datetime.now(timezone.utc):
        logger.warning("Report lookup failed: order_id=%s reason=expired", order_id)
        posthog_capture("anonymous", "report_lookup_failed", {"order_id": order_id, "reason": "expired"})
        raise HTTPException(status_code=404, detail="Report expired")

    return report


@router.get("/api/report/{order_id}")
async def get_report(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get analysis report by order ID. Checks Redis cache first, then DB."""
    # Try Redis cache first
    cached = await get_cached_report(order_id)
    if cached and "report" in cached:
        logger.debug("Report cache hit: order_id=%s", order_id)
        posthog_capture("anonymous", "report_viewed", {"order_id": order_id, "source": "redis"})
        return cached
    if cached:
        logger.warning("Legacy report cache shape detected: order_id=%s; falling back to database", order_id)
    logger.info("Report cache miss: order_id=%s", order_id)
    posthog_capture("anonymous", "report_cache_miss", {"order_id": order_id})

    # Fallback to DB
    report = await _load_report_row(order_id, db)

    logger.info("Report loaded from database: order_id=%s language=%s", order_id, report.language)
    posthog_capture("anonymous", "report_viewed", {"order_id": order_id, "source": "database"})

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


@router.get("/api/report/{order_id}/pdf")
async def download_report_pdf(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    report = await _load_report_row(order_id, db)

    pdf_bytes = report_pdf_renderer.build_pdf(
        order_id=str(report.order_id),
        language=report.language,
        created_at=report.created_at.strftime("%Y-%m-%d %H:%M %Z"),
        expires_at=report.expires_at.strftime("%Y-%m-%d %H:%M %Z"),
        overall_risk_level=report.overall_risk_level,
        summary=report.summary,
        clause_analyses=report.clause_analyses or [],
        high_risk_count=report.high_risk_count,
        medium_risk_count=report.medium_risk_count,
        low_risk_count=report.low_risk_count,
        total_clauses=report.total_clauses,
    )
    filename = f"contractguard-report-{order_id}.pdf"
    logger.info("Report PDF generated: order_id=%s language=%s", order_id, report.language)
    posthog_capture("anonymous", "report_pdf_downloaded", {"order_id": order_id, "language": report.language})
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
