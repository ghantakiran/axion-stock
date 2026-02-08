"""PRD-64: Liquidity Risk Analytics

Revision ID: 064
Revises: 063
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '064'
down_revision: Union[str, None] = '063'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Liquidity scores table
    op.create_table(
        'liquidity_scores',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('composite_score', sa.Float(), nullable=False),
        sa.Column('volume_score', sa.Float(), default=0),
        sa.Column('spread_score', sa.Float(), default=0),
        sa.Column('depth_score', sa.Float(), default=0),
        sa.Column('volatility_score', sa.Float(), default=0),
        sa.Column('turnover_ratio', sa.Float(), nullable=True),
        sa.Column('avg_daily_volume', sa.BigInteger(), nullable=True),
        sa.Column('avg_spread_bps', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.BigInteger(), nullable=True),
        sa.Column('liquidity_tier', sa.String(20), nullable=False),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_liq_scores_symbol_ts', 'liquidity_scores', ['symbol', 'timestamp'])

    # Spread snapshots table
    op.create_table(
        'spread_snapshots',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('bid_price', sa.Float(), nullable=False),
        sa.Column('ask_price', sa.Float(), nullable=False),
        sa.Column('mid_price', sa.Float(), nullable=False),
        sa.Column('spread', sa.Float(), nullable=False),
        sa.Column('spread_bps', sa.Float(), nullable=False),
        sa.Column('bid_size', sa.Integer(), nullable=True),
        sa.Column('ask_size', sa.Integer(), nullable=True),
        sa.Column('effective_spread', sa.Float(), nullable=True),
        sa.Column('realized_spread', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_spread_snap_symbol_ts', 'spread_snapshots', ['symbol', 'timestamp'])

    # Market impact estimates table
    op.create_table(
        'market_impact_estimates',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('order_size_shares', sa.Integer(), nullable=False),
        sa.Column('order_size_value', sa.Float(), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('participation_rate', sa.Float(), nullable=True),
        sa.Column('estimated_impact_bps', sa.Float(), nullable=False),
        sa.Column('temporary_impact_bps', sa.Float(), nullable=True),
        sa.Column('permanent_impact_bps', sa.Float(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('model_used', sa.String(30), nullable=False),
        sa.Column('model_params', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # Slippage records table
    op.create_table(
        'slippage_records',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('order_size', sa.Integer(), nullable=False),
        sa.Column('expected_price', sa.Float(), nullable=False),
        sa.Column('executed_price', sa.Float(), nullable=False),
        sa.Column('slippage_bps', sa.Float(), nullable=False),
        sa.Column('slippage_cost', sa.Float(), nullable=False),
        sa.Column('market_volume', sa.BigInteger(), nullable=True),
        sa.Column('participation_rate', sa.Float(), nullable=True),
        sa.Column('spread_at_entry', sa.Float(), nullable=True),
        sa.Column('volatility_at_entry', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_slippage_symbol_ts', 'slippage_records', ['symbol', 'timestamp'])


def downgrade() -> None:
    op.drop_table('slippage_records')
    op.drop_table('market_impact_estimates')
    op.drop_table('spread_snapshots')
    op.drop_table('liquidity_scores')
