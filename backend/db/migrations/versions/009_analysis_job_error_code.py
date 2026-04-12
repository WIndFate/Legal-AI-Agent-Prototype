"""Add error_code column to analysis_jobs

Revision ID: 009_analysis_job_error_code
Revises: 008_orders_pricing_model
Create Date: 2026-04-13 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "009_analysis_job_error_code"
down_revision = "008_orders_pricing_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE analysis_jobs ADD COLUMN IF NOT EXISTS error_code VARCHAR(50)"
    )


def downgrade() -> None:
    op.drop_column("analysis_jobs", "error_code")
