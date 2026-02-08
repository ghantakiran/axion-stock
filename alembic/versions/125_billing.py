"""PRD-125: Cost & Usage Metering + Billing.

Revision ID: 125
Revises: 124
"""

from alembic import op
import sqlalchemy as sa

revision = "125"
down_revision = "124"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_meters",
        sa.Column("meter_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("meter_type", sa.String(32), nullable=False, index=True),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("price_per_unit", sa.Float(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True, index=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_value", sa.Float(), nullable=True, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )

    op.create_table(
        "invoices",
        sa.Column("invoice_id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("bill_id", sa.String(36), nullable=False, index=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("line_items_json", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("invoices")
    op.drop_table("billing_meters")
