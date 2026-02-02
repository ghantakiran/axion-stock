"""Crowding analysis system tables.

Revision ID: 035
Revises: 034
Create Date: 2026-02-01

Adds:
- crowding_scores: Position crowding snapshots
- fund_overlaps: Fund overlap scores
- short_interest: Short interest records
- consensus_signals: Consensus divergence signals
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crowding scores
    op.create_table(
        "crowding_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("level", sa.String(20)),
        sa.Column("n_holders", sa.Integer),
        sa.Column("concentration", sa.Float),
        sa.Column("momentum", sa.Float),
        sa.Column("percentile", sa.Float),
        sa.Column("is_decrowding", sa.Boolean),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_crowding_scores_symbol", "crowding_scores", ["symbol"])

    # Fund overlaps
    op.create_table(
        "fund_overlaps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("fund_a", sa.String(100), nullable=False),
        sa.Column("fund_b", sa.String(100), nullable=False),
        sa.Column("overlap_score", sa.Float),
        sa.Column("shared_positions", sa.Integer),
        sa.Column("total_positions_a", sa.Integer),
        sa.Column("total_positions_b", sa.Integer),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_fund_overlaps_funds", "fund_overlaps", ["fund_a", "fund_b"])

    # Short interest
    op.create_table(
        "short_interest",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("shares_short", sa.Float),
        sa.Column("float_shares", sa.Float),
        sa.Column("si_ratio", sa.Float),
        sa.Column("days_to_cover", sa.Float),
        sa.Column("cost_to_borrow", sa.Float),
        sa.Column("squeeze_score", sa.Float),
        sa.Column("risk", sa.String(20)),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_short_interest_symbol", "short_interest", ["symbol"])

    # Consensus signals
    op.create_table(
        "consensus_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("mean_rating", sa.Float),
        sa.Column("n_analysts", sa.Integer),
        sa.Column("buy_count", sa.Integer),
        sa.Column("hold_count", sa.Integer),
        sa.Column("sell_count", sa.Integer),
        sa.Column("mean_target", sa.Float),
        sa.Column("target_upside", sa.Float),
        sa.Column("divergence", sa.Float),
        sa.Column("is_contrarian", sa.Boolean),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_consensus_signals_symbol", "consensus_signals", ["symbol"])


def downgrade() -> None:
    op.drop_table("consensus_signals")
    op.drop_table("short_interest")
    op.drop_table("fund_overlaps")
    op.drop_table("crowding_scores")
