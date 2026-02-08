"""PRD-74: ML Model Registry & Versioning.

Revision ID: 074
Revises: 073
"""

from alembic import op
import sqlalchemy as sa

revision = "074"
down_revision = "073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Model deployment tracking
    op.create_table(
        "ml_model_deployments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("model_name", sa.String(100), nullable=False, index=True),
        sa.Column("model_version", sa.String(20), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("deployed_by", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("endpoint_url", sa.String(500), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
    )

    # Model comparison results
    op.create_table(
        "ml_model_comparisons",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("comparison_name", sa.String(200), nullable=False),
        sa.Column("model_a", sa.String(100), nullable=False),
        sa.Column("model_b", sa.String(100), nullable=False),
        sa.Column("dataset", sa.String(100), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("winner", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ml_model_comparisons")
    op.drop_table("ml_model_deployments")
