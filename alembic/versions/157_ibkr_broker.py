"""PRD-157: Interactive Brokers (IBKR) Integration.

Revision ID: 157
Revises: 156
"""

from alembic import op
import sqlalchemy as sa

revision = "157"
down_revision = "156"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ibkr_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("account_id", sa.String(30), nullable=False, index=True),
        sa.Column("account_type", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("mode", sa.String(10)),
        sa.Column("gateway_host", sa.String(100)),
        sa.Column("gateway_port", sa.Integer),
        sa.Column("net_liquidation", sa.Float),
        sa.Column("buying_power", sa.Float),
        sa.Column("position_count", sa.Integer),
        sa.Column("base_currency", sa.String(5)),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ibkr_order_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("log_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("account_id", sa.String(30), nullable=False, index=True),
        sa.Column("order_id", sa.String(50), nullable=False),
        sa.Column("conid", sa.Integer),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("sec_type", sa.String(10)),
        sa.Column("side", sa.String(20)),
        sa.Column("order_type", sa.String(20)),
        sa.Column("quantity", sa.Float),
        sa.Column("filled_quantity", sa.Float),
        sa.Column("price", sa.Float),
        sa.Column("status", sa.String(20), index=True),
        sa.Column("exchange", sa.String(20)),
        sa.Column("currency", sa.String(5)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ibkr_order_log")
    op.drop_table("ibkr_connections")
