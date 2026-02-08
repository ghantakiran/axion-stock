"""PRD-84: Options Flow Analysis.

Revision ID: 084
Revises: 083
"""

from alembic import op
import sqlalchemy as sa

revision = "084"
down_revision = "083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Aggregated options flow analytics
    op.create_table(
        "options_flow_aggregates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("total_premium", sa.Float(), nullable=False),
        sa.Column("call_premium", sa.Float(), nullable=False),
        sa.Column("put_premium", sa.Float(), nullable=False),
        sa.Column("net_sentiment", sa.String(20), nullable=True),
        sa.Column("sweep_count", sa.Integer(), server_default="0"),
        sa.Column("block_count", sa.Integer(), server_default="0"),
        sa.Column("unusual_count", sa.Integer(), server_default="0"),
        sa.Column("put_call_ratio", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Smart alert configuration and history
    op.create_table(
        "options_smart_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=True, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=False),
        sa.Column("triggered", sa.Boolean(), server_default="0"),
        sa.Column("trigger_value", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("triggered_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("options_smart_alerts")
    op.drop_table("options_flow_aggregates")
