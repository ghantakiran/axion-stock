"""PRD-91: Advanced Stock Screener.

Revision ID: 091
Revises: 090
"""

from alembic import op
import sqlalchemy as sa

revision = "091"
down_revision = "090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cached screen results for historical comparison
    op.create_table(
        "saved_screen_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("screen_id", sa.String(36), nullable=False, index=True),
        sa.Column("screen_name", sa.String(100), nullable=False),
        sa.Column("matched_symbols", sa.JSON(), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=False),
        sa.Column("new_entries", sa.JSON(), nullable=True),
        sa.Column("exits", sa.JSON(), nullable=True),
        sa.Column("run_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Detected pattern history log
    op.create_table(
        "scan_pattern_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("pattern_type", sa.String(50), nullable=False),
        sa.Column("pattern_name", sa.String(100), nullable=False),
        sa.Column("signal_strength", sa.String(20), nullable=True),
        sa.Column("price_at_detection", sa.Float(), nullable=True),
        sa.Column("volume_at_detection", sa.Float(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("scan_pattern_history")
    op.drop_table("saved_screen_results")
