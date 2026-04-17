"""Add private access/share tokens for order-owned resources

Revision ID: 012_order_access_tokens
Revises: 011_drop_temp_upload_columns
Create Date: 2026-04-17
"""
from __future__ import annotations

import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "012_order_access_tokens"
down_revision: Union[str, None] = "011_drop_temp_upload_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


orders = sa.table(
    "orders",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("access_token", sa.String()),
    sa.column("share_token", sa.String()),
)


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def upgrade() -> None:
    op.add_column("orders", sa.Column("access_token", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("share_token", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.select(orders.c.id)).fetchall()
    for row in rows:
        bind.execute(
            orders.update()
            .where(orders.c.id == row.id)
            .values(access_token=_generate_token())
        )

    op.alter_column("orders", "access_token", existing_type=sa.String(length=64), nullable=False)


def downgrade() -> None:
    op.drop_column("orders", "share_token")
    op.drop_column("orders", "access_token")
