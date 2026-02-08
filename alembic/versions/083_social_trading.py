"""PRD-83: Social Trading.

Revision ID: 083
Revises: 082
"""

from alembic import op
import sqlalchemy as sa

revision = "083"
down_revision = "082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Social platform analytics
    op.create_table(
        "social_analytics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("metric_type", sa.String(50), nullable=False, index=True),
        sa.Column("total_users", sa.Integer(), server_default="0"),
        sa.Column("active_users", sa.Integer(), server_default="0"),
        sa.Column("total_strategies", sa.Integer(), server_default="0"),
        sa.Column("active_copies", sa.Integer(), server_default="0"),
        sa.Column("total_posts", sa.Integer(), server_default="0"),
        sa.Column("total_interactions", sa.Integer(), server_default="0"),
        sa.Column("avg_engagement_rate", sa.Float(), nullable=True),
        sa.Column("top_strategy_id", sa.String(36), nullable=True),
        sa.Column("snapshot_date", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Copy trade execution log
    op.create_table(
        "copy_trade_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("copy_id", sa.String(36), nullable=False, index=True),
        sa.Column("leader_user_id", sa.String(36), nullable=False),
        sa.Column("copier_user_id", sa.String(36), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("leader_quantity", sa.Float(), nullable=False),
        sa.Column("copy_quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("copy_trade_executions")
    op.drop_table("social_analytics")
