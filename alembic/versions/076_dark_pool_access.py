"""PRD-76: Institutional Dark Pool Access.

Revision ID: 076
Revises: 075
"""

from alembic import op
import sqlalchemy as sa

revision = "076"
down_revision = "075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dark pool venue configurations
    op.create_table(
        "dark_pool_venues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("venue_type", sa.String(30), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("min_order_size", sa.Integer(), nullable=True),
        sa.Column("avg_fill_rate", sa.Float(), nullable=True),
        sa.Column("avg_price_improvement_bps", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Dark pool routing decisions audit
    op.create_table(
        "dark_pool_routing_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(36), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("venue_id", sa.String(36), nullable=True),
        sa.Column("liquidity_score", sa.Float(), nullable=True),
        sa.Column("routed_dark", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("fill_result", sa.String(20), nullable=True),
        sa.Column("price_improvement_bps", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("dark_pool_routing_log")
    op.drop_table("dark_pool_venues")
