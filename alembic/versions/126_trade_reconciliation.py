"""PRD-126: Trade Reconciliation & Settlement Engine.

Revision ID: 126
Revises: 125
"""

from alembic import op
import sqlalchemy as sa

revision = "126"
down_revision = "125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_records",
        sa.Column("match_id", sa.String(36), primary_key=True),
        sa.Column("internal_trade_id", sa.String(64), nullable=True, index=True),
        sa.Column("broker_trade_id", sa.String(64), nullable=True, index=True),
        sa.Column("symbol", sa.String(20), nullable=True, index=True),
        sa.Column("side", sa.String(10), nullable=True),
        sa.Column("internal_quantity", sa.Float, nullable=True),
        sa.Column("broker_quantity", sa.Float, nullable=True),
        sa.Column("internal_price", sa.Float, nullable=True),
        sa.Column("broker_price", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("break_type", sa.String(30), nullable=True, index=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("resolved_by", sa.String(128), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "settlement_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("trade_id", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("expected_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counterparty", sa.String(128), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("amount", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("settlement_events")
    op.drop_table("reconciliation_records")
