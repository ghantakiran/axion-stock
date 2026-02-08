"""PRD-119: WebSocket Scaling & Real-time Infrastructure.

Revision ID: 119
Revises: 118
"""

from alembic import op
import sqlalchemy as sa

revision = "119"
down_revision = "118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ws_connections",
        sa.Column("connection_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False, index=True),
        sa.Column("instance_id", sa.String(100), nullable=False, index=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="connected"),
        sa.Column("subscriptions", sa.Text(), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("disconnected_at", sa.DateTime(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ws_connections")
