"""API Request/Response Models.

Pydantic schemas for all API endpoints.
"""

from datetime import date, datetime
from typing import Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


# ─── Common ──────────────────────────────────────────────────────────────


class PaginationParams(BaseModel):
    """Cursor-based pagination."""

    cursor: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    data: list[Any]
    next_cursor: Optional[str] = None
    has_more: bool = False
    total: Optional[int] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    code: str
    detail: Optional[str] = None
    request_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Market Data ─────────────────────────────────────────────────────────


class QuoteResponse(BaseModel):
    """Real-time quote."""

    symbol: str
    price: float
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    prev_close: float = 0.0
    market_cap: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OHLCVBar(BaseModel):
    """Single OHLCV bar."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None


class OHLCVResponse(BaseModel):
    """Historical OHLCV response."""

    symbol: str
    bar_type: str = "1d"
    bars: list[OHLCVBar]
    count: int = 0


class FundamentalsResponse(BaseModel):
    """Fundamental data response."""

    symbol: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: float = 0.0
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    as_of: Optional[date] = None


# ─── Factor Scores ──────────────────────────────────────────────────────


class FactorScoreResponse(BaseModel):
    """Factor scores for a symbol."""

    symbol: str
    score_date: date = Field(default_factory=date.today)
    value: Optional[float] = None
    momentum: Optional[float] = None
    quality: Optional[float] = None
    growth: Optional[float] = None
    volatility: Optional[float] = None
    sentiment: Optional[float] = None
    composite: Optional[float] = None
    regime: Optional[str] = None


class ScreenRequest(BaseModel):
    """Factor screening request."""

    factor: str = "composite"
    top: int = Field(default=20, ge=1, le=100)
    min_market_cap: Optional[float] = None
    sector: Optional[str] = None
    universe: str = "sp500"


class ScreenResult(BaseModel):
    """Single screening result."""

    rank: int
    symbol: str
    score: float
    name: str = ""
    sector: str = ""
    market_cap: float = 0.0


class ScreenResponse(BaseModel):
    """Factor screening response."""

    factor: str
    results: list[ScreenResult]
    count: int
    universe: str = "sp500"
    as_of: date = Field(default_factory=date.today)


class RegimeResponse(BaseModel):
    """Market regime response."""

    regime: str
    confidence: float = 0.0
    features: dict[str, float] = Field(default_factory=dict)
    as_of: date = Field(default_factory=date.today)


# ─── Portfolio ───────────────────────────────────────────────────────────


class PositionResponse(BaseModel):
    """Portfolio position."""

    symbol: str
    qty: int
    avg_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    weight: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    sector: str = ""


class PortfolioResponse(BaseModel):
    """Portfolio summary."""

    total_value: float
    cash: float
    positions_value: float
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    total_return: float = 0.0
    positions: list[PositionResponse]
    n_positions: int = 0
    as_of: datetime = Field(default_factory=datetime.utcnow)


class OptimizeRequest(BaseModel):
    """Portfolio optimization request."""

    method: str = "max_sharpe"
    symbols: Optional[list[str]] = None
    max_weight: float = Field(default=0.10, ge=0.01, le=1.0)
    max_positions: int = Field(default=20, ge=1, le=100)
    risk_target: Optional[float] = None


class OptimizeResponse(BaseModel):
    """Optimization result."""

    method: str
    weights: dict[str, float]
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    converged: bool = True


class RiskResponse(BaseModel):
    """Portfolio risk metrics."""

    volatility: float = 0.0
    beta: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    as_of: datetime = Field(default_factory=datetime.utcnow)


# ─── Trading ─────────────────────────────────────────────────────────────


class OrderSideEnum(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderTypeEnum(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatusEnum(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class CreateOrderRequest(BaseModel):
    """Order creation request."""

    symbol: str
    qty: int = Field(ge=1)
    side: OrderSideEnum
    order_type: OrderTypeEnum = OrderTypeEnum.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"
    client_order_id: Optional[str] = None


class OrderResponse(BaseModel):
    """Order response."""

    order_id: str
    client_order_id: Optional[str] = None
    symbol: str
    side: OrderSideEnum
    qty: int
    filled_qty: int = 0
    order_type: OrderTypeEnum
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatusEnum = OrderStatusEnum.PENDING
    avg_fill_price: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None


class TradeResponse(BaseModel):
    """Trade history entry."""

    trade_id: str
    symbol: str
    side: str
    qty: int
    price: float
    notional: float = 0.0
    commission: float = 0.0
    pnl: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── AI & Predictions ───────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """AI chat request."""

    message: str = Field(min_length=1, max_length=4096)
    context: Optional[str] = None
    model: str = "default"


class ChatResponse(BaseModel):
    """AI chat response."""

    response: str
    sources: list[str] = Field(default_factory=list)
    symbols_mentioned: list[str] = Field(default_factory=list)


class PredictionResponse(BaseModel):
    """ML prediction response."""

    symbol: str
    predicted_return: float = 0.0
    confidence: float = 0.0
    direction: str = "neutral"
    features: dict[str, float] = Field(default_factory=dict)
    model_version: str = ""
    as_of: datetime = Field(default_factory=datetime.utcnow)


class SentimentResponse(BaseModel):
    """Sentiment analysis response."""

    symbol: str
    overall: float = 0.0
    news_sentiment: float = 0.0
    social_sentiment: float = 0.0
    analyst_sentiment: float = 0.0
    insider_sentiment: float = 0.0
    articles_count: int = 0
    as_of: datetime = Field(default_factory=datetime.utcnow)


# ─── Options ─────────────────────────────────────────────────────────────


class OptionContract(BaseModel):
    """Single option contract."""

    symbol: str
    expiration: date
    strike: float
    option_type: str  # call or put
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_vol: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0


class OptionsChainResponse(BaseModel):
    """Options chain response."""

    symbol: str
    underlying_price: float
    expirations: list[date]
    contracts: list[OptionContract]
    as_of: datetime = Field(default_factory=datetime.utcnow)


class OptionsAnalyzeRequest(BaseModel):
    """Options strategy analysis request."""

    symbol: str
    strategy: str  # covered_call, straddle, iron_condor, etc.
    expiration: date
    strikes: list[float] = Field(default_factory=list)


class OptionsAnalyzeResponse(BaseModel):
    """Options strategy analysis result."""

    strategy: str
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven: list[float] = Field(default_factory=list)
    pop: float = 0.0  # probability of profit
    expected_return: float = 0.0
    greeks: dict[str, float] = Field(default_factory=dict)


# ─── Backtesting ─────────────────────────────────────────────────────────


class BacktestRequest(BaseModel):
    """Backtest request."""

    strategy: str
    start_date: date
    end_date: date
    initial_capital: float = 100_000
    symbols: list[str] = Field(default_factory=list)
    rebalance_frequency: str = "monthly"
    params: dict[str, Any] = Field(default_factory=dict)


class BacktestResponse(BaseModel):
    """Backtest result summary."""

    backtest_id: str
    strategy: str
    total_return: float = 0.0
    cagr: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    start_date: date = Field(default_factory=date.today)
    end_date: date = Field(default_factory=date.today)
    status: str = "completed"


# ─── WebSocket ───────────────────────────────────────────────────────────


class WSMessage(BaseModel):
    """WebSocket message."""

    action: str  # subscribe, unsubscribe, heartbeat
    channel: Optional[str] = None
    symbols: list[str] = Field(default_factory=list)
    data: Optional[dict] = None


class WSQuoteUpdate(BaseModel):
    """WebSocket quote update."""

    channel: str = "quotes"
    symbol: str
    price: float
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSAlertUpdate(BaseModel):
    """WebSocket alert."""

    channel: str = "alerts"
    alert_type: str
    severity: str = "normal"
    message: str
    data: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Webhooks ────────────────────────────────────────────────────────────


class WebhookCreateRequest(BaseModel):
    """Webhook registration."""

    url: str
    events: list[str]
    secret: Optional[str] = None
    description: str = ""
    is_active: bool = True


class WebhookResponse(BaseModel):
    """Webhook response."""

    webhook_id: str
    url: str
    events: list[str]
    secret_preview: str = ""  # last 4 chars
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_delivery: Optional[datetime] = None
    delivery_success_rate: float = 1.0


class WebhookDelivery(BaseModel):
    """Webhook delivery record."""

    delivery_id: str
    webhook_id: str
    event: str
    payload: dict
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    success: bool = False
    attempts: int = 0
    next_retry: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── API Keys ────────────────────────────────────────────────────────────


class APIKeyCreateRequest(BaseModel):
    """API key creation."""

    name: str = Field(min_length=1, max_length=128)
    scopes: list[str] = Field(default_factory=lambda: ["read"])
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    """API key response."""

    key_id: str
    name: str
    key: Optional[str] = None  # Only returned on creation
    key_preview: str = ""  # ax_...last4
    scopes: list[str]
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
