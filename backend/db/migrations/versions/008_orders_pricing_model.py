"""replace orders price_tier with pricing_model

Revision ID: 008_orders_pricing_model
Revises: 007_order_cost_estimates
Create Date: 2026-03-28 23:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "008_orders_pricing_model"
down_revision = "007_order_cost_estimates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("pricing_model", sa.String(length=32), nullable=True, server_default="token_linear"),
    )
    op.execute(
        """
        UPDATE orders
        SET pricing_model = CASE
            WHEN price_tier IS NULL OR price_tier = '' THEN 'token_linear'
            WHEN price_tier = 'token_linear' THEN 'token_linear'
            ELSE 'token_linear'
        END
        """
    )
    op.alter_column("orders", "pricing_model", nullable=False, server_default="token_linear")
    op.drop_column("orders", "price_tier")


def downgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("price_tier", sa.String(length=20), nullable=False, server_default="token_linear"),
    )
    op.execute(
        """
        UPDATE orders
        SET price_tier = CASE
            WHEN pricing_model IS NULL OR pricing_model = '' THEN 'token_linear'
            ELSE pricing_model
        END
        """
    )
    op.alter_column("orders", "price_tier", nullable=False, server_default=None)
    op.drop_column("orders", "pricing_model")
