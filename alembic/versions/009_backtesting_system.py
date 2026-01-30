"""Backtesting system database schema.

Revision ID: 009_backtesting_system
Revises: 008_options_platform
Create Date: 2026-01-28

Tables:
- backtest_runs: Individual backtest executions
- backtest_trades: Trades from backtests
- backtest_snapshots: Point-in-time portfolio snapshots
- walk_forward_results: Walk-forward optimization results
- monte_carlo_results: Monte Carlo analysis results
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = '009_backtesting_system'
down_revision = '008_options_platform'
branch_labels = None
depends_on = None


def upgrade():
    # ==========================================================================
    # backtest_runs - Individual backtest executions
    # ==========================================================================
    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.String(64), unique=True, nullable=False),
        sa.Column('strategy_name', sa.String(128), nullable=False),
        sa.Column('strategy_params', JSONB, default={}),
        
        # Time range
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('bar_type', sa.String(10), default='1d'),
        
        # Configuration
        sa.Column('initial_capital', sa.Float(), default=100000),
        sa.Column('rebalance_frequency', sa.String(20), default='monthly'),
        sa.Column('universe', sa.String(64), default='sp500'),
        sa.Column('config', JSONB, default={}),
        
        # Results - Returns
        sa.Column('total_return', sa.Float()),
        sa.Column('cagr', sa.Float()),
        sa.Column('benchmark_return', sa.Float()),
        sa.Column('alpha', sa.Float()),
        
        # Results - Risk
        sa.Column('volatility', sa.Float()),
        sa.Column('max_drawdown', sa.Float()),
        sa.Column('sharpe_ratio', sa.Float()),
        sa.Column('sortino_ratio', sa.Float()),
        sa.Column('calmar_ratio', sa.Float()),
        
        # Results - Trading
        sa.Column('total_trades', sa.Integer()),
        sa.Column('win_rate', sa.Float()),
        sa.Column('profit_factor', sa.Float()),
        sa.Column('avg_hold_days', sa.Float()),
        
        # Results - Costs
        sa.Column('total_commission', sa.Float()),
        sa.Column('total_slippage', sa.Float()),
        sa.Column('turnover', sa.Float()),
        
        # Full results JSON
        sa.Column('full_metrics', JSONB),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('notes', sa.Text()),
        sa.Column('tags', ARRAY(sa.String(32))),
    )
    
    op.create_index(
        'ix_backtest_runs_strategy', 'backtest_runs', ['strategy_name']
    )
    op.create_index(
        'ix_backtest_runs_created', 'backtest_runs', ['created_at']
    )
    op.create_index(
        'ix_backtest_runs_sharpe', 'backtest_runs', ['sharpe_ratio']
    )
    
    # ==========================================================================
    # backtest_trades - Trades from backtests
    # ==========================================================================
    op.create_table(
        'backtest_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.String(64), sa.ForeignKey('backtest_runs.run_id', ondelete='CASCADE'), nullable=False),
        
        # Trade details
        sa.Column('symbol', sa.String(16), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('entry_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('exit_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False),
        
        # P&L
        sa.Column('pnl', sa.Float()),
        sa.Column('pnl_pct', sa.Float()),
        sa.Column('hold_days', sa.Integer()),
        
        # Context
        sa.Column('entry_reason', sa.String(256)),
        sa.Column('exit_reason', sa.String(256)),
        sa.Column('sector', sa.String(64)),
        sa.Column('factor_signal', sa.String(64)),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index(
        'ix_backtest_trades_run', 'backtest_trades', ['run_id']
    )
    op.create_index(
        'ix_backtest_trades_symbol', 'backtest_trades', ['symbol']
    )
    
    # ==========================================================================
    # backtest_snapshots - Point-in-time portfolio snapshots
    # ==========================================================================
    op.create_table(
        'backtest_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.String(64), sa.ForeignKey('backtest_runs.run_id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('equity', sa.Float(), nullable=False),
        sa.Column('cash', sa.Float()),
        sa.Column('positions_value', sa.Float()),
        sa.Column('n_positions', sa.Integer()),
        sa.Column('drawdown', sa.Float()),
        
        # Detailed positions (JSON)
        sa.Column('positions', JSONB),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index(
        'ix_backtest_snapshots_run_time', 'backtest_snapshots', ['run_id', 'timestamp']
    )
    
    # ==========================================================================
    # walk_forward_results - Walk-forward optimization results
    # ==========================================================================
    op.create_table(
        'walk_forward_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('result_id', sa.String(64), unique=True, nullable=False),
        sa.Column('strategy_name', sa.String(128), nullable=False),
        
        # Configuration
        sa.Column('n_windows', sa.Integer(), default=5),
        sa.Column('in_sample_pct', sa.Float(), default=0.70),
        sa.Column('param_grid', JSONB),
        
        # Results
        sa.Column('in_sample_sharpe_avg', sa.Float()),
        sa.Column('out_of_sample_sharpe', sa.Float()),
        sa.Column('efficiency_ratio', sa.Float()),
        sa.Column('combined_cagr', sa.Float()),
        sa.Column('combined_max_dd', sa.Float()),
        
        # Parameter stability
        sa.Column('param_stability', JSONB),
        
        # Window details
        sa.Column('windows', JSONB),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index(
        'ix_walk_forward_strategy', 'walk_forward_results', ['strategy_name']
    )
    op.create_index(
        'ix_walk_forward_efficiency', 'walk_forward_results', ['efficiency_ratio']
    )
    
    # ==========================================================================
    # monte_carlo_results - Monte Carlo analysis results
    # ==========================================================================
    op.create_table(
        'monte_carlo_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.String(64), sa.ForeignKey('backtest_runs.run_id', ondelete='CASCADE')),
        
        sa.Column('n_simulations', sa.Integer(), nullable=False),
        
        # Sharpe distribution
        sa.Column('sharpe_mean', sa.Float()),
        sa.Column('sharpe_std', sa.Float()),
        sa.Column('sharpe_ci_low', sa.Float()),
        sa.Column('sharpe_ci_high', sa.Float()),
        
        # CAGR distribution
        sa.Column('cagr_mean', sa.Float()),
        sa.Column('cagr_std', sa.Float()),
        sa.Column('cagr_ci_low', sa.Float()),
        sa.Column('cagr_ci_high', sa.Float()),
        
        # Drawdown distribution
        sa.Column('max_dd_mean', sa.Float()),
        sa.Column('max_dd_std', sa.Float()),
        sa.Column('max_dd_ci_low', sa.Float()),
        sa.Column('max_dd_ci_high', sa.Float()),
        
        # Probabilities
        sa.Column('pct_profitable', sa.Float()),
        sa.Column('pct_beats_benchmark', sa.Float()),
        
        # Significance
        sa.Column('is_significant', sa.Boolean(), default=False),
        sa.Column('p_value', sa.Float()),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index(
        'ix_monte_carlo_run', 'monte_carlo_results', ['run_id']
    )


def downgrade():
    op.drop_table('monte_carlo_results')
    op.drop_table('walk_forward_results')
    op.drop_table('backtest_snapshots')
    op.drop_table('backtest_trades')
    op.drop_table('backtest_runs')
