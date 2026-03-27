"""Add persistent analysis jobs and events

Revision ID: 005
Revises: 004
Create Date: 2026-03-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="waiting"),
        sa.Column("current_step", sa.String(length=30), nullable=True),
        sa.Column("progress_message", sa.String(length=500), nullable=True),
        sa.Column("progress_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_language", sa.String(length=10), nullable=False, server_default="ja"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])

    op.create_table(
        "analysis_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("step", sa.String(length=30), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "seq", name="uq_analysis_events_job_id_seq"),
    )
    op.create_index("ix_analysis_events_job_id", "analysis_events", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_events_job_id", table_name="analysis_events")
    op.drop_table("analysis_events")
    op.drop_index("ix_analysis_jobs_status", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
