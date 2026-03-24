"""Initial schema: orders, reports, referrals, legal_knowledge_embeddings

Revision ID: 001
Revises: None
Create Date: 2026-03-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Orders table
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("contract_text", sa.Text, nullable=True),
        sa.Column("input_type", sa.String(20), nullable=False),
        sa.Column("estimated_tokens", sa.Integer, nullable=False),
        sa.Column("page_estimate", sa.Integer, nullable=False),
        sa.Column("price_tier", sa.String(20), nullable=False),
        sa.Column("price_jpy", sa.Integer, nullable=False),
        sa.Column("komoju_session_id", sa.String(255), nullable=True),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_status", sa.String(20), nullable=False, server_default="waiting"),
        sa.Column("target_language", sa.String(10), nullable=False, server_default="ja"),
        sa.Column("referral_code_used", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("contract_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Reports table
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("overall_risk_level", sa.String(10), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("clause_analyses", postgresql.JSONB, nullable=False),
        sa.Column("high_risk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("medium_risk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("low_risk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_clauses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Referrals table
    op.create_table(
        "referrals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("referrer_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("referral_code", sa.String(50), nullable=False, unique=True),
        sa.Column("uses_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer, nullable=False, server_default="10"),
        sa.Column("discount_jpy", sa.Integer, nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Legal knowledge embeddings table (for pgvector RAG)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS legal_knowledge_embeddings (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            embedding vector(1536),
            metadata JSONB NOT NULL DEFAULT '{{}}'
        )
    """)

    # Add indexes for common queries
    op.create_index("ix_orders_email", "orders", ["email"])
    op.create_index("ix_orders_payment_status", "orders", ["payment_status"])
    op.create_index("ix_reports_expires_at", "reports", ["expires_at"])


def downgrade() -> None:
    op.drop_table("legal_knowledge_embeddings")
    op.drop_table("referrals")
    op.drop_table("reports")
    op.drop_table("orders")
    op.execute("DROP EXTENSION IF EXISTS vector")
