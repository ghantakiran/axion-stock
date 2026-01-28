"""Initial schema - all core tables.

Revision ID: 001
Revises: None
Create Date: 2026-01-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- instruments ---
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column(
            "asset_type",
            sa.Enum("STOCK", "ETF", "INDEX", name="assettype"),
            nullable=True,
            server_default="STOCK",
        ),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(200), nullable=True),
        sa.Column("exchange", sa.String(20), nullable=True),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker"),
    )
    op.create_index("ix_instruments_ticker", "instruments", ["ticker"])

    # --- price_bars ---
    op.create_table(
        "price_bars",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("adj_close", sa.Float(), nullable=True),
        sa.Column("source", sa.String(20), server_default="yfinance"),
        sa.PrimaryKeyConstraint("time", "instrument_id"),
    )
    op.create_index(
        "ix_price_bars_instrument_time", "price_bars", ["instrument_id", "time"]
    )

    # --- financials ---
    op.create_table(
        "financials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("trailing_pe", sa.Float(), nullable=True),
        sa.Column("price_to_book", sa.Float(), nullable=True),
        sa.Column("dividend_yield", sa.Float(), nullable=True),
        sa.Column("ev_to_ebitda", sa.Float(), nullable=True),
        sa.Column("return_on_equity", sa.Float(), nullable=True),
        sa.Column("debt_to_equity", sa.Float(), nullable=True),
        sa.Column("revenue_growth", sa.Float(), nullable=True),
        sa.Column("earnings_growth", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("source", sa.String(20), server_default="yfinance"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id", "as_of_date", name="uq_financial_date"),
    )
    op.create_index(
        "ix_financials_instrument_date", "financials", ["instrument_id", "as_of_date"]
    )

    # --- factor_scores ---
    op.create_table(
        "factor_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("computed_date", sa.Date(), nullable=False),
        sa.Column("value_score", sa.Float(), nullable=True),
        sa.Column("momentum_score", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("growth_score", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id", "computed_date", name="uq_score_date"),
    )
    op.create_index("ix_scores_composite", "factor_scores", ["composite_score"])
    op.create_index(
        "ix_scores_instrument_date",
        "factor_scores",
        ["instrument_id", "computed_date"],
    )

    # --- economic_indicators ---
    op.create_table(
        "economic_indicators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("series_id", sa.String(50), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("source", sa.String(20), server_default="fred"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_id", "date", name="uq_indicator_date"),
    )
    op.create_index(
        "ix_indicator_series_date", "economic_indicators", ["series_id", "date"]
    )

    # --- data_quality_logs ---
    op.create_table(
        "data_quality_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("check_name", sa.String(100), nullable=False),
        sa.Column("table_name", sa.String(50), nullable=True),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("data_quality_logs")
    op.drop_table("economic_indicators")
    op.drop_table("factor_scores")
    op.drop_table("financials")
    op.drop_table("price_bars")
    op.drop_table("instruments")
    op.execute("DROP TYPE IF EXISTS assettype")
