"""Alternative data system tables.

Revision ID: 036
Revises: 035
Create Date: 2026-02-02

Adds:
- satellite_signals: Satellite observation records
- web_traffic_snapshots: Web traffic snapshots
- social_mentions: Social media mentions
- alt_data_composites: Composite alternative data scores
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Satellite signals
    op.create_table(
        "satellite_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("satellite_type", sa.String(30), nullable=False),
        sa.Column("raw_value", sa.Float),
        sa.Column("normalized_value", sa.Float),
        sa.Column("z_score", sa.Float),
        sa.Column("is_anomaly", sa.Boolean),
        sa.Column("trend", sa.Float),
        sa.Column("observed_at", sa.DateTime),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_satellite_signals_symbol", "satellite_signals", ["symbol"])

    # Web traffic snapshots
    op.create_table(
        "web_traffic_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("domain", sa.String(255)),
        sa.Column("visits", sa.Integer),
        sa.Column("unique_visitors", sa.Integer),
        sa.Column("bounce_rate", sa.Float),
        sa.Column("avg_duration", sa.Float),
        sa.Column("growth_rate", sa.Float),
        sa.Column("engagement_score", sa.Float),
        sa.Column("snapshot_at", sa.DateTime),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_web_traffic_snapshots_symbol", "web_traffic_snapshots", ["symbol"])

    # Social mentions
    op.create_table(
        "social_mentions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("sentiment_score", sa.Float),
        sa.Column("mentions", sa.Integer),
        sa.Column("volume_change", sa.Float),
        sa.Column("bullish_pct", sa.Float),
        sa.Column("bearish_pct", sa.Float),
        sa.Column("is_spike", sa.Boolean),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_social_mentions_symbol", "social_mentions", ["symbol"])

    # Composite scores
    op.create_table(
        "alt_data_composites",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("satellite_score", sa.Float),
        sa.Column("web_score", sa.Float),
        sa.Column("social_score", sa.Float),
        sa.Column("app_score", sa.Float),
        sa.Column("composite", sa.Float),
        sa.Column("n_sources", sa.Integer),
        sa.Column("quality", sa.String(20)),
        sa.Column("confidence", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_alt_data_composites_symbol", "alt_data_composites", ["symbol"])


def downgrade() -> None:
    op.drop_table("alt_data_composites")
    op.drop_table("social_mentions")
    op.drop_table("web_traffic_snapshots")
    op.drop_table("satellite_signals")
