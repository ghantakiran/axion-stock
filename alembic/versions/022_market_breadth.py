"""Market breadth system tables.

Revision ID: 022
Revises: 021
Create Date: 2026-01-31

Adds:
- breadth_snapshots: Daily breadth indicator values
- breadth_signals: Detected breadth signals
- market_health: Composite health scores
- sector_breadth: Per-sector breadth data
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Breadth snapshots
    op.create_table(
        "breadth_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("snapshot_id", sa.String(32), unique=True, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("advancing", sa.Integer),
        sa.Column("declining", sa.Integer),
        sa.Column("unchanged", sa.Integer),
        sa.Column("up_volume", sa.Float),
        sa.Column("down_volume", sa.Float),
        sa.Column("new_highs", sa.Integer),
        sa.Column("new_lows", sa.Integer),
        sa.Column("cumulative_ad_line", sa.Float),
        sa.Column("mcclellan_oscillator", sa.Float),
        sa.Column("mcclellan_summation", sa.Float),
        sa.Column("breadth_thrust_ema", sa.Float),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_breadth_snapshots_date", "breadth_snapshots", ["date"])

    # Breadth signals
    op.create_table(
        "breadth_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("signal_type", sa.String(32), nullable=False),
        sa.Column("indicator", sa.String(32)),
        sa.Column("value", sa.Float),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_breadth_signals_date", "breadth_signals", ["date"])
    op.create_index("ix_breadth_signals_type", "breadth_signals", ["signal_type"])

    # Market health
    op.create_table(
        "market_health",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("health_id", sa.String(32), unique=True, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("level", sa.String(16)),
        sa.Column("ad_score", sa.Float),
        sa.Column("nhnl_score", sa.Float),
        sa.Column("mcclellan_score", sa.Float),
        sa.Column("thrust_score", sa.Float),
        sa.Column("volume_score", sa.Float),
        sa.Column("signals_json", sa.JSON),
        sa.Column("summary", sa.Text),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_market_health_date", "market_health", ["date"])

    # Sector breadth
    op.create_table(
        "sector_breadth",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("sector", sa.String(64), nullable=False),
        sa.Column("advancing", sa.Integer),
        sa.Column("declining", sa.Integer),
        sa.Column("unchanged", sa.Integer),
        sa.Column("pct_advancing", sa.Float),
        sa.Column("breadth_score", sa.Float),
        sa.Column("momentum", sa.String(16)),
    )
    op.create_index("ix_sector_breadth_date", "sector_breadth", ["date"])
    op.create_index("ix_sector_breadth_sector", "sector_breadth", ["sector"])


def downgrade() -> None:
    op.drop_table("sector_breadth")
    op.drop_table("market_health")
    op.drop_table("breadth_signals")
    op.drop_table("breadth_snapshots")
