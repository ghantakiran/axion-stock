"""PRD-71: Compliance & Audit.

Revision ID: 071
Revises: 070
"""

from alembic import op
import sqlalchemy as sa

revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Compliance check overrides (audit trail for manual overrides)
    op.create_table(
        "compliance_overrides",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("violation_id", sa.String(36), nullable=False, index=True),
        sa.Column("check_id", sa.BigInteger(), nullable=True),
        sa.Column("override_by", sa.String(36), nullable=False, index=True),
        sa.Column("override_reason", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Compliance rule change history
    op.create_table(
        "compliance_rule_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.String(36), nullable=False, index=True),
        sa.Column("changed_by", sa.String(36), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("compliance_rule_history")
    op.drop_table("compliance_overrides")
