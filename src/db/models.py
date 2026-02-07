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
    ForeignKey,
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


# ---------------------------------------------------------------------------
# PRD-67: User Authentication & RBAC
# ---------------------------------------------------------------------------


class UserRoleType(enum.Enum):
    """User role types."""
    VIEWER = "viewer"
    TRADER = "trader"
    MANAGER = "manager"
    ADMIN = "admin"
    API = "api"


class SubscriptionType(enum.Enum):
    """Subscription tier types."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    """User account for authentication."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    name = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default="trader")
    subscription = Column(String(20), nullable=False, default="free")

    # Profile
    avatar_url = Column(String(500), nullable=True)
    timezone = Column(String(50), default="UTC")
    preferences = Column(Text)  # JSON

    # OAuth IDs
    google_id = Column(String(100), nullable=True, index=True)
    github_id = Column(String(100), nullable=True, index=True)
    apple_id = Column(String(100), nullable=True)

    # 2FA
    totp_secret = Column(String(100), nullable=True)
    totp_enabled = Column(Boolean, default=False)

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("UserAPIKey", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    """User session for JWT token management."""

    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_token_hash = Column(String(64), nullable=False)
    refresh_token_hash = Column(String(64), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_info = Column(Text)  # JSON
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, nullable=True)

    # Relationship
    user = relationship("User", back_populates="sessions")


class UserAPIKey(Base):
    """API key for programmatic access."""

    __tablename__ = "user_api_keys"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(64), nullable=False)
    key_prefix = Column(String(12), nullable=False, index=True)
    scopes = Column(Text)  # JSON array
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    request_count = Column(Integer, default=0)

    # Relationship
    user = relationship("User", back_populates="api_keys")


class UserAuditLog(Base):
    """Audit log for user actions."""

    __tablename__ = "user_audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    user_id = Column(String(36), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text)  # JSON
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    status = Column(String(20), default="success")
    error_message = Column(Text, nullable=True)


class OAuthState(Base):
    """OAuth state token for OAuth flow."""

    __tablename__ = "oauth_states"

    id = Column(String(36), primary_key=True)
    state = Column(String(64), unique=True, nullable=False)
    provider = Column(String(20), nullable=False)
    redirect_uri = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)


class RateLimitRecord(Base):
    """Rate limiting record."""

    __tablename__ = "rate_limit_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(255), nullable=False, index=True)
    count = Column(Integer, default=1)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)


class PasswordResetToken(Base):
    """Password reset token."""

    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    token_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)


class EmailVerificationToken(Base):
    """Email verification token."""

    __tablename__ = "email_verification_tokens"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    token_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)


# ---------------------------------------------------------------------------
# PRD-68: Multi-Account Management
# ---------------------------------------------------------------------------


class AccountTypeEnum(enum.Enum):
    """Account types."""
    INDIVIDUAL = "individual"
    IRA_TRADITIONAL = "ira_traditional"
    IRA_ROTH = "ira_roth"
    JOINT = "joint"
    TRUST = "trust"
    CORPORATE = "corporate"
    PAPER = "paper"


class TaxStatusEnum(enum.Enum):
    """Account tax status."""
    TAXABLE = "taxable"
    TAX_DEFERRED = "tax_deferred"
    TAX_FREE = "tax_free"


class BrokerEnum(enum.Enum):
    """Supported brokers."""
    PAPER = "paper"
    ALPACA = "alpaca"
    IBKR = "ibkr"


