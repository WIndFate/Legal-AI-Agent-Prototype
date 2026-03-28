import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.config import get_settings
from backend.models.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    overall_risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    clause_analyses: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cost_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    high_risk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    medium_risk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_risk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_clauses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=get_settings().REPORT_TTL_HOURS),
        index=True,
    )
