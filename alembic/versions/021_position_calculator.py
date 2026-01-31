"""Position calculator system tables.

Revision ID: 021
Revises: 020
Create Date: 2026-01-31

Adds:
- sizing_calculations: Stored position sizing results
- position_risks: Open position risk records
- heat_snapshots: Portfolio heat snapshots
- drawdown_snapshots: Drawdown state snapshots
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sizing calculations
    op.create_table(
        "sizing_calculations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("record_id", sa.String(32), unique=True, nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("sizing_method", sa.String(32)),
        sa.Column("instrument_type", sa.String(16)),
        sa.Column("account_value", sa.Float),
        sa.Column("entry_price", sa.Float),
        sa.Column("stop_price", sa.Float),
        sa.Column("target_price", sa.Float),
        sa.Column("position_size", sa.Integer),
        sa.Column("position_value", sa.Float),
        sa.Column("risk_amount", sa.Float),
        sa.Column("risk_pct", sa.Float),
        sa.Column("risk_reward_ratio", sa.Float),
        sa.Column("warnings_json", sa.JSON),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sizing_calculations_symbol", "sizing_calculations", ["symbol"])

    # Position risks
    op.create_table(
        "position_risks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("qty", sa.Integer),
        sa.Column("entry_price", sa.Float),
        sa.Column("stop_price", sa.Float),
        sa.Column("current_price", sa.Float),
        sa.Column("instrument_type", sa.String(16)),
        sa.Column("contract_multiplier", sa.Integer),
        sa.Column("risk_dollars", sa.Float),
        sa.Column("market_value", sa.Float),
        sa.Column("unrealized_pnl", sa.Float),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_position_risks_symbol", "position_risks", ["symbol"])

    # Heat snapshots
    op.create_table(
        "heat_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("account_value", sa.Float),
        sa.Column("total_heat_pct", sa.Float),
        sa.Column("total_heat_dollars", sa.Float),
        sa.Column("n_positions", sa.Integer),
        sa.Column("exceeds_limit", sa.Boolean),
        sa.Column("position_heats_json", sa.JSON),
        sa.Column("heat_limit_pct", sa.Float),
    )
    op.create_index("ix_heat_snapshots_timestamp", "heat_snapshots", ["timestamp"])

    # Drawdown snapshots
    op.create_table(
        "drawdown_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("peak_value", sa.Float),
        sa.Column("current_value", sa.Float),
        sa.Column("drawdown_pct", sa.Float),
        sa.Column("drawdown_dollars", sa.Float),
        sa.Column("at_limit", sa.Boolean),
        sa.Column("at_warning", sa.Boolean),
        sa.Column("blocked", sa.Boolean),
        sa.Column("size_multiplier", sa.Float),
        sa.Column("limit_pct", sa.Float),
    )
    op.create_index("ix_drawdown_snapshots_timestamp", "drawdown_snapshots", ["timestamp"])


def downgrade() -> None:
    op.drop_table("drawdown_snapshots")
    op.drop_table("heat_snapshots")
    op.drop_table("position_risks")
    op.drop_table("sizing_calculations")