class TradingAccount(Base):
    """Trading account for multi-account management."""

    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True)
    owner_id = Column(String(36), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    account_type = Column(String(30), nullable=False)
    broker = Column(String(30), nullable=False, index=True)
    broker_account_id = Column(String(100), nullable=True)

    # Strategy
    strategy_id = Column(String(36), nullable=True)
    strategy_name = Column(String(100), nullable=True)
    target_allocation = Column(Text)  # JSON

    # Financials
    cash_balance = Column(Float, default=0)
    total_value = Column(Float, default=0)
    cost_basis = Column(Float, default=0)

    # Tax
    tax_status = Column(String(20), nullable=False)

    # Benchmark
    benchmark = Column(String(20), default="SPY")

    # Dates
    inception_date = Column(Date, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)

    # Permissions
    permissions = Column(Text)  # JSON array of user IDs

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    snapshots = relationship("AccountSnapshotRecord", back_populates="account", cascade="all, delete-orphan")
    positions = relationship("AccountPositionRecord", back_populates="account", cascade="all, delete-orphan")


class AccountSnapshotRecord(Base):
    """Daily account snapshot for performance tracking."""

    __tablename__ = "account_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False)

    # Values
    total_value = Column(Float, nullable=False)
    cash_balance = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False)

    # P&L
    day_pnl = Column(Float, nullable=True)
    day_return_pct = Column(Float, nullable=True)
    total_pnl = Column(Float, nullable=True)
    total_return_pct = Column(Float, nullable=True)

    # Positions snapshot
    positions = Column(Text)  # JSON

    # Metrics
    num_positions = Column(Integer, nullable=True)
    portfolio_beta = Column(Float, nullable=True)
    portfolio_volatility = Column(Float, nullable=True)

    # Timestamp
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    account = relationship("TradingAccount", back_populates="snapshots")

    __table_args__ = (
        Index("ix_account_snapshots_account_date", "account_id", "snapshot_date"),
    )


class AccountPositionRecord(Base):
    """Current position in an account."""

    __tablename__ = "account_positions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    avg_cost = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    market_value = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    unrealized_pnl_pct = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)  # % of portfolio
    asset_class = Column(String(30), nullable=True)
    sector = Column(String(50), nullable=True)
    updated_at = Column(DateTime, server_default=func.now())

    # Relationship
    account = relationship("TradingAccount", back_populates="positions")


class AccountLink(Base):
    """Link between accounts for household view."""

    __tablename__ = "account_links"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    primary_user_id = Column(String(36), nullable=False)
    linked_account_id = Column(String(36), nullable=False)
    relationship = Column(String(30), nullable=True)  # spouse, child, trust
    access_level = Column(String(20), nullable=False)  # view, trade, manage
    created_at = Column(DateTime, server_default=func.now())


class RebalancingHistory(Base):
    """History of account rebalancing operations."""

    __tablename__ = "rebalancing_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(36), nullable=False, index=True)
    rebalance_date = Column(DateTime, nullable=False)
    rebalance_type = Column(String(30), nullable=True)  # threshold, scheduled, manual
    pre_allocation = Column(Text)  # JSON
    post_allocation = Column(Text)  # JSON
    trades_executed = Column(Text)  # JSON
    total_traded_value = Column(Float, nullable=True)
    status = Column(String(20), nullable=False)  # completed, partial, failed
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# PRD-69: Team Workspaces
# ---------------------------------------------------------------------------


