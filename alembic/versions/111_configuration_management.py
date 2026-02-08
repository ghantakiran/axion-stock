"""PRD-111: Centralized Configuration Management.

Revision ID: 111
Revises: 110
"""

from alembic import op
import sqlalchemy as sa

revision = "111"
down_revision = "110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_entries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(256), nullable=False, unique=True, index=True),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("value_type", sa.String(32), nullable=False),
        sa.Column("namespace", sa.String(64), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_sensitive", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "feature_flags",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("flag_type", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean, default=False),
        sa.Column("percentage", sa.Float, nullable=True),
        sa.Column("user_list", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("feature_flags")
    op.drop_table("config_entries")
