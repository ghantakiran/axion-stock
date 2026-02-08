"""PRD-89: Advanced Watchlists.

Revision ID: 089
Revises: 088
"""

from alembic import op
import sqlalchemy as sa

revision = "089"
down_revision = "088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical watchlist state snapshots
    op.create_table(
        "watchlist_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("watchlist_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=True),
        sa.Column("avg_gain_pct", sa.Float(), nullable=True),
        sa.Column("targets_hit", sa.Integer(), server_default="0"),
        sa.Column("snapshot_date", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # User activity audit trail
    op.create_table(
        "watchlist_activity_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("watchlist_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("performed_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("watchlist_activity_log")
    op.drop_table("watchlist_snapshots")
