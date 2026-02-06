"""SQLAlchemy ORM models for the Axion platform.

Tables:
- instruments: Stock/ETF universe with metadata and GICS classification
- price_bars: OHLCV time-series (TimescaleDB hypertable)
- financials: Fundamental data snapshots
- factor_scores: Pre-computed factor scores (v2: 6 categories)
- economic_indicators: FRED macro data
- market_regimes: Historical regime classifications
- trade_orders: Order history and status
- trade_executions: Executed trade records
- portfolio_snapshots: Daily portfolio snapshots
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


class MarketRegimeType(enum.Enum):
    """Market regime classification."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    CRISIS = "crisis"


class Instrument(Base):
    """Tradeable instrument (stock, ETF, index) with GICS classification."""

    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200))
    asset_type = Column(Enum(AssetType), default=AssetType.STOCK)
    
    # Legacy sector/industry (kept for backward compatibility)
    sector = Column(String(100))
    industry = Column(String(200))
    
    # GICS Classification (4-level hierarchy)
    gics_sector = Column(String(100), index=True)  # Level 1: 11 sectors
    gics_industry_group = Column(String(100))  # Level 2: 25 industry groups
    gics_industry = Column(String(100))  # Level 3: 74 industries
    gics_sub_industry = Column(String(100))  # Level 4: 163 sub-industries
    gics_sector_code = Column(String(10))  # Numeric GICS code (e.g., "45")
    
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
    """Pre-computed factor scores for an instrument (v2: 6 categories)."""

    __tablename__ = "factor_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(Integer, nullable=False, index=True)
    computed_date = Column(Date, nullable=False)
    
    # Original 4 factors
    value_score = Column(Float)
    momentum_score = Column(Float)
    quality_score = Column(Float)
    growth_score = Column(Float)
    
    # New v2 factors
    volatility_score = Column(Float)
    technical_score = Column(Float)
    
    # Composite scores
    composite_score = Column(Float)
    sector_relative_score = Column(Float)  # Sector-adjusted composite
    
    # Metadata
    regime = Column(Enum(MarketRegimeType))  # Regime at time of computation
    engine_version = Column(String(10), default="v2")  # Track which engine computed

    __table_args__ = (
        UniqueConstraint("instrument_id", "computed_date", name="uq_score_date"),
        Index("ix_scores_composite", "composite_score"),
        Index("ix_scores_instrument_date", "instrument_id", "computed_date"),
        Index("ix_scores_sector_relative", "sector_relative_score"),
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


class MarketRegime(Base):
    """Historical market regime classifications."""

    __tablename__ = "market_regimes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    regime = Column(Enum(MarketRegimeType), nullable=False)
    confidence = Column(Float)
    
    # Regime features (for debugging/analysis)
    sp500_trend_strength = Column(Float)
    vix_level = Column(Float)
    breadth_ratio = Column(Float)
    momentum_1m = Column(Float)
    
    # Weights used for this regime
    value_weight = Column(Float)
    momentum_weight = Column(Float)
    quality_weight = Column(Float)
    growth_weight = Column(Float)
    volatility_weight = Column(Float)
    technical_weight = Column(Float)
    
    created_at = Column(DateTime, server_default=func.now())


class OrderSideType(enum.Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatusType(enum.Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderTypeEnum(enum.Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class TradeOrder(Base):
    """Order history for trade journaling."""

    __tablename__ = "trade_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(100), unique=True, nullable=False, index=True)
    client_order_id = Column(String(100))
    
    # Order details
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(OrderSideType), nullable=False)
    order_type = Column(Enum(OrderTypeEnum), nullable=False)
    quantity = Column(Float, nullable=False)
    limit_price = Column(Float)
    stop_price = Column(Float)
    
    # Execution details
    filled_quantity = Column(Float, default=0)
    filled_avg_price = Column(Float)
    status = Column(Enum(OrderStatusType), nullable=False)
    
    # Costs
    commission = Column(Float, default=0)
    slippage = Column(Float, default=0)
    
    # Context
    trigger = Column(String(50))  # 'manual', 'rebalance', 'signal', 'stop_loss'
    broker = Column(String(50))  # 'paper', 'alpaca', 'ibkr'
    regime_at_order = Column(Enum(MarketRegimeType))
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    submitted_at = Column(DateTime)
    filled_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    
    # Notes
    notes = Column(Text)

    __table_args__ = (
        Index("ix_orders_symbol_date", "symbol", "created_at"),
        Index("ix_orders_status", "status"),
    )


class TradeExecution(Base):
    """Individual trade execution records."""

    __tablename__ = "trade_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(100), unique=True, nullable=False)
    order_id = Column(String(100), nullable=False, index=True)
    
    # Trade details
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(OrderSideType), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    
    # Costs
    commission = Column(Float, default=0)
    slippage = Column(Float, default=0)
    
    # Context at time of trade
    factor_scores = Column(Text)  # JSON: {value: 0.8, momentum: 0.7, ...}
    regime_at_trade = Column(Enum(MarketRegimeType))
    portfolio_value_at_trade = Column(Float)
    
    # Timestamps
    executed_at = Column(DateTime, nullable=False, index=True)
    
    # Notes
    notes = Column(Text)

    __table_args__ = (
        Index("ix_executions_symbol_date", "symbol", "executed_at"),
    )


class PortfolioSnapshot(Base):
    """Daily portfolio snapshots for performance tracking."""

    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    
    # Account values
    cash = Column(Float, nullable=False)
    portfolio_value = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    
    # Performance metrics
    daily_pnl = Column(Float)
    daily_return_pct = Column(Float)
    cumulative_return_pct = Column(Float)
    
    # Risk metrics
    portfolio_beta = Column(Float)
    portfolio_volatility = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    
    # Position details (JSON)
    positions = Column(Text)  # JSON array of positions
    
    # Context
    regime = Column(Enum(MarketRegimeType))
    num_positions = Column(Integer)
    
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("snapshot_date", name="uq_snapshot_date"),
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


# ---------------------------------------------------------------------------
# PRD-42: Order Flow Analysis
# ---------------------------------------------------------------------------


class OrderbookSnapshotRecord(Base):
    """Order book imbalance history (PRD-42)."""

    __tablename__ = "orderbook_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    bid_volume = Column(Float)
    ask_volume = Column(Float)
    imbalance_ratio = Column(Float)
    imbalance_type = Column(String(16))
    signal = Column(String(16))
    timestamp = Column(DateTime)
    computed_at = Column(DateTime, server_default=func.now())


class BlockTradeRecord(Base):
    """Detected large block trades (PRD-42)."""

    __tablename__ = "block_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    size = Column(Integer)
    price = Column(Float)
    side = Column(String(4))
    dollar_value = Column(Float)
    block_size = Column(String(16), index=True)
    timestamp = Column(DateTime)
    computed_at = Column(DateTime, server_default=func.now())


class FlowPressureRecord(Base):
    """Buy/sell pressure measurements (PRD-42)."""

    __tablename__ = "flow_pressure"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    buy_volume = Column(Float)
    sell_volume = Column(Float)
    net_flow = Column(Float)
    pressure_ratio = Column(Float)
    direction = Column(String(16))
    cumulative_delta = Column(Float)
    date = Column(Date)
    computed_at = Column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_flow_pressure_symbol_date", "symbol", "date"),)


class SmartMoneySignalRecord(Base):
    """Smart money signal history (PRD-42)."""

    __tablename__ = "smart_money_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    signal = Column(String(16))
    confidence = Column(Float)
    block_ratio = Column(Float)
    institutional_net_flow = Column(Float)
    institutional_buy_pct = Column(Float)
    date = Column(Date)
    computed_at = Column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# PRD-66: Trade Journal Dashboard
# ---------------------------------------------------------------------------


class TradeDirection(enum.Enum):
    """Trade direction."""
    LONG = "long"
    SHORT = "short"


class TradeType(enum.Enum):
    """Trade type by duration."""
    SCALP = "scalp"
    DAY = "day"
    SWING = "swing"
    POSITION = "position"


class EmotionalState(enum.Enum):
    """Emotional state for trade journaling."""
    CALM = "calm"
    CONFIDENT = "confident"
    ANXIOUS = "anxious"
    FOMO = "fomo"
    GREEDY = "greedy"
    FEARFUL = "fearful"
    FRUSTRATED = "frustrated"
    EUPHORIC = "euphoric"
    REVENGE = "revenge"


class TradingStrategy(Base):
    """User-defined trading strategies with rules."""

    __tablename__ = "trading_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    entry_rules = Column(Text)  # JSON array of rules
    exit_rules = Column(Text)  # JSON array of rules
    max_risk_per_trade = Column(Float)
    target_risk_reward = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class TradeSetup(Base):
    """Categorized trade setups/patterns."""

    __tablename__ = "trade_setups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50))  # breakout, pullback, reversal, etc.
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class JournalEntry(Base):
    """Extended trade journal entry with emotions, setup, notes."""

    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(30), nullable=False, index=True)

    # Direction & Type
    direction = Column(String(20), nullable=False)  # long, short
    trade_type = Column(String(30))  # swing, day, scalp, position

    # Entry
    entry_date = Column(DateTime, nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    entry_quantity = Column(Float, nullable=False)
    entry_reason = Column(Text)

    # Exit
    exit_date = Column(DateTime)
    exit_price = Column(Float)
    exit_reason = Column(Text)

    # P&L
    realized_pnl = Column(Float)
    realized_pnl_pct = Column(Float)
    fees = Column(Float)

    # Setup & Strategy
    setup_id = Column(String(50), index=True)
    strategy_id = Column(String(50), index=True)
    timeframe = Column(String(20))  # 1m, 5m, 1h, 1d

    # Tags
    tags = Column(Text)  # JSON array

    # Notes
    notes = Column(Text)
    lessons_learned = Column(Text)

    # Emotions
    pre_trade_emotion = Column(String(30))
    during_trade_emotion = Column(String(30))
    post_trade_emotion = Column(String(30))

    # Screenshots
    screenshots = Column(Text)  # JSON array of paths/URLs

    # Risk management
    initial_stop = Column(Float)
    initial_target = Column(Float)
    risk_reward_planned = Column(Float)
    risk_reward_actual = Column(Float)

    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class DailyReview(Base):
    """Daily trading review/self-assessment."""

    __tablename__ = "daily_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_date = Column(Date, unique=True, nullable=False, index=True)

    # Summary
    trades_taken = Column(Integer)
    gross_pnl = Column(Float)
    net_pnl = Column(Float)
    win_rate = Column(Float)

    # Self-assessment
    followed_plan = Column(Boolean)
    mistakes_made = Column(Text)  # JSON array
    did_well = Column(Text)  # JSON array

    # Goals
    tomorrow_focus = Column(Text)

    # Rating
    overall_rating = Column(Integer)  # 1-5

    # Notes
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class PeriodicReview(Base):
    """Weekly/monthly trading reviews."""

    __tablename__ = "periodic_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_type = Column(String(20), nullable=False)  # weekly, monthly
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Performance
    total_trades = Column(Integer)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    net_pnl = Column(Float)
    max_drawdown = Column(Float)

    # Analysis
    best_setups = Column(Text)  # JSON
    worst_setups = Column(Text)  # JSON
    key_learnings = Column(Text)  # JSON array
    action_items = Column(Text)  # JSON array
    strategy_adjustments = Column(Text)

    # Goals
    goals_achieved = Column(Text)  # JSON array
    next_period_goals = Column(Text)  # JSON array
    created_at = Column(DateTime, server_default=func.now())
