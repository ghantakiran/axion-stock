"""PRD-172: Bot API & WebSocket Control.

Revision ID: 172
Revises: 171
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "172"
down_revision = "171"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_api_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("user_id", sa.String(100), index=True),
        sa.Column("session_type", sa.String(20)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("started_at", sa.DateTime(timezone=True), index=True),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bot_api_sessions")
