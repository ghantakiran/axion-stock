"""Order flow analysis system tables.

Revision ID: 028
Revises: 027
Create Date: 2026-02-01

Adds:
- orderbook_snapshots: Order book imbalance history
- block_trades: Detected large block trades
- flow_pressure: Buy/sell pressure measurements
- smart_money_signals: Smart money signal history
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Order book snapshots
    op.create_table(
        "orderbook_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("bid_volume", sa.Float),
        sa.Column("ask_volume", sa.Float),
        sa.Column("imbalance_ratio", sa.Float),
        sa.Column("imbalance_type", sa.String(16)),
        sa.Column("signal", sa.String(16)),
        sa.Column("timestamp", sa.DateTime),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_orderbook_snapshots_symbol", "orderbook_snapshots", ["symbol"])

    # Block trades
    op.create_table(
        "block_trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("size", sa.Integer),
        sa.Column("price", sa.Float),
        sa.Column("side", sa.String(4)),
        sa.Column("dollar_value", sa.Float),
        sa.Column("block_size", sa.String(16)),
        sa.Column("timestamp", sa.DateTime),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_block_trades_symbol", "block_trades", ["symbol"])
    op.create_index("ix_block_trades_size", "block_trades", ["block_size"])

    # Flow pressure
    op.create_table(
        "flow_pressure",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("buy_volume", sa.Float),
        sa.Column("sell_volume", sa.Float),
        sa.Column("net_flow", sa.Float),
        sa.Column("pressure_ratio", sa.Float),
        sa.Column("direction", sa.String(16)),
        sa.Column("cumulative_delta", sa.Float),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_flow_pressure_symbol_date", "flow_pressure", ["symbol", "date"])

    # Smart money signals
    op.create_table(
        "smart_money_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("signal", sa.String(16)),
        sa.Column("confidence", sa.Float),
        sa.Column("block_ratio", sa.Float),
        sa.Column("institutional_net_flow", sa.Float),
        sa.Column("institutional_buy_pct", sa.Float),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_smart_money_signals_symbol", "smart_money_signals", ["symbol"])


def downgrade() -> None:
    op.drop_table("smart_money_signals")
    op.drop_table("flow_pressure")
    op.drop_table("block_trades")
    op.drop_table("orderbook_snapshots")
