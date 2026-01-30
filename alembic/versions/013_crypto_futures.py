"""Crypto & futures expansion tables.

Revision ID: 013
Revises: 012
Create Date: 2026-01-30

Adds:
- crypto_assets: Crypto instrument metadata
- crypto_factor_scores: Crypto factor score history
- futures_contracts: Futures contract specs and active contracts
- futures_positions: Open futures positions
- fx_rates: FX rate history
- multi_asset_portfolios: Cross-asset portfolio records
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crypto assets
    op.create_table(
        "crypto_assets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), unique=True, nullable=False),
        sa.Column("name", sa.String(128)),
        sa.Column("category", sa.String(32)),
        sa.Column("market_cap", sa.Float),
        sa.Column("circulating_supply", sa.Float),
        sa.Column("max_supply", sa.Float, nullable=True),
        sa.Column("rank", sa.Integer),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Crypto factor scores
    op.create_table(
        "crypto_factor_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("score_date", sa.Date, nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("momentum", sa.Float),
        sa.Column("quality", sa.Float),
        sa.Column("sentiment", sa.Float),
        sa.Column("network", sa.Float),
        sa.Column("composite", sa.Float),
    )
    op.create_index(
        "ix_crypto_scores_symbol_date",
        "crypto_factor_scores", ["symbol", "score_date"],
    )

    # Futures contracts
    op.create_table(
        "futures_contracts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("root", sa.String(8), nullable=False),
        sa.Column("symbol", sa.String(16), unique=True, nullable=False),
        sa.Column("contract_month", sa.String(8)),
        sa.Column("category", sa.String(32)),
        sa.Column("multiplier", sa.Float),
        sa.Column("tick_size", sa.Float),
        sa.Column("tick_value", sa.Float),
        sa.Column("margin_initial", sa.Float),
        sa.Column("margin_maintenance", sa.Float),
        sa.Column("expiry", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
    )
    op.create_index("ix_futures_contracts_root", "futures_contracts", ["root"])

    # Futures positions
    op.create_table(
        "futures_positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("contract_symbol", sa.String(16), nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("avg_entry_price", sa.Float),
        sa.Column("current_price", sa.Float),
        sa.Column("margin_required", sa.Float),
        sa.Column("unrealized_pnl", sa.Float),
        sa.Column("opened_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_futures_positions_account", "futures_positions", ["account_id"])

    # FX rates
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("quote_currency", sa.String(8), nullable=False),
        sa.Column("rate", sa.Float, nullable=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_fx_rates_pair_ts",
        "fx_rates", ["base_currency", "quote_currency", "timestamp"],
    )

    # Multi-asset portfolios
    op.create_table(
        "multi_asset_portfolios",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("portfolio_id", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(128)),
        sa.Column("user_id", sa.String(64)),
        sa.Column("template", sa.String(64)),
        sa.Column("total_value_usd", sa.Float),
        sa.Column("allocations_json", sa.JSON),
        sa.Column("risk_report_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_multi_asset_user", "multi_asset_portfolios", ["user_id"])


def downgrade() -> None:
    op.drop_table("multi_asset_portfolios")
    op.drop_table("fx_rates")
    op.drop_table("futures_positions")
    op.drop_table("futures_contracts")
    op.drop_table("crypto_factor_scores")
    op.drop_table("crypto_assets")
