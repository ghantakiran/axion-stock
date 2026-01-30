"""Mobile App & Public API.

Comprehensive API layer for the Axion platform including:
- REST API with FastAPI (market data, factors, portfolio, trading, AI, options, backtesting)
- WebSocket real-time streaming (quotes, portfolio, alerts, signals)
- Webhook system for event-driven integrations
- Python SDK for programmatic access
- API key management and rate limiting

Example:
    from src.api import create_app
    app = create_app()

    # Or use the SDK:
    from src.api import AxionClient
    client = AxionClient(api_key="ax_...")
    scores = client.factors.get("AAPL")
"""

from src.api.config import (
    APITier,
    WebSocketChannel,
    WebhookEvent,
    RATE_LIMITS,
    APIConfig,
    WebSocketConfig,
    WebhookConfig,
    DEFAULT_API_CONFIG,
    DEFAULT_WS_CONFIG,
    DEFAULT_WEBHOOK_CONFIG,
)

from src.api.models import (
    PaginationParams,
    PaginatedResponse,
    ErrorResponse,
    HealthResponse,
    QuoteResponse,
    OHLCVResponse,
    OHLCVBar,
    FundamentalsResponse,
    FactorScoreResponse,
    ScreenRequest,
    ScreenResult,
    ScreenResponse,
    RegimeResponse,
    PositionResponse,
    PortfolioResponse,
    OptimizeRequest,
    OptimizeResponse,
    RiskResponse,
    OrderSideEnum,
    OrderTypeEnum,
    OrderStatusEnum,
    CreateOrderRequest,
    OrderResponse,
    TradeResponse,
    ChatRequest,
    ChatResponse,
    PredictionResponse,
    SentimentResponse,
    OptionContract,
    OptionsChainResponse,
    OptionsAnalyzeRequest,
    OptionsAnalyzeResponse,
    BacktestRequest,
    BacktestResponse,
    WSMessage,
    WSQuoteUpdate,
    WSAlertUpdate,
    WebhookCreateRequest,
    WebhookResponse,
    WebhookDelivery,
    APIKeyCreateRequest,
    APIKeyResponse,
)

from src.api.auth import (
    APIKeyManager,
    RateLimiter,
    WebhookSigner,
)

from src.api.websocket import (
    WSConnection,
    WebSocketManager,
)

from src.api.webhooks import (
    Webhook,
    DeliveryRecord,
    WebhookManager,
)

from src.api.sdk import (
    SDKConfig,
    AxionClient,
)

from src.api.app import create_app

__all__ = [
    # Config
    "APITier",
    "WebSocketChannel",
    "WebhookEvent",
    "RATE_LIMITS",
    "APIConfig",
    "WebSocketConfig",
    "WebhookConfig",
    "DEFAULT_API_CONFIG",
    "DEFAULT_WS_CONFIG",
    "DEFAULT_WEBHOOK_CONFIG",
    # Models - Common
    "PaginationParams",
    "PaginatedResponse",
    "ErrorResponse",
    "HealthResponse",
    # Models - Market Data
    "QuoteResponse",
    "OHLCVResponse",
    "OHLCVBar",
    "FundamentalsResponse",
    # Models - Factors
    "FactorScoreResponse",
    "ScreenRequest",
    "ScreenResult",
    "ScreenResponse",
    "RegimeResponse",
    # Models - Portfolio
    "PositionResponse",
    "PortfolioResponse",
    "OptimizeRequest",
    "OptimizeResponse",
    "RiskResponse",
    # Models - Trading
    "OrderSideEnum",
    "OrderTypeEnum",
    "OrderStatusEnum",
    "CreateOrderRequest",
    "OrderResponse",
    "TradeResponse",
    # Models - AI
    "ChatRequest",
    "ChatResponse",
    "PredictionResponse",
    "SentimentResponse",
    # Models - Options
    "OptionContract",
    "OptionsChainResponse",
    "OptionsAnalyzeRequest",
    "OptionsAnalyzeResponse",
    # Models - Backtesting
    "BacktestRequest",
    "BacktestResponse",
    # Models - WebSocket
    "WSMessage",
    "WSQuoteUpdate",
    "WSAlertUpdate",
    # Models - Webhooks
    "WebhookCreateRequest",
    "WebhookResponse",
    "WebhookDelivery",
    # Models - API Keys
    "APIKeyCreateRequest",
    "APIKeyResponse",
    # Auth
    "APIKeyManager",
    "RateLimiter",
    "WebhookSigner",
    # WebSocket
    "WSConnection",
    "WebSocketManager",
    # Webhooks
    "Webhook",
    "DeliveryRecord",
    "WebhookManager",
    # SDK
    "SDKConfig",
    "AxionClient",
    # App
    "create_app",
]
