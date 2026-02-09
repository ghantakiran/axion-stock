"""PRD-158: tastytrade Broker Integration.

Revision ID: 158
Revises: 157
"""

from alembic import op
import sqlalchemy as sa

revision = "158"
down_revision = "157"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tastytrade_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("account_number", sa.String(30), nullable=False, index=True),
        sa.Column("account_type", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("mode", sa.String(10)),
        sa.Column("net_liquidating_value", sa.Float),
        sa.Column("option_level", sa.Integer),
        sa.Column("futures_enabled", sa.Boolean, default=False),
        sa.Column("position_count", sa.Integer),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tastytrade_order_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("log_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("account_number", sa.String(30), nullable=False, index=True),
        sa.Column("order_id", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False, index=True),
        sa.Column("instrument_type", sa.String(20)),
        sa.Column("order_type", sa.String(20)),
        sa.Column("order_class", sa.String(20)),
        sa.Column("size", sa.Float),
        sa.Column("filled_size", sa.Float),
        sa.Column("price", sa.Float),
        sa.Column("status", sa.String(20), index=True),
        sa.Column("legs_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tastytrade_order_log")
    op.drop_table("tastytrade_connections")
