"""Factor Engine v2 schema updates.

Revision ID: 004
Revises: 003_continuous_aggregates
Create Date: 2026-01-27

Adds:
- GICS sector classification columns to instruments
- New factor score columns (volatility, technical)
- Market regimes table for tracking regime history
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add GICS columns to instruments table
    op.add_column('instruments', sa.Column('gics_sector', sa.String(100), nullable=True))
    op.add_column('instruments', sa.Column('gics_industry_group', sa.String(100), nullable=True))
    op.add_column('instruments', sa.Column('gics_industry', sa.String(100), nullable=True))
    op.add_column('instruments', sa.Column('gics_sub_industry', sa.String(100), nullable=True))
    op.add_column('instruments', sa.Column('gics_sector_code', sa.String(10), nullable=True))
    
    # Create index for GICS sector
    op.create_index('ix_instruments_gics_sector', 'instruments', ['gics_sector'])
    
    # Add new factor score columns
    op.add_column('factor_scores', sa.Column('volatility_score', sa.Float, nullable=True))
    op.add_column('factor_scores', sa.Column('technical_score', sa.Float, nullable=True))
    op.add_column('factor_scores', sa.Column('sector_relative_score', sa.Float, nullable=True))
    op.add_column('factor_scores', sa.Column('regime', sa.String(20), nullable=True))
    op.add_column('factor_scores', sa.Column('engine_version', sa.String(10), server_default='v2'))
    
    # Create index for sector-relative score
    op.create_index('ix_scores_sector_relative', 'factor_scores', ['sector_relative_score'])
    
    # Create market_regimes table
    op.create_table(
        'market_regimes',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date, nullable=False, unique=True, index=True),
        sa.Column('regime', sa.String(20), nullable=False),
        sa.Column('confidence', sa.Float),
        sa.Column('sp500_trend_strength', sa.Float),
        sa.Column('vix_level', sa.Float),
        sa.Column('breadth_ratio', sa.Float),
        sa.Column('momentum_1m', sa.Float),
        sa.Column('value_weight', sa.Float),
        sa.Column('momentum_weight', sa.Float),
        sa.Column('quality_weight', sa.Float),
        sa.Column('growth_weight', sa.Float),
        sa.Column('volatility_weight', sa.Float),
        sa.Column('technical_weight', sa.Float),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop market_regimes table
    op.drop_table('market_regimes')
    
    # Remove new factor score columns
    op.drop_index('ix_scores_sector_relative', 'factor_scores')
    op.drop_column('factor_scores', 'engine_version')
    op.drop_column('factor_scores', 'regime')
    op.drop_column('factor_scores', 'sector_relative_score')
    op.drop_column('factor_scores', 'technical_score')
    op.drop_column('factor_scores', 'volatility_score')
    
    # Remove GICS columns from instruments
    op.drop_index('ix_instruments_gics_sector', 'instruments')
    op.drop_column('instruments', 'gics_sector_code')
    op.drop_column('instruments', 'gics_sub_industry')
    op.drop_column('instruments', 'gics_industry')
    op.drop_column('instruments', 'gics_industry_group')
    op.drop_column('instruments', 'gics_sector')
