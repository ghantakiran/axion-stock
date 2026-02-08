"""PRD-112: Data Pipeline Orchestration.

Revision ID: 112
Revises: 111
"""
from alembic import op
import sqlalchemy as sa

revision = "112"
down_revision = "111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("pipeline_id", sa.String(128), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total_nodes", sa.Integer, nullable=True),
        sa.Column("completed_nodes", sa.Integer, nullable=True),
        sa.Column("failed_nodes", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "pipeline_nodes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False, index=True),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("retries_used", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pipeline_nodes")
    op.drop_table("pipeline_runs")
