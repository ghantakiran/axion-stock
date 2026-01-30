"""Alerting & Notifications configuration.

Enums, constants, and configuration dataclasses for the alerting system.
"""

import enum
from dataclasses import dataclass, field


class AlertType(enum.Enum):
    """Types of alerts."""
    PRICE = "price"
    FACTOR = "factor"
    PORTFOLIO = "portfolio"
    TECHNICAL = "technical"
    RISK = "risk"
    VOLUME = "volume"
    SENTIMENT = "sentiment"


class AlertPriority(enum.Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(enum.Enum):
    """Alert lifecycle status."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    SNOOZED = "snoozed"
    DISABLED = "disabled"
    EXPIRED = "expired"


class ComparisonOperator(enum.Enum):
    """Condition comparison operators."""
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NEQ = "!="
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    PCT_CHANGE_GT = "pct_change_gt"
    PCT_CHANGE_LT = "pct_change_lt"


class LogicalOperator(enum.Enum):
    """Logical operators for compound conditions."""
    AND = "and"
    OR = "or"


class ChannelType(enum.Enum):
    """Notification delivery channels."""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    SLACK = "slack"


class DeliveryStatus(enum.Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class DigestFrequency(enum.Enum):
    """Notification digest frequency."""
    IMMEDIATE = "immediate"
    HOURLY = "hourly"
    DAILY = "daily"


# Default cooldown periods by priority (seconds)
DEFAULT_COOLDOWNS: dict[AlertPriority, int] = {
    AlertPriority.LOW: 3600,       # 1 hour
    AlertPriority.MEDIUM: 1800,    # 30 minutes
    AlertPriority.HIGH: 300,       # 5 minutes
    AlertPriority.CRITICAL: 60,    # 1 minute
}

# Max alerts per user
MAX_ALERTS_PER_USER: dict[str, int] = {
    "free": 10,
    "pro": 50,
    "enterprise": 500,
}

# Retry configuration
MAX_DELIVERY_RETRIES = 3
RETRY_BACKOFF_SECONDS = [30, 120, 600]  # 30s, 2m, 10m


# Pre-built alert templates
ALERT_TEMPLATES: dict[str, dict] = {
    "price_breakout": {
        "name": "Price Breakout",
        "description": "Alert when price breaks above a threshold",
        "alert_type": AlertType.PRICE,
        "operator": ComparisonOperator.GT,
        "priority": AlertPriority.MEDIUM,
    },
    "price_breakdown": {
        "name": "Price Breakdown",
        "description": "Alert when price drops below a threshold",
        "alert_type": AlertType.PRICE,
        "operator": ComparisonOperator.LT,
        "priority": AlertPriority.HIGH,
    },
    "rsi_overbought": {
        "name": "RSI Overbought",
        "description": "Alert when RSI exceeds 70",
        "alert_type": AlertType.TECHNICAL,
        "operator": ComparisonOperator.GT,
        "metric": "rsi_14",
        "threshold": 70.0,
        "priority": AlertPriority.MEDIUM,
    },
    "rsi_oversold": {
        "name": "RSI Oversold",
        "description": "Alert when RSI drops below 30",
        "alert_type": AlertType.TECHNICAL,
        "operator": ComparisonOperator.LT,
        "metric": "rsi_14",
        "threshold": 30.0,
        "priority": AlertPriority.MEDIUM,
    },
    "ma_golden_cross": {
        "name": "Golden Cross",
        "description": "50-day MA crosses above 200-day MA",
        "alert_type": AlertType.TECHNICAL,
        "operator": ComparisonOperator.CROSSES_ABOVE,
        "metric": "sma_50_vs_200",
        "threshold": 0.0,
        "priority": AlertPriority.HIGH,
    },
    "ma_death_cross": {
        "name": "Death Cross",
        "description": "50-day MA crosses below 200-day MA",
        "alert_type": AlertType.TECHNICAL,
        "operator": ComparisonOperator.CROSSES_BELOW,
        "metric": "sma_50_vs_200",
        "threshold": 0.0,
        "priority": AlertPriority.HIGH,
    },
    "high_factor_score": {
        "name": "High Factor Score",
        "description": "Alert when composite factor score exceeds threshold",
        "alert_type": AlertType.FACTOR,
        "operator": ComparisonOperator.GT,
        "metric": "composite_score",
        "threshold": 0.80,
        "priority": AlertPriority.MEDIUM,
    },
    "drawdown_warning": {
        "name": "Drawdown Warning",
        "description": "Alert when portfolio drawdown exceeds threshold",
        "alert_type": AlertType.PORTFOLIO,
        "operator": ComparisonOperator.LT,
        "metric": "drawdown_pct",
        "threshold": -0.05,
        "priority": AlertPriority.HIGH,
    },
    "var_breach": {
        "name": "VaR Breach",
        "description": "Alert when portfolio VaR exceeds risk budget",
        "alert_type": AlertType.RISK,
        "operator": ComparisonOperator.GT,
        "metric": "var_95",
        "threshold": 0.02,
        "priority": AlertPriority.CRITICAL,
    },
    "unusual_volume": {
        "name": "Unusual Volume",
        "description": "Alert when volume exceeds 2x 20-day average",
        "alert_type": AlertType.VOLUME,
        "operator": ComparisonOperator.GT,
        "metric": "volume_ratio_20d",
        "threshold": 2.0,
        "priority": AlertPriority.MEDIUM,
    },
    "sentiment_drop": {
        "name": "Sentiment Drop",
        "description": "Alert on significant negative sentiment shift",
        "alert_type": AlertType.SENTIMENT,
        "operator": ComparisonOperator.LT,
        "metric": "sentiment_composite",
        "threshold": -0.5,
        "priority": AlertPriority.HIGH,
    },
}


@dataclass
class EmailConfig:
    """Email delivery configuration."""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    sender_email: str = ""
    sender_name: str = "Axion Alerts"
    username: str = ""
    password: str = ""


@dataclass
class SMSConfig:
    """SMS delivery configuration."""
    provider: str = "twilio"
    account_sid: str = ""
    auth_token: str = ""
    from_number: str = ""


@dataclass
class SlackConfig:
    """Slack delivery configuration."""
    default_webhook_url: str = ""
    bot_token: str = ""


@dataclass
class WebhookConfig:
    """Webhook delivery configuration."""
    signing_secret: str = ""
    timeout_seconds: int = 10
    max_retries: int = MAX_DELIVERY_RETRIES


@dataclass
class QuietHours:
    """Do Not Disturb configuration."""
    enabled: bool = False
    start_hour: int = 22   # 10 PM
    end_hour: int = 7      # 7 AM
    timezone: str = "America/New_York"
    override_critical: bool = True  # Critical alerts bypass quiet hours


@dataclass
class AlertingConfig:
    """Top-level alerting system configuration."""
    email: EmailConfig = field(default_factory=EmailConfig)
    sms: SMSConfig = field(default_factory=SMSConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    webhook: WebhookConfig = field(default_factory=WebhookConfig)
    quiet_hours: QuietHours = field(default_factory=QuietHours)
    max_alerts_per_user: int = 50
    default_cooldown_seconds: int = 1800
    evaluation_interval_seconds: int = 60
    digest_frequency: DigestFrequency = DigestFrequency.IMMEDIATE


DEFAULT_ALERTING_CONFIG = AlertingConfig()
