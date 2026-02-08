"""PRD-99: Compliance Engine.

Revision ID: 099
Revises: 098
"""

from alembic import op
import sqlalchemy as sa

revision = "099"
down_revision = "098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trade surveillance alert records
    op.create_table(
        "surveillance_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("alert_type", sa.String(30), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("account_id", sa.String(36), nullable=True),
        sa.Column("trader_id", sa.String(36), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pattern_details", sa.JSON(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), default=False),
        sa.Column("resolved_by", sa.String(100), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Execution quality metrics
    op.create_table(
        "best_execution_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("fill_price", sa.Float(), nullable=False),
        sa.Column("benchmark_price", sa.Float(), nullable=True),
        sa.Column("slippage_bps", sa.Float(), nullable=True),
        sa.Column("price_improvement_bps", sa.Float(), nullable=True),
        sa.Column("quality", sa.String(20), nullable=True),
        sa.Column("venue", sa.String(30), nullable=True),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("best_execution_log")
    op.drop_table("surveillance_alerts")
