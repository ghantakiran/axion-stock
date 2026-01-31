"""Options analytics platform tables.

Revision ID: 019
Revises: 018
Create Date: 2026-01-30

Adds:
- options_strategies: Saved strategy analyses with legs and metrics
- vol_surfaces: Stored volatility surface snapshots
- options_activity: Unusual activity signal records
- options_backtest_results: Options backtest run results and trades
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Options strategies
    op.create_table(
        "options_strategies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("strategy_id", sa.String(32), unique=True, nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("strategy_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128)),
        sa.Column("legs_json", sa.JSON),
        sa.Column("max_profit", sa.Float),
        sa.Column("max_loss", sa.Float),
        sa.Column("breakevens_json", sa.JSON),
        sa.Column("pop", sa.Float),
        sa.Column("expected_value", sa.Float),
        sa.Column("risk_reward_ratio", sa.Float),
        sa.Column("net_debit_credit", sa.Float),
        sa.Column("capital_required", sa.Float),
        sa.Column("greeks_json", sa.JSON),
        sa.Column("days_to_expiry", sa.Integer),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_options_strategies_symbol", "options_strategies", ["symbol"])
    op.create_index("ix_options_strategies_type", "options_strategies", ["strategy_type"])

    # Volatility surfaces
    op.create_table(
        "vol_surfaces",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("surface_id", sa.String(32), unique=True, nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("atm_iv", sa.Float),
        sa.Column("iv_skew_25d", sa.Float),
        sa.Column("iv_percentile", sa.Float),
        sa.Column("iv_rank", sa.Float),
        sa.Column("hv_iv_spread", sa.Float),
        sa.Column("realized_vol_30", sa.Float),
        sa.Column("realized_vol_60", sa.Float),
        sa.Column("svi_params_json", sa.JSON),
        sa.Column("term_structure_json", sa.JSON),
        sa.Column("raw_points_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_vol_surfaces_symbol_date",
        "vol_surfaces", ["symbol", "snapshot_date"],
    )

    # Options unusual activity
    op.create_table(
        "options_activity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("signal_id", sa.String(32), unique=True, nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("signal_type", sa.String(32), nullable=False),
        sa.Column("option_type", sa.String(8)),
        sa.Column("strike", sa.Float),
        sa.Column("expiry", sa.Date),
        sa.Column("volume", sa.Integer),
        sa.Column("open_interest", sa.Integer),
        sa.Column("premium_total", sa.Float),
        sa.Column("iv", sa.Float),
        sa.Column("severity", sa.String(16)),
        sa.Column("description", sa.Text),
        sa.Column("detected_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_options_activity_symbol", "options_activity", ["symbol"])
    op.create_index("ix_options_activity_type", "options_activity", ["signal_type"])

    # Options backtest results
    op.create_table(
        "options_backtest_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("result_id", sa.String(32), unique=True, nullable=False),
        sa.Column("strategy_type", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(16)),
        sa.Column("total_trades", sa.Integer),
        sa.Column("winning_trades", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("total_pnl", sa.Float),
        sa.Column("avg_winner", sa.Float),
        sa.Column("avg_loser", sa.Float),
        sa.Column("profit_factor", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("max_drawdown", sa.Float),
        sa.Column("avg_hold_days", sa.Float),
        sa.Column("trades_json", sa.JSON),
        sa.Column("entry_rules_json", sa.JSON),
        sa.Column("exit_rules_json", sa.JSON),
        sa.Column("executed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_options_bt_strategy", "options_backtest_results", ["strategy_type"])


def downgrade() -> None:
    op.drop_table("options_backtest_results")
    op.drop_table("options_activity")
    op.drop_table("vol_surfaces")
    op.drop_table("options_strategies")
