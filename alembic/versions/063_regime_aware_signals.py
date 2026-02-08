"""PRD-63: Regime-Aware Signals

Revision ID: 063
Revises: 062
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '063'
down_revision: Union[str, None] = '062'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Regime states table
    op.create_table(
        'regime_states',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('regime_type', sa.String(30), nullable=False, index=True),
        sa.Column('detection_method', sa.String(30), nullable=False),
        sa.Column('confidence', sa.Float(), default=0),
        sa.Column('volatility_level', sa.String(20), nullable=True),
        sa.Column('trend_direction', sa.String(20), nullable=True),
        sa.Column('trend_strength', sa.Float(), nullable=True),
        sa.Column('regime_duration_days', sa.Integer(), default=0),
        sa.Column('transition_probability', sa.Float(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_regime_states_symbol_ts', 'regime_states', ['symbol', 'timestamp'])

    # Regime signals table
    op.create_table(
        'regime_signals',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('signal_type', sa.String(30), nullable=False, index=True),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('strength', sa.Float(), default=0),
        sa.Column('confidence', sa.Float(), default=0),
        sa.Column('regime_type', sa.String(30), nullable=False),
        sa.Column('regime_confidence', sa.Float(), default=0),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('risk_reward_ratio', sa.Float(), nullable=True),
        sa.Column('indicators_used', sa.Text(), nullable=True),
        sa.Column('parameters', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_regime_signals_symbol_ts', 'regime_signals', ['symbol', 'timestamp'])
    op.create_index('ix_regime_signals_active', 'regime_signals', ['is_active', 'symbol'])

    # Signal performance table
    op.create_table(
        'signal_performance',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('signal_id', sa.String(36), sa.ForeignKey('regime_signals.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('signal_type', sa.String(30), nullable=False),
        sa.Column('regime_type', sa.String(30), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('return_pct', sa.Float(), nullable=True),
        sa.Column('max_favorable', sa.Float(), nullable=True),
        sa.Column('max_adverse', sa.Float(), nullable=True),
        sa.Column('duration_hours', sa.Float(), nullable=True),
        sa.Column('hit_stop_loss', sa.Boolean(), default=False),
        sa.Column('hit_take_profit', sa.Boolean(), default=False),
        sa.Column('outcome', sa.String(20), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_signal_perf_regime', 'signal_performance', ['regime_type', 'signal_type'])

    # Regime parameters table
    op.create_table(
        'regime_parameters',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('regime_type', sa.String(30), nullable=False, index=True),
        sa.Column('signal_type', sa.String(30), nullable=False),
        sa.Column('indicator_name', sa.String(30), nullable=False),
        sa.Column('parameter_name', sa.String(50), nullable=False),
        sa.Column('default_value', sa.Float(), nullable=False),
        sa.Column('optimized_value', sa.Float(), nullable=True),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('optimization_score', sa.Float(), nullable=True),
        sa.Column('sample_size', sa.Integer(), default=0),
        sa.Column('last_optimized_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('regime_type', 'signal_type', 'indicator_name', 'parameter_name',
                          name='uq_regime_param_key'),
    )


def downgrade() -> None:
    op.drop_table('regime_parameters')
    op.drop_table('signal_performance')
    op.drop_table('regime_signals')
    op.drop_table('regime_states')
