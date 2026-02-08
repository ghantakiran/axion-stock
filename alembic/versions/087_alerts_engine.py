"""PRD-87: Alerts Engine.

Revision ID: 087
Revises: 086
"""

from alembic import op
import sqlalchemy as sa

revision = "087"
down_revision = "086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Shareable alert rule templates
    op.create_table(
        "alert_rule_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("alert_type", sa.String(50), nullable=False, index=True),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("cooldown_minutes", sa.Integer(), server_default="60"),
        sa.Column("is_public", sa.Boolean(), server_default="1"),
        sa.Column("created_by", sa.String(50), nullable=True),
        sa.Column("usage_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Escalation tracking for critical alerts
    op.create_table(
        "alert_escalation_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("alert_id", sa.String(36), nullable=False, index=True),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("recipient", sa.String(100), nullable=True),
        sa.Column("delivery_status", sa.String(20), nullable=False),
        sa.Column("response_time_seconds", sa.Float(), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), server_default="0"),
        sa.Column("escalated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("alert_escalation_log")
    op.drop_table("alert_rule_templates")
