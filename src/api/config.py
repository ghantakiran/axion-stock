"""API Configuration.

Settings for the REST API, WebSocket, webhooks, rate limiting, and SDK.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class APITier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class WebSocketChannel(str, Enum):
    QUOTES = "quotes"
    PORTFOLIO = "portfolio"
    ALERTS = "alerts"
    SIGNALS = "signals"
    ORDERS = "orders"


class WebhookEvent(str, Enum):
    ORDER_FILLED = "order.filled"
    ORDER_CANCELLED = "order.cancelled"
    ALERT_RISK = "alert.risk"
    SIGNAL_NEW = "signal.new"
    REBALANCE_DUE = "rebalance.due"
    EARNINGS_UPCOMING = "earnings.upcoming"
    FACTOR_CHANGE = "factor.change"
    DRAWDOWN_WARNING = "drawdown.warning"


# Rate limits per tier
RATE_LIMITS: dict[APITier, dict] = {
    APITier.FREE: {
        "daily_limit": 100,
        "per_minute": 10,
        "burst": 10,
    },
    APITier.PRO: {
        "daily_limit": 1_000,
        "per_minute": 60,
        "burst": 60,
    },
    APITier.ENTERPRISE: {
        "daily_limit": 0,  # unlimited
        "per_minute": 600,
        "burst": 600,
    },
}


@dataclass
class APIConfig:
    """Core API settings."""

    title: str = "Axion API"
    version: str = "1.0.0"
    description: str = "Algorithmic Trading Platform API"
    prefix: str = "/api/v1"
    docs_url: str = "/docs"
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:8501",   # Streamlit dashboard
        "http://localhost:8000",   # API self-reference
        "http://localhost:3000",   # Grafana
    ])
    cors_methods: list[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    cors_headers: list[str] = field(default_factory=lambda: ["*"])
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    api_key_prefix: str = "ax_"
    max_page_size: int = 100
    default_page_size: int = 20


@dataclass
class WebSocketConfig:
    """WebSocket settings."""

    heartbeat_interval: int = 30  # seconds
    max_connections_per_user: int = 5
    max_subscriptions_per_connection: int = 50
    message_rate_limit: int = 100  # per second


@dataclass
class WebhookConfig:
    """Webhook delivery settings."""

    max_webhooks_per_user: int = 10
    delivery_timeout: int = 10  # seconds
    max_retries: int = 3
    retry_delays: list[int] = field(default_factory=lambda: [60, 300, 3600])
    signing_algorithm: str = "sha256"
    payload_max_size: int = 65536


DEFAULT_API_CONFIG = APIConfig()
DEFAULT_WS_CONFIG = WebSocketConfig()
DEFAULT_WEBHOOK_CONFIG = WebhookConfig()
