"""Signal Fusion Agent tables.

Revision ID: 147
Revises: 146
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "147"
down_revision = "146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Signal fusion scan log
    op.create_table(
        "signal_fusion_scans",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scan_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signals_count", sa.Integer, nullable=False),
        sa.Column("fusions_count", sa.Integer, nullable=False),
        sa.Column("recommendations_count", sa.Integer, nullable=False),
        sa.Column("state_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Signal fusion recommendations
    op.create_table(
        "signal_fusion_recommendations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rec_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("scan_id", sa.String(50), index=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("composite_score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("position_size_pct", sa.Float),
        sa.Column("reasoning_json", sa.Text),
        sa.Column("executed", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("signal_fusion_recommendations")
    op.drop_table("signal_fusion_scans")