class WorkspaceRoleEnum(enum.Enum):
    """Workspace member roles."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class WorkspaceRecord(Base):
    """Team workspace for collaboration."""

    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String(36), nullable=False, index=True)

    # Settings
    settings = Column(Text)  # JSON
    logo_url = Column(String(500), nullable=True)

    # Stats (cached)
    member_count = Column(Integer, default=1)
    strategy_count = Column(Integer, default=0)
    total_aum = Column(Float, default=0)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    members = relationship("WorkspaceMemberRecord", back_populates="workspace", cascade="all, delete-orphan")
    strategies = relationship("SharedStrategyRecord", back_populates="workspace", cascade="all, delete-orphan")
    activities = relationship("WorkspaceActivityRecord", back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMemberRecord(Base):
    """Workspace membership."""

    __tablename__ = "workspace_members"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # owner, admin, member, viewer
    invited_by = Column(String(36), nullable=True)
    joined_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Relationship
    workspace = relationship("WorkspaceRecord", back_populates="members")

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )


class SharedStrategyRecord(Base):
    """Strategy shared within a workspace."""

    __tablename__ = "shared_strategies"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id = Column(String(36), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    config = Column(Text)  # JSON

    # Performance (cached)
    ytd_return = Column(Float, default=0)
    sharpe_ratio = Column(Float, default=0)
    total_return = Column(Float, default=0)
    max_drawdown = Column(Float, default=0)
    win_rate = Column(Float, default=0)

    # Usage
    use_count = Column(Integer, default=0)
    fork_count = Column(Integer, default=0)

    # Status
    is_public = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationship
    workspace = relationship("WorkspaceRecord", back_populates="strategies")


class WorkspaceActivityRecord(Base):
    """Activity feed item for a workspace."""

    __tablename__ = "workspace_activities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    user_name = Column(String(100), nullable=True)
    action = Column(String(50), nullable=False)  # created_strategy, executed_trade, etc.
    resource_type = Column(String(30), nullable=True)  # strategy, trade, account
    resource_id = Column(String(36), nullable=True)
    resource_name = Column(String(100), nullable=True)
    details = Column(Text)  # JSON
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    # Relationship
    workspace = relationship("WorkspaceRecord", back_populates="activities")


class WorkspaceWatchlistRecord(Base):
    """Shared watchlist within a workspace."""

    __tablename__ = "workspace_watchlists"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    creator_id = Column(String(36), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    symbols = Column(Text)  # JSON array
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class WorkspaceResearchNoteRecord(Base):
    """Research note shared within a workspace."""

    __tablename__ = "workspace_research_notes"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    author_id = Column(String(36), nullable=True)
    author_name = Column(String(100), nullable=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    symbols = Column(Text)  # JSON array
    tags = Column(Text)  # JSON array
    is_pinned = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


# ---------------------------------------------------------------------------
# PRD-70: Professional Reporting
# ---------------------------------------------------------------------------


class ReportTypeEnum(enum.Enum):
    """Report types."""
    PERFORMANCE = "performance"
    HOLDINGS = "holdings"
    ATTRIBUTION = "attribution"
    TRADE_ACTIVITY = "trade_activity"
    RISK = "risk"
    CUSTOM = "custom"


class ReportFormatEnum(enum.Enum):
    """Report output formats."""
    PDF = "pdf"
    EXCEL = "excel"
    HTML = "html"
    CSV = "csv"


class ReportFrequencyEnum(enum.Enum):
    """Report scheduling frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ReportStatusEnum(enum.Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportTemplateRecord(Base):
    """Report template configuration."""

    __tablename__ = "report_templates"

    id = Column(String(36), primary_key=True)
    owner_id = Column(String(36), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    report_type = Column(String(30), nullable=False)

    # Template configuration
    sections = Column(Text)  # JSON
    metrics = Column(Text)  # JSON
    charts = Column(Text)  # JSON
    filters = Column(Text)  # JSON

    # Branding
    logo_url = Column(String(500), nullable=True)
    company_name = Column(String(100), nullable=True)
    primary_color = Column(String(20), nullable=True)
    footer_text = Column(Text, nullable=True)

    # Status
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    sections_rel = relationship("ReportSectionRecord", back_populates="template", cascade="all, delete-orphan")


class GeneratedReportRecord(Base):
    """Generated report instance."""

    __tablename__ = "generated_reports"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), nullable=True, index=True)
    template_id = Column(String(36), nullable=True)

    # Report info
    title = Column(String(200), nullable=False)
    report_type = Column(String(30), nullable=False)
    format = Column(String(10), nullable=False)

    # Period
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    period_type = Column(String(20), nullable=True)

    # Content
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=True)

    # Metadata
    parameters = Column(Text)  # JSON
    metrics_snapshot = Column(Text)  # JSON

    # Status
    status = Column(String(20), nullable=False)
    error_message = Column(Text, nullable=True)
    generation_time_ms = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), index=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    distributions = relationship("ReportDistributionRecord", back_populates="report", cascade="all, delete-orphan")


