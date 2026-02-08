"""PRD-114: Notification & Alerting System.

Revision ID: 114
Revises: 110
"""

from alembic import op
import sqlalchemy as sa

revision = "114"
down_revision = "110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_records",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, index=True),
        sa.Column("category", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("dedup_key", sa.String(128), nullable=True),
        sa.Column("occurrence_count", sa.Integer, default=1),
        sa.Column("acknowledged_by", sa.String(128), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("alert_records")
