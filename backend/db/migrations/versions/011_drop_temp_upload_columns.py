"""Drop unused temp_upload_* columns from orders

Revision ID: 011_drop_temp_upload_columns
Revises: 010_orders_client_ip
Create Date: 2026-04-17

These columns were introduced in migration 002 to stage raw upload bytes for a
post-payment re-OCR pass (dual-OCR flow). After the migration from GPT-4o
Vision to Google Cloud Vision DOCUMENT_TEXT_DETECTION, pre-payment OCR now
returns the final contract_text, and the staging path became unreachable —
stage_temp_upload() was never called from production code. The columns have
been NULL for every row they ever held.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "011_drop_temp_upload_columns"
down_revision: Union[str, None] = "010_orders_client_ip"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF EXISTS because older deploys that ran create_all before stamping
    # may have skipped migration 002 entirely, in which case these columns
    # never existed and a plain DROP would fail.
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS temp_upload_mime_type")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS temp_upload_name")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS temp_upload_token")


def downgrade() -> None:
    op.add_column("orders", sa.Column("temp_upload_token", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("temp_upload_name", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("temp_upload_mime_type", sa.String(length=100), nullable=True))
