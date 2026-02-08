"""PRD-130: Capacity Planning & Auto-Scaling.

Revision ID: 130
Revises: 129
"""

from alembic import op
import sqlalchemy as sa

revision = "130"
down_revision = "129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capacity_metrics",
        sa.Column("metric_id", sa.String(36), primary_key=True),
        sa.Column("resource_type", sa.String(32), nullable=False, index=True),
        sa.Column("service", sa.String(128), nullable=False, index=True),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("capacity", sa.Float(), nullable=False),
        sa.Column("utilization_pct", sa.Float(), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=True, index=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )

    op.create_table(
        "scaling_events",
        sa.Column("action_id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(36), nullable=False, index=True),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("from_value", sa.Integer(), nullable=False),
        sa.Column("to_value", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("scaling_events")
    op.drop_table("capacity_metrics")
