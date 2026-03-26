"""Add indexes for common query paths

Revision ID: 004
Revises: 003
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # payment_status and reports.expires_at already exist in revision 001.
    # This revision only adds the missing analysis_status index.
    op.create_index("ix_orders_analysis_status", "orders", ["analysis_status"])


def downgrade() -> None:
    op.drop_index("ix_orders_analysis_status", table_name="orders")
