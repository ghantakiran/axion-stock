"""PRD-68: Multi-Account Management.

Revision ID: 054
Revises: 053
"""

from alembic import op
import sqlalchemy as sa

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trading accounts
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("account_type", sa.String(30), nullable=False),  # individual, ira_traditional, ira_roth, etc.
        sa.Column("broker", sa.String(30), nullable=False),  # paper, alpaca, ibkr
        sa.Column("broker_account_id", sa.String(100), nullable=True),
        # Strategy
        sa.Column("strategy_id", sa.String(36), nullable=True),
        sa.Column("strategy_name", sa.String(100), nullable=True),
        sa.Column("target_allocation", sa.JSON(), nullable=True),
        # Financials
        sa.Column("cash_balance", sa.Float(), server_default="0"),
        sa.Column("total_value", sa.Float(), server_default="0"),
        sa.Column("cost_basis", sa.Float(), server_default="0"),
        # Tax
        sa.Column("tax_status", sa.String(20), nullable=False),  # taxable, tax_deferred, tax_free
        # Benchmark
        sa.Column("benchmark", sa.String(20), server_default="'SPY'"),
        # Dates
        sa.Column("inception_date", sa.Date(), nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_primary", sa.Boolean(), server_default="false"),
        # Permissions (JSON array of user IDs who can access)
        sa.Column("permissions", sa.JSON(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Account snapshots (daily performance history)
    op.create_table(
        "account_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        # Values
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("cash_balance", sa.Float(), nullable=False),
        sa.Column("positions_value", sa.Float(), nullable=False),
        # P&L
        sa.Column("day_pnl", sa.Float(), nullable=True),
        sa.Column("day_return_pct", sa.Float(), nullable=True),
        sa.Column("total_pnl", sa.Float(), nullable=True),
        sa.Column("total_return_pct", sa.Float(), nullable=True),
        # Positions JSON snapshot
        sa.Column("positions", sa.JSON(), nullable=True),
        # Metrics
        sa.Column("num_positions", sa.Integer(), nullable=True),
        sa.Column("portfolio_beta", sa.Float(), nullable=True),
        sa.Column("portfolio_volatility", sa.Float(), nullable=True),
        # Timestamp
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Current positions per account
    op.create_table(
        "account_positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_cost", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl_pct", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),  # % of portfolio
        sa.Column("asset_class", sa.String(30), nullable=True),  # equity, fixed_income, cash, etc.
        sa.Column("sector", sa.String(50), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Linked accounts (for household/family view)
    op.create_table(
        "account_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("primary_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("linked_account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship", sa.String(30), nullable=True),  # spouse, child, trust, etc.
        sa.Column("access_level", sa.String(20), nullable=False),  # view, trade, manage
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Rebalancing history
    op.create_table(
        "rebalancing_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rebalance_date", sa.DateTime(), nullable=False),
        sa.Column("rebalance_type", sa.String(30), nullable=True),  # threshold, scheduled, manual
        sa.Column("pre_allocation", sa.JSON(), nullable=True),
        sa.Column("post_allocation", sa.JSON(), nullable=True),
        sa.Column("trades_executed", sa.JSON(), nullable=True),
        sa.Column("total_traded_value", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),  # completed, partial, failed
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes
    op.create_index("ix_accounts_owner_id", "accounts", ["owner_id"])
    op.create_index("ix_accounts_broker", "accounts", ["broker"])
    op.create_index("ix_account_snapshots_account_date", "account_snapshots", ["account_id", "snapshot_date"])
    op.create_index("ix_account_positions_account_id", "account_positions", ["account_id"])
    op.create_index("ix_account_positions_symbol", "account_positions", ["symbol"])

    # Unique constraint for one snapshot per account per day
    op.create_unique_constraint(
        "uq_account_snapshot_date",
        "account_snapshots",
        ["account_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_account_snapshot_date", "account_snapshots")
    op.drop_index("ix_account_positions_symbol")
    op.drop_index("ix_account_positions_account_id")
    op.drop_index("ix_account_snapshots_account_date")
    op.drop_index("ix_accounts_broker")
    op.drop_index("ix_accounts_owner_id")
    op.drop_table("rebalancing_history")
    op.drop_table("account_links")
    op.drop_table("account_positions")
    op.drop_table("account_snapshots")
    op.drop_table("accounts")
