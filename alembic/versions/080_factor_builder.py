"""PRD-80: Custom Factor Builder.

Revision ID: 080
Revises: 079
"""

from alembic import op
import sqlalchemy as sa

revision = "080"
down_revision = "079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Custom factor definitions
    op.create_table(
        "custom_factor_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(50), nullable=True, index=True),
        sa.Column("aggregation", sa.String(30), nullable=False, server_default="weighted_average"),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Computed factor results
    op.create_table(
        "custom_factor_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("factor_id", sa.String(36), nullable=False, index=True),
        sa.Column("factor_name", sa.String(100), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("n_scored", sa.Integer(), nullable=False),
        sa.Column("top_symbols", sa.JSON(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("custom_factor_results")
    op.drop_table("custom_factor_definitions")
