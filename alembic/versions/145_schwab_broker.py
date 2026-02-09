"""Schwab broker integration.

Revision ID: 145
Revises: 144
Create Date: 2025-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "145"
down_revision = "144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schwab API connections
    op.create_table(
        "schwab_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("account_number", sa.String(100)),
        sa.Column("account_type", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10)),
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

    # Schwab order execution log
    op.create_table(
        "schwab_order_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("local_id", sa.String(50), index=True, nullable=False),
        sa.Column("schwab_order_id", sa.String(100), index=True),
        sa.Column("account_number", sa.String(100)),
        sa.Column("symbol", sa.String(10), nullable=False, index=True),
        sa.Column("instruction", sa.String(20), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("duration", sa.String(10)),
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
    op.drop_table("schwab_order_log")
    op.drop_table("schwab_connections")
