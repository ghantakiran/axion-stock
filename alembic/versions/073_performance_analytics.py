"""PRD-73: Performance Analytics.

Revision ID: 073
Revises: 072
"""

from alembic import op
import sqlalchemy as sa

revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Performance attribution snapshots (scheduled captures)
    op.create_table(
        "attribution_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("portfolio_id", sa.String(36), nullable=False, index=True),
        sa.Column("snapshot_type", sa.String(30), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("benchmark", sa.String(20), nullable=True),
        sa.Column("total_return", sa.Float(), nullable=True),
        sa.Column("active_return", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("tracking_error", sa.Float(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Saved benchmark configurations
    op.create_table(
        "custom_benchmarks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("benchmark_type", sa.String(20), nullable=False),
        sa.Column("components", sa.JSON(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("custom_benchmarks")
    op.drop_table("attribution_snapshots")
