"""PRD-127: Workflow Engine & Approval System.

Revision ID: 127
Revises: 126
"""

from alembic import op
import sqlalchemy as sa

revision = "127"
down_revision = "126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Workflow instance tracking
    op.create_table(
        "workflow_instances",
        sa.Column("instance_id", sa.String(36), primary_key=True),
        sa.Column("template_name", sa.String(128), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("current_state", sa.String(64), nullable=True),
        sa.Column("requester", sa.String(128), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("approval_level", sa.String(20), nullable=True),
        sa.Column("trigger_type", sa.String(20), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # State transition audit log
    op.create_table(
        "workflow_transitions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.String(36), nullable=False, index=True),
        sa.Column("from_state", sa.String(64), nullable=False),
        sa.Column("to_state", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_instances")
