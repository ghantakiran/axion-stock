"""PRD-174: Bot Alerting & Notifications.

Revision ID: 174
Revises: 173
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "174"
down_revision = "173"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_alert_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("severity", sa.String(20), index=True),
        sa.Column("category", sa.String(20)),
        sa.Column("source", sa.String(30)),
        sa.Column("dedup_key", sa.String(100), index=True),
        sa.Column("ticker", sa.String(20), index=True),
        sa.Column("fired_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bot_alert_history")
