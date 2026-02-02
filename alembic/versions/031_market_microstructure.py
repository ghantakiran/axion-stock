"""Market microstructure system tables.

Revision ID: 031
Revises: 030
Create Date: 2026-02-01

Adds:
- spread_snapshots_ms: Spread metric snapshots
- orderbook_snapshots: Order book state snapshots
- tick_metrics: Tick-level aggregated metrics
- impact_estimates: Price impact estimates
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Spread snapshots
    op.create_table(
        "spread_snapshots_ms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("quoted_spread", sa.Float),
        sa.Column("quoted_spread_bps", sa.Float),
        sa.Column("effective_spread", sa.Float),
        sa.Column("effective_spread_bps", sa.Float),
        sa.Column("realized_spread", sa.Float),
        sa.Column("realized_spread_bps", sa.Float),
        sa.Column("roll_spread", sa.Float),
        sa.Column("adverse_selection", sa.Float),
        sa.Column("adverse_selection_bps", sa.Float),
        sa.Column("midpoint", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_spread_snapshots_ms_symbol", "spread_snapshots_ms", ["symbol"])

    # Order book snapshots
    op.create_table(
        "orderbook_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("imbalance", sa.Float),
        sa.Column("bid_depth", sa.Float),
        sa.Column("ask_depth", sa.Float),
        sa.Column("weighted_midpoint", sa.Float),
        sa.Column("book_pressure", sa.Float),
        sa.Column("bid_slope", sa.Float),
        sa.Column("ask_slope", sa.Float),
        sa.Column("resilience", sa.Float),
        sa.Column("spread", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_orderbook_snapshots_symbol", "orderbook_snapshots", ["symbol"])

    # Tick metrics
    op.create_table(
        "tick_metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("total_trades", sa.Integer),
        sa.Column("total_volume", sa.Float),
        sa.Column("buy_volume", sa.Float),
        sa.Column("sell_volume", sa.Float),
        sa.Column("vwap", sa.Float),
        sa.Column("twap", sa.Float),
        sa.Column("tick_to_trade_ratio", sa.Float),
        sa.Column("kyle_lambda", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_tick_metrics_symbol", "tick_metrics", ["symbol"])

    # Impact estimates
    op.create_table(
        "impact_estimates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("order_size", sa.Float),
        sa.Column("temporary_impact_bps", sa.Float),
        sa.Column("permanent_impact_bps", sa.Float),
        sa.Column("total_impact_bps", sa.Float),
        sa.Column("cost_dollars", sa.Float),
        sa.Column("participation_rate", sa.Float),
        sa.Column("daily_volume", sa.Float),
        sa.Column("volatility", sa.Float),
        sa.Column("model_used", sa.String(30)),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_impact_estimates_symbol", "impact_estimates", ["symbol"])


def downgrade() -> None:
    op.drop_table("impact_estimates")
    op.drop_table("tick_metrics")
    op.drop_table("orderbook_snapshots")
    op.drop_table("spread_snapshots_ms")
