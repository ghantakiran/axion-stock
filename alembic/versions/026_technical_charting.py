"""Technical charting system tables.

Revision ID: 026
Revises: 025
Create Date: 2026-02-01

Adds:
- chart_patterns: Detected pattern history
- trend_analyses: Trend assessments
- sr_levels: Support/resistance levels
- fibonacci_analyses: Fibonacci computations
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Chart patterns
    op.create_table(
        "chart_patterns",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("pattern_type", sa.String(32)),
        sa.Column("start_idx", sa.Integer),
        sa.Column("end_idx", sa.Integer),
        sa.Column("neckline", sa.Float),
        sa.Column("target_price", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("confirmed", sa.Boolean),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_chart_patterns_symbol", "chart_patterns", ["symbol"])
    op.create_index("ix_chart_patterns_type", "chart_patterns", ["pattern_type"])

    # Trend analyses
    op.create_table(
        "trend_analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(16)),
        sa.Column("strength", sa.Float),
        sa.Column("slope", sa.Float),
        sa.Column("r_squared", sa.Float),
        sa.Column("ma_short", sa.Float),
        sa.Column("ma_medium", sa.Float),
        sa.Column("ma_long", sa.Float),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_trend_analyses_symbol_date", "trend_analyses", ["symbol", "date"])

    # Support/resistance levels
    op.create_table(
        "sr_levels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("level_type", sa.String(16)),
        sa.Column("price", sa.Float),
        sa.Column("touches", sa.Integer),
        sa.Column("strength", sa.Float),
        sa.Column("last_tested_idx", sa.Integer),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sr_levels_symbol", "sr_levels", ["symbol"])

    # Fibonacci analyses
    op.create_table(
        "fibonacci_analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("swing_high", sa.Float),
        sa.Column("swing_low", sa.Float),
        sa.Column("is_uptrend", sa.Boolean),
        sa.Column("retracements_json", sa.JSON),
        sa.Column("extensions_json", sa.JSON),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_fibonacci_analyses_symbol", "fibonacci_analyses", ["symbol"])


def downgrade() -> None:
    op.drop_table("fibonacci_analyses")
    op.drop_table("sr_levels")
    op.drop_table("trend_analyses")
    op.drop_table("chart_patterns")
