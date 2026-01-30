"""Risk management system tables.

Revision ID: 006
Revises: 005
Create Date: 2026-01-28

Adds:
- risk_alerts: Risk alert history
- risk_snapshots: Daily risk metrics snapshots
- stress_test_results: Stress test result history
- drawdown_events: Drawdown event history
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create risk_alerts table
    op.create_table(
        'risk_alerts',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('alert_id', sa.String(100), unique=True, nullable=False),
        sa.Column('level', sa.String(20), nullable=False),  # info, warning, critical, emergency
        sa.Column('category', sa.String(50), nullable=False),  # drawdown, concentration, var, etc.
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('metric_name', sa.String(50)),
        sa.Column('metric_value', sa.Float),
        sa.Column('threshold', sa.Float),
        sa.Column('position', sa.String(20)),  # Symbol if position-specific
        sa.Column('action_required', sa.Boolean, default=False),
        sa.Column('action_type', sa.String(50)),  # reduce, close, halt
        sa.Column('action_taken', sa.Boolean, default=False),
        sa.Column('acknowledged', sa.Boolean, default=False),
        sa.Column('acknowledged_at', sa.DateTime),
        sa.Column('acknowledged_by', sa.String(100)),
        sa.Column('resolved', sa.Boolean, default=False),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), index=True),
    )
    op.create_index('ix_alerts_level', 'risk_alerts', ['level'])
    op.create_index('ix_alerts_category', 'risk_alerts', ['category'])
    op.create_index('ix_alerts_resolved', 'risk_alerts', ['resolved'])

    # Create risk_snapshots table
    op.create_table(
        'risk_snapshots',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('snapshot_date', sa.Date, nullable=False, index=True),
        sa.Column('portfolio_value', sa.Float, nullable=False),

        # Portfolio metrics
        sa.Column('sharpe_ratio', sa.Float),
        sa.Column('sortino_ratio', sa.Float),
        sa.Column('calmar_ratio', sa.Float),
        sa.Column('information_ratio', sa.Float),
        sa.Column('portfolio_beta', sa.Float),
        sa.Column('portfolio_volatility', sa.Float),
        sa.Column('tracking_error', sa.Float),

        # Drawdown
        sa.Column('current_drawdown', sa.Float),
        sa.Column('max_drawdown', sa.Float),
        sa.Column('drawdown_duration_days', sa.Integer),

        # VaR metrics
        sa.Column('var_95', sa.Float),
        sa.Column('var_99', sa.Float),
        sa.Column('cvar_95', sa.Float),
        sa.Column('var_95_pct', sa.Float),
        sa.Column('var_99_pct', sa.Float),

        # Concentration
        sa.Column('largest_position_weight', sa.Float),
        sa.Column('largest_position_symbol', sa.String(20)),
        sa.Column('top5_weight', sa.Float),
        sa.Column('largest_sector_weight', sa.Float),
        sa.Column('largest_sector_name', sa.String(50)),
        sa.Column('hhi', sa.Float),  # Herfindahl-Hirschman Index

        # Status
        sa.Column('overall_status', sa.String(20)),  # normal, warning, elevated, critical
        sa.Column('trading_allowed', sa.Boolean, default=True),
        sa.Column('recovery_state', sa.String(20)),
        sa.Column('active_alert_count', sa.Integer, default=0),

        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_risk_snapshots_date', 'risk_snapshots', ['snapshot_date'], unique=True)

    # Create stress_test_results table
    op.create_table(
        'stress_test_results',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('run_date', sa.Date, nullable=False, index=True),
        sa.Column('scenario_type', sa.String(20), nullable=False),  # historical, hypothetical
        sa.Column('scenario_name', sa.String(100), nullable=False),
        sa.Column('scenario_description', sa.Text),
        sa.Column('portfolio_value', sa.Float),
        sa.Column('portfolio_impact_dollars', sa.Float),
        sa.Column('portfolio_impact_pct', sa.Float),
        sa.Column('worst_position_symbol', sa.String(20)),
        sa.Column('worst_position_impact_pct', sa.Float),
        sa.Column('surviving_portfolio_value', sa.Float),
        sa.Column('position_impacts', sa.Text),  # JSON
        sa.Column('sector_impacts', sa.Text),  # JSON
        sa.Column('factor_contributions', sa.Text),  # JSON
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_stress_tests_date_scenario', 'stress_test_results', ['run_date', 'scenario_name'])

    # Create drawdown_events table
    op.create_table(
        'drawdown_events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.String(50), nullable=False),  # portfolio_drawdown, position_stop_loss, daily_loss
        sa.Column('trigger_level', sa.String(20)),  # warning, reduce, emergency
        sa.Column('drawdown_pct', sa.Float, nullable=False),
        sa.Column('threshold_pct', sa.Float),
        sa.Column('position', sa.String(20)),  # Symbol if position-specific
        sa.Column('action_taken', sa.String(100)),
        sa.Column('portfolio_value_before', sa.Float),
        sa.Column('portfolio_value_after', sa.Float),
        sa.Column('recovery_started', sa.Boolean, default=False),
        sa.Column('recovery_completed', sa.Boolean, default=False),
        sa.Column('recovery_completed_at', sa.DateTime),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), index=True),
    )
    op.create_index('ix_drawdown_events_type', 'drawdown_events', ['event_type'])

    # Create attribution_results table
    op.create_table(
        'attribution_results',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('period_start', sa.Date, nullable=False),
        sa.Column('period_end', sa.Date, nullable=False),
        sa.Column('attribution_type', sa.String(20), nullable=False),  # brinson, factor

        # Brinson attribution
        sa.Column('total_return', sa.Float),
        sa.Column('benchmark_return', sa.Float),
        sa.Column('active_return', sa.Float),
        sa.Column('allocation_effect', sa.Float),
        sa.Column('selection_effect', sa.Float),
        sa.Column('interaction_effect', sa.Float),

        # Factor attribution
        sa.Column('market_contribution', sa.Float),
        sa.Column('value_contribution', sa.Float),
        sa.Column('momentum_contribution', sa.Float),
        sa.Column('quality_contribution', sa.Float),
        sa.Column('growth_contribution', sa.Float),
        sa.Column('residual_alpha', sa.Float),

        # Factor exposures
        sa.Column('factor_exposures', sa.Text),  # JSON
        sa.Column('factor_returns', sa.Text),  # JSON

        # Sector attribution
        sa.Column('sector_attribution', sa.Text),  # JSON

        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_attribution_period', 'attribution_results', ['period_start', 'period_end'])


def downgrade() -> None:
    op.drop_table('attribution_results')
    op.drop_table('drawdown_events')
    op.drop_table('stress_test_results')
    op.drop_table('risk_snapshots')
    op.drop_table('risk_alerts')
