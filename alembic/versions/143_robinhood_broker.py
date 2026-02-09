"""Robinhood Broker Integration.

Revision ID: 143
Revises: 142
Create Date: 2025-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "143"
down_revision = "142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Robinhood connections
    op.create_table(
        "robinhood_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("username", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10)),
        sa.Column("account_number", sa.String(50)),
        sa.Column("equity", sa.Float),
        sa.Column("buying_power", sa.Float),
        sa.Column("cash", sa.Float),
        sa.Column("position_count", sa.Integer),
        sa.Column("last_sync", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("config_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Robinhood order log
    op.create_table(
        "robinhood_order_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("local_id", sa.String(50), index=True, nullable=False),
        sa.Column("rh_order_id", sa.String(100), index=True),
        sa.Column("symbol", sa.String(10), nullable=False, index=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("time_in_force", sa.String(10)),
        sa.Column("limit_price", sa.Float),
        sa.Column("stop_price", sa.Float),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filled_qty", sa.Float),
        sa.Column("filled_avg_price", sa.Float),
        sa.Column("signal_id", sa.String(50)),
        sa.Column("strategy", sa.String(50)),
        sa.Column("error_message", sa.Text),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("filled_at", sa.DateTime(timezone=True)),
        sa.Column("canceled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("robinhood_order_log")
    op.drop_table("robinhood_connections")
