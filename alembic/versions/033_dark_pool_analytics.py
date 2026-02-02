"""Dark pool analytics system tables.

Revision ID: 033
Revises: 032
Create Date: 2026-02-01

Adds:
- dark_pool_volume: Daily dark pool volume records
- dark_prints: Individual dark print records
- dark_blocks: Detected block trades
- dark_liquidity: Liquidity estimation snapshots
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dark pool volume
    op.create_table(
        "dark_pool_volume",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("dark_volume", sa.Float),
        sa.Column("lit_volume", sa.Float),
        sa.Column("total_volume", sa.Float),
        sa.Column("dark_share", sa.Float),
        sa.Column("short_volume", sa.Float),
        sa.Column("short_ratio", sa.Float),
        sa.Column("n_venues", sa.Integer),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_dark_pool_volume_symbol", "dark_pool_volume", ["symbol"])
    op.create_index("ix_dark_pool_volume_date", "dark_pool_volume", ["date"])

    # Dark prints
    op.create_table(
        "dark_prints",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("price", sa.Float),
        sa.Column("size", sa.Float),
        sa.Column("timestamp", sa.Float),
        sa.Column("venue", sa.String(50)),
        sa.Column("print_type", sa.String(20)),
        sa.Column("price_improvement", sa.Float),
        sa.Column("notional", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_dark_prints_symbol", "dark_prints", ["symbol"])

    # Dark blocks
    op.create_table(
        "dark_blocks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("size", sa.Float),
        sa.Column("notional", sa.Float),
        sa.Column("price", sa.Float),
        sa.Column("direction", sa.String(10)),
        sa.Column("adv_ratio", sa.Float),
        sa.Column("venue", sa.String(50)),
        sa.Column("timestamp", sa.Float),
        sa.Column("cluster_id", sa.Integer),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_dark_blocks_symbol", "dark_blocks", ["symbol"])

    # Dark liquidity
    op.create_table(
        "dark_liquidity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("liquidity_score", sa.Float),
        sa.Column("level", sa.String(20)),
        sa.Column("estimated_depth", sa.Float),
        sa.Column("dark_lit_ratio", sa.Float),
        sa.Column("consistency", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_dark_liquidity_symbol", "dark_liquidity", ["symbol"])


def downgrade() -> None:
    op.drop_table("dark_liquidity")
    op.drop_table("dark_blocks")
    op.drop_table("dark_prints")
    op.drop_table("dark_pool_volume")
