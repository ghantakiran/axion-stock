"""PRD-123: Feature Store & ML Feature Management.

Revision ID: 123
Revises: 122
"""

from alembic import op
import sqlalchemy as sa

revision = "123"
down_revision = "122"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_definitions",
        sa.Column("feature_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feature_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50), nullable=False, index=True),
        sa.Column("owner", sa.String(100), nullable=False, server_default="system"),
        sa.Column("freshness_sla_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("dependencies", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("compute_mode", sa.String(20), nullable=False, server_default="batch"),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "feature_values",
        sa.Column("value_id", sa.String(36), primary_key=True),
        sa.Column("feature_id", sa.String(36), nullable=False, index=True),
        sa.Column("entity_id", sa.String(100), nullable=False, index=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("as_of_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("feature_values")
    op.drop_table("feature_definitions")
