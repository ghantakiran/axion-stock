"""PRD-110: Migration Safety & Reversibility.

Revision ID: 110
Revises: 109
"""

from alembic import op
import sqlalchemy as sa

revision = "110"
down_revision = "109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "migration_audit",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("revision", sa.String(64), nullable=False, index=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("validation_passed", sa.Boolean, nullable=True),
        sa.Column("issues_found", sa.Integer, nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("migration_audit")
