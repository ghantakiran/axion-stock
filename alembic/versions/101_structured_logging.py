"""PRD-101: Structured Logging & Request Tracing.

Revision ID: 101
Revises: 100
"""

from alembic import op
import sqlalchemy as sa

revision = "101"
down_revision = "100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create request_logs table for persistent request trace storage
    op.create_table(
        "request_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(64), nullable=False, index=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("service", sa.String(64), default="axion"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create performance_logs table for slow operation tracking
    op.create_table(
        "performance_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("operation", sa.String(256), nullable=False),
        sa.Column("duration_ms", sa.Float, nullable=False),
        sa.Column("threshold_ms", sa.Float, nullable=True),
        sa.Column("is_slow", sa.Boolean, default=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("metadata", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("performance_logs")
    op.drop_table("request_logs")
