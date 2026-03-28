"""add order cost estimates table

Revision ID: 007_order_cost_estimates
Revises: 006_analysis_job_cost_summary_and_72h_ttl
Create Date: 2026-03-28 20:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "007_order_cost_estimates"
down_revision = "006_analysis_job_cost_summary_and_72h_ttl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_cost_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("estimate_version", sa.String(length=32), nullable=False),
        sa.Column("pricing_policy_version", sa.String(length=64), nullable=True),
        sa.Column("estimate_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actual_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("comparison_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(op.f("ix_order_cost_estimates_order_id"), "order_cost_estimates", ["order_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_cost_estimates_order_id"), table_name="order_cost_estimates")
    op.drop_table("order_cost_estimates")
