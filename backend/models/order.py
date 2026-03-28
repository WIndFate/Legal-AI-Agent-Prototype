import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_type: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    page_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    pricing_model: Mapped[str] = mapped_column(String(32), nullable=False, default="token_linear")
    price_jpy: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="exact")
    estimate_source: Mapped[str] = mapped_column(String(32), nullable=False, default="raw_text")
    temp_upload_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temp_upload_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temp_upload_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    komoju_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting", index=True)
    target_language: Mapped[str] = mapped_column(String(10), nullable=False, default="ja")
    referral_code_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    contract_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
