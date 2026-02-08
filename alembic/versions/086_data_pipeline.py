"""PRD-86: Data Pipeline.

Revision ID: 086
Revises: 085
"""

from alembic import op
import sqlalchemy as sa

revision = "086"
down_revision = "085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pipeline execution tracking
    op.create_table(
        "pipeline_run_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pipeline_name", sa.String(100), nullable=False, index=True),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("records_processed", sa.Integer(), server_default="0"),
        sa.Column("records_failed", sa.Integer(), server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # Data quality metric snapshots
    op.create_table(
        "data_quality_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False, index=True),
        sa.Column("dataset", sa.String(100), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("null_pct", sa.Float(), nullable=True),
        sa.Column("duplicate_count", sa.Integer(), server_default="0"),
        sa.Column("validation_passed", sa.Boolean(), nullable=False),
        sa.Column("checks_run", sa.Integer(), server_default="0"),
        sa.Column("checks_failed", sa.Integer(), server_default="0"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("measured_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("data_quality_metrics")
    op.drop_table("pipeline_run_log")
