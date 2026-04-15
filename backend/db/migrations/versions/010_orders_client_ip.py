"""Add client_ip column to orders for abuse guard tracking

Revision ID: 010_orders_client_ip
Revises: 009_analysis_job_error_code
Create Date: 2026-04-15 00:00:00.000000
"""

from alembic import op


revision = "010_orders_client_ip"
down_revision = "009_analysis_job_error_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS client_ip VARCHAR(64)"
    )


def downgrade() -> None:
    op.drop_column("orders", "client_ip")
