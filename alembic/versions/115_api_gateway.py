"""PRD-115: API Gateway & Advanced Rate Limiting.

Revision ID: 115
Revises: 114
"""
from alembic import op
import sqlalchemy as sa

revision = "115"
down_revision = "114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_usage_records",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(64), nullable=False, index=True),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("user_id", sa.String(128), nullable=True, index=True),
        sa.Column("api_key", sa.String(64), nullable=True),
        sa.Column("tier", sa.String(32), nullable=True),
        sa.Column("version", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "api_quotas",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("tier", sa.String(32), nullable=False),
        sa.Column("daily_limit", sa.Integer, nullable=False),
        sa.Column("monthly_limit", sa.Integer, nullable=False),
        sa.Column("daily_used", sa.Integer, default=0),
        sa.Column("monthly_used", sa.Integer, default=0),
        sa.Column("last_reset_daily", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reset_monthly", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("api_quotas")
    op.drop_table("api_usage_records")
