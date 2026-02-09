"""Coinbase broker integration tables.

Revision ID: 144
Revises: 143
Create Date: 2025-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "144"
down_revision = "143"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Coinbase API connections
    op.create_table(
        "coinbase_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("account_id", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10)),
        sa.Column("total_value_usd", sa.Float),
        sa.Column("crypto_count", sa.Integer),
        sa.Column("usd_balance", sa.Float),
        sa.Column("last_sync", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("config_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Coinbase order log
    op.create_table(
        "coinbase_order_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("local_id", sa.String(50), index=True, nullable=False),
        sa.Column("coinbase_order_id", sa.String(100), index=True),
        sa.Column("product_id", sa.String(20), nullable=False, index=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("size", sa.Float, nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("limit_price", sa.Float),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filled_size", sa.Float),
        sa.Column("filled_price", sa.Float),
        sa.Column("fee", sa.Float),
        sa.Column("signal_id", sa.String(50)),
        sa.Column("error_message", sa.Text),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Coinbase account snapshots
    op.create_table(
        "coinbase_account_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(50), index=True, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, index=True),
        sa.Column("balance", sa.Float, nullable=False),
        sa.Column("available", sa.Float),
        sa.Column("native_value_usd", sa.Float),
        sa.Column("price_usd", sa.Float),
        sa.Column("allocation_pct", sa.Float),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("coinbase_account_snapshots")
    op.drop_table("coinbase_order_log")
    op.drop_table("coinbase_connections")
