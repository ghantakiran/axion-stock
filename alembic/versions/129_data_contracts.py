"""PRD-129: Data Contracts & Schema Governance.

Revision ID: 129
Revises: 128
"""

from alembic import op
import sqlalchemy as sa

revision = "129"
down_revision = "128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Data contract definitions
    op.create_table(
        "data_contracts",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("producer", sa.String(100), nullable=False, index=True),
        sa.Column("consumer", sa.String(100), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, default="draft", index=True),
        sa.Column("schema_version", sa.String(20), nullable=True),
        sa.Column("schema_definition", sa.JSON(), nullable=True),
        sa.Column("compatibility_mode", sa.String(20), nullable=True, default="backward"),
        sa.Column("validation_level", sa.String(20), nullable=True, default="strict"),
        sa.Column("sla_config", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("version_history", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Contract violations log
    op.create_table(
        "contract_violations",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("contract_id", sa.String(16), nullable=False, index=True),
        sa.Column("violation_type", sa.String(30), nullable=False, index=True),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("expected", sa.Text(), nullable=True),
        sa.Column("actual", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, default="error"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("contract_violations")
    op.drop_table("data_contracts")
