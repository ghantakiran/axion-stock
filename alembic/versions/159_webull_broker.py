"""PRD-159: Webull Broker Integration.

Revision ID: 159
Revises: 158
"""

from alembic import op
import sqlalchemy as sa

revision = "159"
down_revision = "158"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webull_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("account_id", sa.String(30), nullable=False, index=True),
        sa.Column("account_type", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("mode", sa.String(10)),
        sa.Column("device_id", sa.String(50)),
        sa.Column("net_liquidation", sa.Float),
        sa.Column("buying_power", sa.Float),
        sa.Column("day_trades_remaining", sa.Integer),
        sa.Column("position_count", sa.Integer),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "webull_order_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("log_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("account_id", sa.String(30), nullable=False, index=True),
        sa.Column("order_id", sa.String(50), nullable=False),
        sa.Column("ticker_id", sa.Integer),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("action", sa.String(20)),
        sa.Column("order_type", sa.String(20)),
        sa.Column("quantity", sa.Float),
        sa.Column("filled_quantity", sa.Float),
        sa.Column("price", sa.Float),
        sa.Column("status", sa.String(20), index=True),
        sa.Column("outside_regular_hours", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("webull_order_log")
    op.drop_table("webull_connections")
