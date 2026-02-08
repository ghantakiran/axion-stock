"""PRD-120: Deployment Strategies & Rollback Automation.

Revision ID: 120
Revises: 119
"""

from alembic import op
import sqlalchemy as sa

revision = "120"
down_revision = "119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployments",
        sa.Column("deployment_id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("previous_version", sa.String(50), nullable=True),
        sa.Column("strategy", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("deployed_by", sa.String(100), nullable=False, server_default="system"),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "deployment_validations",
        sa.Column("check_id", sa.String(36), primary_key=True),
        sa.Column("deployment_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("actual_value", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("deployment_validations")
    op.drop_table("deployments")
