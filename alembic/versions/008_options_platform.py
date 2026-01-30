"""Options trading platform tables.

Revision ID: 008
Revises: 007
Create Date: 2026-01-29

Adds:
- options_chains: Options chain snapshots
- options_trades: Options trade history
- iv_surfaces: Historical IV surface data
- options_activity: Unusual activity signals
- options_backtests: Backtest results
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Options chain snapshots
    op.create_table(
        'options_chains',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('option_type', sa.String(4), nullable=False),
        sa.Column('strike', sa.Float(), nullable=False),
        sa.Column('expiry', sa.Date(), nullable=False),
        sa.Column('dte', sa.Integer()),
        sa.Column('bid', sa.Float()),
        sa.Column('ask', sa.Float()),
        sa.Column('mid_price', sa.Float()),
        sa.Column('volume', sa.Integer()),
        sa.Column('open_interest', sa.Integer()),
        sa.Column('iv', sa.Float()),
        sa.Column('delta', sa.Float()),
        sa.Column('gamma', sa.Float()),
        sa.Column('theta', sa.Float()),
        sa.Column('vega', sa.Float()),
        sa.Column('rho', sa.Float()),
        sa.Column('snapshot_date', sa.DateTime(), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Options trade history
    op.create_table(
        'options_trades',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('strategy_type', sa.String(50)),
        sa.Column('legs_json', sa.Text()),
        sa.Column('entry_date', sa.DateTime(), nullable=False),
        sa.Column('exit_date', sa.DateTime()),
        sa.Column('entry_premium', sa.Float()),
        sa.Column('exit_premium', sa.Float()),
        sa.Column('pnl', sa.Float()),
        sa.Column('pnl_pct', sa.Float()),
        sa.Column('exit_reason', sa.String(50)),
        sa.Column('status', sa.String(20), default='open'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Historical IV surface data
    op.create_table(
        'iv_surfaces',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False, index=True),
        sa.Column('atm_iv', sa.Float()),
        sa.Column('iv_skew_25d', sa.Float()),
        sa.Column('iv_rank', sa.Float()),
        sa.Column('iv_percentile', sa.Float()),
        sa.Column('hv_30d', sa.Float()),
        sa.Column('hv_60d', sa.Float()),
        sa.Column('surface_json', sa.Text()),
        sa.Column('svi_params_json', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Unusual activity signals
    op.create_table(
        'options_activity',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('signal_type', sa.String(30), nullable=False),
        sa.Column('option_type', sa.String(4)),
        sa.Column('strike', sa.Float()),
        sa.Column('expiry', sa.Date()),
        sa.Column('volume', sa.Integer()),
        sa.Column('open_interest', sa.Integer()),
        sa.Column('premium_total', sa.Float()),
        sa.Column('iv', sa.Float()),
        sa.Column('severity', sa.String(10)),
        sa.Column('description', sa.Text()),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Backtest results
    op.create_table(
        'options_backtests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('strategy_type', sa.String(50), nullable=False),
        sa.Column('underlying', sa.String(10), nullable=False),
        sa.Column('start_date', sa.Date()),
        sa.Column('end_date', sa.Date()),
        sa.Column('total_trades', sa.Integer()),
        sa.Column('win_rate', sa.Float()),
        sa.Column('total_pnl', sa.Float()),
        sa.Column('avg_trade_pnl', sa.Float()),
        sa.Column('max_drawdown', sa.Float()),
        sa.Column('sharpe_ratio', sa.Float()),
        sa.Column('profit_factor', sa.Float()),
        sa.Column('params_json', sa.Text()),
        sa.Column('trades_json', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('options_backtests')
    op.drop_table('options_activity')
    op.drop_table('iv_surfaces')
    op.drop_table('options_trades')
    op.drop_table('options_chains')
