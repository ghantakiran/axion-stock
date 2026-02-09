"""PRD-161: Social Signal Backtester.

Revision ID: 161
Revises: 160
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "161"
down_revision = "160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Archived social signals for backtesting replay
    op.create_table(
        "social_signal_archive",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("composite_score", sa.Float),
        sa.Column("direction", sa.String(10), index=True),
        sa.Column("action", sa.String(20)),
        sa.Column("sentiment_avg", sa.Float),
        sa.Column("platform_count", sa.Integer),
        sa.Column("platform_consensus", sa.Float),
        sa.Column("influencer_signal", sa.Boolean, default=False),
        sa.Column("volume_anomaly", sa.Boolean, default=False),
        sa.Column("mention_count", sa.Integer),
        sa.Column("confidence", sa.Float),
        sa.Column("signal_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Signal outcome validation records
    op.create_table(
        "social_signal_outcomes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("outcome_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("signal_id", sa.String(50), nullable=False, index=True),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("signal_direction", sa.String(10)),
        sa.Column("signal_score", sa.Float),
        sa.Column("price_at_signal", sa.Float),
        sa.Column("return_1d", sa.Float),
        sa.Column("return_5d", sa.Float),
        sa.Column("return_10d", sa.Float),
        sa.Column("return_30d", sa.Float),
        sa.Column("direction_correct_1d", sa.Boolean),
        sa.Column("direction_correct_5d", sa.Boolean),
        sa.Column("direction_correct_30d", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Correlation analysis cache
    op.create_table(
        "social_correlation_cache",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cache_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("lag_days", sa.Integer),
        sa.Column("correlation", sa.Float),
        sa.Column("p_value", sa.Float),
        sa.Column("sample_size", sa.Integer),
        sa.Column("is_significant", sa.Boolean),
        sa.Column("lookback_days", sa.Integer),
        sa.Column("computed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("social_correlation_cache")
    op.drop_table("social_signal_outcomes")
    op.drop_table("social_signal_archive")
