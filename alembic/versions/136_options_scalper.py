"""PRD-136: Options & Leveraged ETF Scalping Engine.

Revision ID: 136
Revises: 135
"""

from alembic import op
import sqlalchemy as sa

revision = "136"
down_revision = "135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Options scalps table
    op.create_table(
        "options_scalps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(50), index=True),
        sa.Column("ticker", sa.String(10), nullable=False, index=True),
        sa.Column("option_symbol", sa.String(30), nullable=False),
        sa.Column("option_type", sa.String(4), nullable=False),
        sa.Column("strike", sa.Float(), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("dte", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("contracts", sa.Integer(), nullable=False),
        sa.Column("entry_premium", sa.Float(), nullable=False),
        sa.Column("exit_premium", sa.Float(), nullable=True),
        sa.Column("entry_delta", sa.Float(), nullable=True),
        sa.Column("entry_theta", sa.Float(), nullable=True),
        sa.Column("entry_iv", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("exit_reason", sa.String(50), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("broker", sa.String(20), nullable=True),
        sa.Column("order_id", sa.String(100), nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_options_scalps_ticker_status", "options_scalps", ["ticker", "status"])
    op.create_index("ix_options_scalps_expiry", "options_scalps", ["expiry"])

    # ETF scalps table
    op.create_table(
        "etf_scalps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(50), index=True),
        sa.Column("ticker", sa.String(10), nullable=False, index=True),
        sa.Column("original_ticker", sa.String(10), nullable=True),
        sa.Column("leverage", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("exit_reason", sa.String(50), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("broker", sa.String(20), nullable=True),
        sa.Column("order_id", sa.String(100), nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_etf_scalps_ticker_status", "etf_scalps", ["ticker", "status"])


def downgrade() -> None:
    op.drop_index("ix_etf_scalps_ticker_status", table_name="etf_scalps")
    op.drop_index("ix_options_scalps_expiry", table_name="options_scalps")
    op.drop_index("ix_options_scalps_ticker_status", table_name="options_scalps")
    op.drop_table("etf_scalps")
    op.drop_table("options_scalps")
