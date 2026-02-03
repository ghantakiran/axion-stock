"""Cross-Asset Signal Configuration."""

from dataclasses import dataclass
from enum import Enum


class AssetClass(str, Enum):
    """Asset class classification."""
    EQUITY = "equity"
    BOND = "bond"
    COMMODITY = "commodity"
    CURRENCY = "currency"


class CorrelationRegime(str, Enum):
    """Correlation regime between assets."""
    NORMAL = "normal"
    DECOUPLED = "decoupled"
    CRISIS = "crisis"


class SignalDirection(str, Enum):
    """Signal direction."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalStrength(str, Enum):
    """Signal strength classification."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


@dataclass(frozen=True)
class IntermarketConfig:
    """Intermarket analysis configuration."""
    correlation_window: int = 63
    long_window: int = 252
    divergence_threshold: float = 1.5
    crisis_correlation_threshold: float = 0.80
    decoupled_correlation_threshold: float = 0.10


@dataclass(frozen=True)
class LeadLagConfig:
    """Lead-lag detection configuration."""
    max_lag: int = 10
    min_correlation: float = 0.10
    significance_threshold: float = 0.05
    stability_window: int = 126


@dataclass(frozen=True)
class MomentumConfig:
    """Cross-asset momentum configuration."""
    lookback_short: int = 21
    lookback_long: int = 252
    zscore_window: int = 63
    mean_reversion_threshold: float = 2.0
    trend_strength_threshold: float = 0.5


@dataclass(frozen=True)
class SignalConfig:
    """Composite signal configuration."""
    intermarket_weight: float = 0.30
    leadlag_weight: float = 0.25
    momentum_weight: float = 0.30
    mean_reversion_weight: float = 0.15
    min_confidence: float = 0.3
    strong_threshold: float = 0.7
    moderate_threshold: float = 0.4
