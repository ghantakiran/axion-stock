"""PRD-66: Trade Journal Dashboard.

Revision ID: 066
Revises: 065
"""

from alembic import op
import sqlalchemy as sa

revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trade journal tags for categorization
    op.create_table(
        "journal_tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("color", sa.String(20), default="#2196F3"),
        sa.Column("usage_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Trade journal screenshots/attachments
    op.create_table(
        "journal_attachments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.String(36), nullable=False, index=True),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(200), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("journal_attachments")
    op.drop_table("journal_tags")
