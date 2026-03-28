"""add analysis job cost summary

Revision ID: 006_analysis_job_cost_summary_and_72h_ttl
Revises: 005_analysis_jobs_and_events
Create Date: 2026-03-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "006_analysis_job_cost_summary_and_72h_ttl"
down_revision = "005_analysis_jobs_and_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_jobs",
        sa.Column("cost_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_jobs", "cost_summary")