class ScheduledReportRecord(Base):
    """Scheduled report configuration."""

    __tablename__ = "scheduled_reports"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), nullable=True)
    template_id = Column(String(36), nullable=True)

    # Schedule info
    name = Column(String(100), nullable=False)
    frequency = Column(String(20), nullable=False)
    day_of_week = Column(Integer, nullable=True)
    day_of_month = Column(Integer, nullable=True)
    time_of_day = Column(String(10), nullable=True)
    timezone = Column(String(50), default="UTC")

    # Report config
    report_type = Column(String(30), nullable=False)
    format = Column(String(10), nullable=False)
    parameters = Column(Text)  # JSON

    # Distribution
    recipients = Column(Text)  # JSON array
    send_empty = Column(Boolean, default=False)

    # Status
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    run_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ReportDistributionRecord(Base):
    """Report email distribution log."""

    __tablename__ = "report_distributions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    report_id = Column(String(36), ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id = Column(String(36), nullable=True)

    # Recipient info
    recipient_email = Column(String(200), nullable=False)
    recipient_name = Column(String(100), nullable=True)

    # Status
    status = Column(String(20), nullable=False)  # pending, sent, delivered, failed, bounced
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Tracking
    message_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    report = relationship("GeneratedReportRecord", back_populates="distributions")


class ReportSectionRecord(Base):
    """Custom section within a report template."""

    __tablename__ = "report_sections"

    id = Column(String(36), primary_key=True)
    template_id = Column(String(36), ForeignKey("report_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    section_type = Column(String(30), nullable=False)  # summary, holdings, trades, chart, text, metrics
    order_index = Column(Integer, nullable=False)
    config = Column(Text)  # JSON
    is_visible = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    template = relationship("ReportTemplateRecord", back_populates="sections_rel")


class ReportBrandingRecord(Base):
    """White-label branding configuration."""

    __tablename__ = "report_branding"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)

    # Branding
    company_name = Column(String(100), nullable=False)
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(20), default="#007bff")
    secondary_color = Column(String(20), default="#6c757d")
    accent_color = Column(String(20), default="#28a745")

    # Text
    header_text = Column(Text, nullable=True)
    footer_text = Column(Text, nullable=True)
    disclaimer = Column(Text, nullable=True)

    # Contact
    contact_email = Column(String(200), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    website = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_report_branding_user"),
    )


# ---------------------------------------------------------------------------
# PRD-71: Compliance & Audit
# ---------------------------------------------------------------------------


class ComplianceRuleTypeEnum(enum.Enum):
    """Types of compliance rules."""
    POSITION_LIMIT = "position_limit"
    SECTOR_LIMIT = "sector_limit"
    CONCENTRATION = "concentration"
    RESTRICTED_LIST = "restricted_list"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    TRADING_FREQUENCY = "trading_frequency"
    CUSTOM = "custom"


