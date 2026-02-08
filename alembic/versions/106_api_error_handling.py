"""PRD-106: API Error Handling & Validation.

Revision ID: 106
Revises: 105
"""

from alembic import op
import sqlalchemy as sa

revision = "106"
down_revision = "105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_error_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("error_code", sa.String(64), nullable=False, index=True),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("path", sa.String(512), nullable=True),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True, index=True),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("api_error_logs")
