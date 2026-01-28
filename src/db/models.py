"""SQLAlchemy ORM models for the Axion platform.

Tables:
- instruments: Stock/ETF universe with metadata
- price_bars: OHLCV time-series (TimescaleDB hypertable)
- financials: Fundamental data snapshots
- factor_scores: Pre-computed factor scores
- economic_indicators: FRED macro data
- data_quality_logs: Validation audit trail
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from src.db.base import Base


class AssetType(enum.Enum):
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"


class Instrument(Base):
    """Tradeable instrument (stock, ETF, index)."""

    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200))
    asset_type = Column(Enum(AssetType), default=AssetType.STOCK)
    sector = Column(String(100))
    industry = Column(String(200))
    exchange = Column(String(20))
    market_cap = Column(BigInteger)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PriceBar(Base):
    """OHLCV price data. Converted to TimescaleDB hypertable via migration."""

    __tablename__ = "price_bars"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    instrument_id = Column(Integer, primary_key=True, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    adj_close = Column(Float)
    source = Column(String(20), default="yfinance")

    __table_args__ = (
        Index("ix_price_bars_instrument_time", "instrument_id", "time"),
    )


class Financial(Base):
    """Fundamental data snapshot for an instrument on a given date."""

    __tablename__ = "financials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(Integer, nullable=False, index=True)
    as_of_date = Column(Date, nullable=False)
    trailing_pe = Column(Float)
    price_to_book = Column(Float)
    dividend_yield = Column(Float)
    ev_to_ebitda = Column(Float)
    return_on_equity = Column(Float)
    debt_to_equity = Column(Float)
    revenue_growth = Column(Float)
    earnings_growth = Column(Float)
    market_cap = Column(BigInteger)
    current_price = Column(Float)
    source = Column(String(20), default="yfinance")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("instrument_id", "as_of_date", name="uq_financial_date"),
        Index("ix_financials_instrument_date", "instrument_id", "as_of_date"),
    )


class FactorScore(Base):
    """Pre-computed factor scores for an instrument."""

    __tablename__ = "factor_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(Integer, nullable=False, index=True)
    computed_date = Column(Date, nullable=False)
    value_score = Column(Float)
    momentum_score = Column(Float)
    quality_score = Column(Float)
    growth_score = Column(Float)
    composite_score = Column(Float)

    __table_args__ = (
        UniqueConstraint("instrument_id", "computed_date", name="uq_score_date"),
        Index("ix_scores_composite", "composite_score"),
        Index("ix_scores_instrument_date", "instrument_id", "computed_date"),
    )


class EconomicIndicator(Base):
    """Economic indicator time-series from FRED."""

    __tablename__ = "economic_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(String(50), nullable=False)
    date = Column(Date, nullable=False)
    value = Column(Float)
    source = Column(String(20), default="fred")

    __table_args__ = (
        UniqueConstraint("series_id", "date", name="uq_indicator_date"),
        Index("ix_indicator_series_date", "series_id", "date"),
    )


class DataQualityLog(Base):
    """Audit log for data quality validation checks."""

    __tablename__ = "data_quality_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    check_name = Column(String(100), nullable=False)
    table_name = Column(String(50))
    ticker = Column(String(20))
    severity = Column(String(20))  # info, warning, error, critical
    message = Column(String(500))
    details = Column(Text)  # JSON string
    created_at = Column(DateTime, server_default=func.now())