class ComplianceSeverityEnum(enum.Enum):
    """Compliance violation severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RestrictionTypeEnum(enum.Enum):
    """Types of trading restrictions."""
    ALL = "all"
    BUY_ONLY = "buy_only"
    SELL_ONLY = "sell_only"


class AuditActionEnum(enum.Enum):
    """Audit log action types."""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    TOTP_ENABLE = "totp_enable"
    TOTP_DISABLE = "totp_disable"
    # Trading
    ORDER_SUBMIT = "order_submit"
    ORDER_CANCEL = "order_cancel"
    ORDER_FILL = "order_fill"
    REBALANCE = "rebalance"
    # Account
    ACCOUNT_CREATE = "account_create"
    ACCOUNT_UPDATE = "account_update"
    ACCOUNT_DELETE = "account_delete"
    # Strategy
    STRATEGY_CREATE = "strategy_create"
    STRATEGY_UPDATE = "strategy_update"
    STRATEGY_DELETE = "strategy_delete"
    # Compliance
    COMPLIANCE_VIOLATION = "compliance_violation"
    RESTRICTED_TRADE = "restricted_trade"
    RULE_CREATE = "rule_create"
    RULE_UPDATE = "rule_update"
    # Admin
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    ROLE_CHANGE = "role_change"
    SETTING_CHANGE = "setting_change"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"


class ComplianceRuleRecord(Base):
    """Compliance rule definition."""

    __tablename__ = "compliance_rules"

    id = Column(String(36), primary_key=True)
    owner_id = Column(String(36), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    rule_type = Column(String(30), nullable=False, index=True)

    # Rule parameters
    parameters = Column(Text)  # JSON
    severity = Column(String(20), default="warning")

    # Scope
    applies_to_accounts = Column(Text)  # JSON array
    applies_to_symbols = Column(Text)  # JSON array

    # Status
    is_active = Column(Boolean, default=True)
    is_blocking = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    violations = relationship("ComplianceViolationRecord", back_populates="rule")


class RestrictedSecurityRecord(Base):
    """Restricted security entry."""

    __tablename__ = "restricted_securities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    owner_id = Column(String(36), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    reason = Column(String(100), nullable=False)
    restriction_type = Column(String(20), nullable=False)

    # Details
    notes = Column(Text, nullable=True)
    added_by = Column(String(36), nullable=True)
    added_by_name = Column(String(100), nullable=True)

    # Validity period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("owner_id", "symbol", name="uq_restricted_security_active"),
    )


class ComplianceViolationRecord(Base):
    """Compliance violation record."""

    __tablename__ = "compliance_violations"

    id = Column(String(36), primary_key=True)
    rule_id = Column(String(36), ForeignKey("compliance_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), nullable=True)

    # Violation details
    rule_name = Column(String(100), nullable=False)
    violation_type = Column(String(30), nullable=False)
    severity = Column(String(20), nullable=False)
    details = Column(Text)  # JSON

    # Context
    symbol = Column(String(20), nullable=True)
    action = Column(String(20), nullable=True)
    quantity = Column(Integer, nullable=True)
    price = Column(Float, nullable=True)

    # Resolution
    is_resolved = Column(Boolean, default=False, index=True)
    resolved_by = Column(String(36), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Was trade blocked?
    trade_blocked = Column(Boolean, default=False)

    # Timestamps
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    # Relationship
    rule = relationship("ComplianceRuleRecord", back_populates="violations")


class AuditLogRecord(Base):
    """Comprehensive audit log entry."""

    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=True, index=True)
    user_email = Column(String(200), nullable=True)

    # Action
    action = Column(String(50), nullable=False, index=True)
    action_category = Column(String(30), nullable=True)

    # Resource
    resource_type = Column(String(30), nullable=True)
    resource_id = Column(String(36), nullable=True)

    # Details
    details = Column(Text)  # JSON
    changes = Column(Text)  # JSON - before/after

    # Status
    status = Column(String(20), nullable=False)
    error_message = Column(Text, nullable=True)

    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(36), nullable=True)

    # Timestamps
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )


class PreTradeCheckRecord(Base):
    """Pre-trade compliance check result."""

    __tablename__ = "pretrade_checks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), nullable=True)
    order_id = Column(String(36), nullable=True)

    # Trade details
    symbol = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=True)

    # Results
    checks_run = Column(Text)  # JSON array
    passed = Column(Boolean, nullable=False)
    blocking_violations = Column(Integer, default=0)
    warnings = Column(Integer, default=0)

    # Outcome
    trade_allowed = Column(Boolean, nullable=False)
    override_by = Column(String(36), nullable=True)
    override_reason = Column(Text, nullable=True)

    # Timestamps
    timestamp = Column(DateTime, server_default=func.now(), index=True)


class ComplianceReportRecord(Base):
    """Regulatory compliance report."""

    __tablename__ = "compliance_reports"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    report_type = Column(String(30), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Content
    title = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=True)
    data = Column(Text)  # JSON

    # Status
    status = Column(String(20), nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    submitted_to = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


# =============================================================================
# PRD-58: AI Trading Copilot
# =============================================================================


class CopilotSessionRecord(Base):
    """AI Copilot conversation session."""

    __tablename__ = "copilot_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    session_type = Column(String(30), nullable=True)

    # Context
    context = Column(Text)  # JSON
    active_symbol = Column(String(20), nullable=True)

    # Stats
    message_count = Column(Integer, default=0)
    ideas_generated = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    started_at = Column(DateTime, server_default=func.now())
    last_activity_at = Column(DateTime, server_default=func.now())

    # Relationships
    messages = relationship("CopilotMessageRecord", back_populates="session", cascade="all, delete-orphan")


class CopilotMessageRecord(Base):
    """AI Copilot conversation message."""

    __tablename__ = "copilot_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("copilot_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(String(36), nullable=False)

    # Content
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)

    # Metadata
    tokens_used = Column(Integer, nullable=True)
    model = Column(String(50), nullable=True)
    extracted_symbols = Column(Text)  # JSON
    extracted_actions = Column(Text)  # JSON
    confidence_score = Column(Float, nullable=True)

    # Feedback
    user_rating = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)

    # Timestamp
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    # Relationship
    session = relationship("CopilotSessionRecord", back_populates="messages")


class CopilotPreferencesRecord(Base):
    """User preferences for AI Copilot."""

    __tablename__ = "copilot_preferences"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Risk & Style
    risk_tolerance = Column(String(20), default="moderate")
    investment_style = Column(String(30), default="balanced")
    time_horizon = Column(String(20), default="medium")

    # Sectors
    preferred_sectors = Column(Text)  # JSON
    excluded_sectors = Column(Text)  # JSON

    # Response style
    response_style = Column(String(20), default="balanced")
    include_technicals = Column(Boolean, default=True)
    include_fundamentals = Column(Boolean, default=True)
    include_sentiment = Column(Boolean, default=True)

    # Constraints
    max_position_size_pct = Column(Float, nullable=True)
    min_market_cap = Column(BigInteger, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class CopilotSavedIdeaRecord(Base):
    """Saved trade idea from AI Copilot."""

    __tablename__ = "copilot_saved_ideas"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), nullable=True)
    message_id = Column(String(36), nullable=True)

    # Idea details
    symbol = Column(String(20), nullable=False, index=True)
    action = Column(String(10), nullable=False)
    confidence = Column(Float, nullable=True)
    rationale = Column(Text, nullable=True)

    # Targets
    entry_price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    time_horizon = Column(String(20), nullable=True)

    # Tracking
    status = Column(String(20), default="active", index=True)
    executed_at = Column(DateTime, nullable=True)
    execution_price = Column(Float, nullable=True)
    outcome = Column(String(20), nullable=True)
    outcome_pct = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)


# =============================================================================
# PRD-59: Real-time WebSocket API
# =============================================================================


class ConnectionStatusEnum(enum.Enum):
    """WebSocket connection status."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


