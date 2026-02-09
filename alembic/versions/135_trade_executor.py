"""PRD-135: Autonomous Trade Executor.

Revision ID: 135
Revises: 134
"""

from alembic import op
import sqlalchemy as sa

revision = "135"
down_revision = "134"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trade executions table
    op.create_table(
        "bot_trade_executions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(50), index=True),
        sa.Column("ticker", sa.String(10), nullable=False, index=True),
        sa.Column("instrument_type", sa.String(20), nullable=False, server_default="stock"),
        sa.Column("original_ticker", sa.String(10), nullable=True),
        sa.Column("leverage", sa.Float(), server_default="1.0"),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("trade_type", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("conviction", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("exit_reason", sa.String(50), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("broker", sa.String(20), nullable=True),
        sa.Column("order_id", sa.String(100), nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Composite indexes
    op.create_index(
        "ix_trade_executions_ticker_status",
        "bot_trade_executions",
        ["ticker", "status"],
    )
    op.create_index(
        "ix_trade_executions_entry_time",
        "bot_trade_executions",
        ["entry_time"],
    )

    # Daily P&L table
    op.create_table(
        "bot_daily_pnl",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True, index=True),
        sa.Column("starting_equity", sa.Float(), nullable=False),
        sa.Column("ending_equity", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("winning_trades", sa.Integer(), nullable=False),
        sa.Column("losing_trades", sa.Integer(), nullable=False),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("kill_switch_triggered", sa.Boolean(), server_default="false"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_trade_executions_entry_time", table_name="bot_trade_executions")
    op.drop_index("ix_trade_executions_ticker_status", table_name="bot_trade_executions")
    op.drop_table("bot_daily_pnl")
    op.drop_table("bot_trade_executions")
