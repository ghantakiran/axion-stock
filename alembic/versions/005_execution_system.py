"""Execution system tables for order and trade journaling.

Revision ID: 005
Revises: 004
Create Date: 2026-01-27

Adds:
- trade_orders: Order history
- trade_executions: Executed trade records
- portfolio_snapshots: Daily portfolio snapshots
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create trade_orders table
    op.create_table(
        'trade_orders',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('order_id', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('client_order_id', sa.String(100)),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('limit_price', sa.Float),
        sa.Column('stop_price', sa.Float),
        sa.Column('filled_quantity', sa.Float, default=0),
        sa.Column('filled_avg_price', sa.Float),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('commission', sa.Float, default=0),
        sa.Column('slippage', sa.Float, default=0),
        sa.Column('trigger', sa.String(50)),
        sa.Column('broker', sa.String(50)),
        sa.Column('regime_at_order', sa.String(20)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime),
        sa.Column('filled_at', sa.DateTime),
        sa.Column('cancelled_at', sa.DateTime),
        sa.Column('notes', sa.Text),
    )
    op.create_index('ix_orders_symbol_date', 'trade_orders', ['symbol', 'created_at'])
    op.create_index('ix_orders_status', 'trade_orders', ['status'])
    
    # Create trade_executions table
    op.create_table(
        'trade_executions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('execution_id', sa.String(100), unique=True, nullable=False),
        sa.Column('order_id', sa.String(100), nullable=False, index=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('price', sa.Float, nullable=False),
        sa.Column('commission', sa.Float, default=0),
        sa.Column('slippage', sa.Float, default=0),
        sa.Column('factor_scores', sa.Text),
        sa.Column('regime_at_trade', sa.String(20)),
        sa.Column('portfolio_value_at_trade', sa.Float),
        sa.Column('executed_at', sa.DateTime, nullable=False, index=True),
        sa.Column('notes', sa.Text),
    )
    op.create_index('ix_executions_symbol_date', 'trade_executions', ['symbol', 'executed_at'])
    
    # Create portfolio_snapshots table
    op.create_table(
        'portfolio_snapshots',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('snapshot_date', sa.Date, nullable=False, unique=True, index=True),
        sa.Column('cash', sa.Float, nullable=False),
        sa.Column('portfolio_value', sa.Float, nullable=False),
        sa.Column('equity', sa.Float, nullable=False),
        sa.Column('daily_pnl', sa.Float),
        sa.Column('daily_return_pct', sa.Float),
        sa.Column('cumulative_return_pct', sa.Float),
        sa.Column('portfolio_beta', sa.Float),
        sa.Column('portfolio_volatility', sa.Float),
        sa.Column('sharpe_ratio', sa.Float),
        sa.Column('max_drawdown', sa.Float),
        sa.Column('positions', sa.Text),
        sa.Column('regime', sa.String(20)),
        sa.Column('num_positions', sa.Integer),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('portfolio_snapshots')
    op.drop_table('trade_executions')
    op.drop_table('trade_orders')