class WebSocketConnectionRecord(Base):
    """WebSocket connection state."""

    __tablename__ = "websocket_connections"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False)

    # Connection info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    client_version = Column(String(50), nullable=True)

    # Metrics
    messages_sent = Column(BigInteger, default=0)
    messages_received = Column(BigInteger, default=0)
    bytes_sent = Column(BigInteger, default=0)
    bytes_received = Column(BigInteger, default=0)

    # Timestamps
    connected_at = Column(DateTime, server_default=func.now())
    last_heartbeat = Column(DateTime, server_default=func.now())
    disconnected_at = Column(DateTime, nullable=True)

    # Relationships
    subscriptions = relationship("WebSocketSubscriptionRecord", back_populates="connection", cascade="all, delete-orphan")


class WebSocketSubscriptionRecord(Base):
    """WebSocket channel subscription."""

    __tablename__ = "websocket_subscriptions"

    id = Column(String(36), primary_key=True)
    connection_id = Column(String(36), ForeignKey("websocket_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(30), nullable=False, index=True)

    # Config
    symbols = Column(Text)  # JSON array
    throttle_ms = Column(Integer, default=100)
    filters = Column(Text)  # JSON

    # Status
    is_active = Column(Boolean, default=True)

    # Metrics
    messages_delivered = Column(BigInteger, default=0)
    last_message_at = Column(DateTime, nullable=True)

    # Timestamps
    subscribed_at = Column(DateTime, server_default=func.now())
    unsubscribed_at = Column(DateTime, nullable=True)

    # Relationship
    connection = relationship("WebSocketConnectionRecord", back_populates="subscriptions")


class WebSocketMetricsRecord(Base):
    """Aggregated WebSocket metrics for monitoring."""

    __tablename__ = "websocket_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    # Connection stats
    active_connections = Column(Integer, default=0)
    total_subscriptions = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)

    # Message stats
    messages_per_second = Column(Float, default=0)
    bytes_per_second = Column(Float, default=0)
    avg_latency_ms = Column(Float, default=0)
    p99_latency_ms = Column(Float, default=0)

    # Channel breakdown
    channel_stats = Column(Text)  # JSON

    # Errors
    error_count = Column(Integer, default=0)
    reconnection_count = Column(Integer, default=0)


class WebSocketRateLimitRecord(Base):
    """Rate limiting for WebSocket connections."""

    __tablename__ = "websocket_rate_limits"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    connection_id = Column(String(36), nullable=True)

    # Limits
    limit_type = Column(String(30), nullable=False)  # messages, subscriptions, symbols
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    count = Column(Integer, default=0)
    limit_value = Column(Integer, nullable=False)

    # Violation tracking
    violations = Column(Integer, default=0)
    last_violation_at = Column(DateTime, nullable=True)
    blocked_until = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_ws_rate_limits_lookup", "user_id", "limit_type", "window_start"),
    )


