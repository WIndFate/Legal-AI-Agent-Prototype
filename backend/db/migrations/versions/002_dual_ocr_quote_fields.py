"""Add dual OCR quote fields to orders

Revision ID: 002
Revises: 001
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("quote_mode", sa.String(length=32), nullable=False, server_default="exact"))
    op.add_column("orders", sa.Column("estimate_source", sa.String(length=32), nullable=False, server_default="raw_text"))
    op.add_column("orders", sa.Column("temp_upload_token", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("temp_upload_name", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("temp_upload_mime_type", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "temp_upload_mime_type")
    op.drop_column("orders", "temp_upload_name")
    op.drop_column("orders", "temp_upload_token")
    op.drop_column("orders", "estimate_source")
    op.drop_column("orders", "quote_mode")