# =============================================================================
# PRD-60: Mobile Push Notifications
# =============================================================================


class NotificationDeviceRecord(Base):
    """Device registration for push notifications."""

    __tablename__ = "notification_devices"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_token = Column(String(500), nullable=False)
    platform = Column(String(20), nullable=False)  # ios, android, web
    device_name = Column(String(100), nullable=True)
    device_model = Column(String(100), nullable=True)
    app_version = Column(String(20), nullable=True)
    os_version = Column(String(20), nullable=True)
    push_token_type = Column(String(20), nullable=False)  # fcm, apns, web_push
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True)
    token_refreshed_at = Column(DateTime, nullable=True)


class NotificationPreferenceRecord(Base):
    """User notification preferences."""

    __tablename__ = "notification_preferences"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(30), nullable=False)
    enabled = Column(Boolean, default=True)
    priority = Column(String(20), default="normal")
    channels = Column(Text)  # JSON array
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(10), nullable=True)
    quiet_hours_end = Column(String(10), nullable=True)
    timezone = Column(String(50), default="UTC")
    max_per_hour = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_notification_prefs_user_category"),
    )


class NotificationQueueRecord(Base):
    """Queued notification for delivery."""

    __tablename__ = "notification_queue"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    device_id = Column(String(36), nullable=True)
    category = Column(String(30), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(Text, nullable=True)  # JSON
    image_url = Column(String(500), nullable=True)
    action_url = Column(String(500), nullable=True)
    priority = Column(String(20), nullable=False, default="normal")
    status = Column(String(20), nullable=False, default="pending", index=True)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class NotificationHistoryRecord(Base):
    """Notification delivery history."""

    __tablename__ = "notification_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    notification_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    device_id = Column(String(36), nullable=True)
    category = Column(String(30), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    platform = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
