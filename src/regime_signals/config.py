"""Configuration for Regime-Aware Signals."""

from enum import Enum
from dataclasses import dataclass


class RegimeType(Enum):
    """Market regime types."""
    BULL_TRENDING = "bull_trending"
    BULL_VOLATILE = "bull_volatile"
    BEAR_TRENDING = "bear_trending"
    BEAR_VOLATILE = "bear_volatile"
    SIDEWAYS_LOW_VOL = "sideways_low_vol"
    SIDEWAYS_HIGH_VOL = "sideways_high_vol"
    CRISIS = "crisis"
    RECOVERY = "recovery"


class SignalType(Enum):
    """Signal types."""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    TREND_FOLLOWING = "trend_following"
    COUNTER_TREND = "counter_trend"
    VOLATILITY_EXPANSION = "volatility_expansion"
    VOLATILITY_CONTRACTION = "volatility_contraction"
    DEFENSIVE = "defensive"
    AGGRESSIVE = "aggressive"


class SignalDirection(Enum):
    """Signal direction."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


class DetectionMethod(Enum):
    """Regime detection methods."""
    HMM = "hmm"
    VOLATILITY_CLUSTER = "volatility_cluster"
    TREND_STRENGTH = "trend_strength"
    MOVING_AVERAGE = "moving_average"
    COMBINED = "combined"


class TrendDirection(Enum):
    """Trend direction."""
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class VolatilityLevel(Enum):
    """Volatility level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class SignalOutcome(Enum):
    """Signal outcome."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PENDING = "pending"
    EXPIRED = "expired"


# Default regime-specific parameters
REGIME_PARAMETERS: dict[str, dict] = {
    # Bull trending - favor momentum, wider stops
    RegimeType.BULL_TRENDING.value: {
        "preferred_signals": [SignalType.MOMENTUM, SignalType.TREND_FOLLOWING],
        "sma_period": 20,
        "rsi_period": 14,
        "rsi_overbought": 75,
        "rsi_oversold": 30,
        "atr_multiplier": 2.0,
        "position_size_factor": 1.2,
        "stop_loss_atr": 2.5,
        "take_profit_atr": 4.0,
    },
    # Bull volatile - tighter stops, smaller positions
    RegimeType.BULL_VOLATILE.value: {
        "preferred_signals": [SignalType.BREAKOUT, SignalType.VOLATILITY_EXPANSION],
        "sma_period": 10,
        "rsi_period": 10,
        "rsi_overbought": 70,
        "rsi_oversold": 35,
        "atr_multiplier": 1.5,
        "position_size_factor": 0.8,
        "stop_loss_atr": 2.0,
        "take_profit_atr": 3.0,
    },
    # Bear trending - favor shorts, defensive
    RegimeType.BEAR_TRENDING.value: {
        "preferred_signals": [SignalType.DEFENSIVE, SignalType.TREND_FOLLOWING],
        "sma_period": 20,
        "rsi_period": 14,
        "rsi_overbought": 65,
        "rsi_oversold": 25,
        "atr_multiplier": 2.5,
        "position_size_factor": 0.7,
        "stop_loss_atr": 3.0,
        "take_profit_atr": 5.0,
    },
    # Bear volatile - minimal exposure
    RegimeType.BEAR_VOLATILE.value: {
        "preferred_signals": [SignalType.DEFENSIVE, SignalType.VOLATILITY_EXPANSION],
        "sma_period": 10,
        "rsi_period": 10,
        "rsi_overbought": 60,
        "rsi_oversold": 20,
        "atr_multiplier": 3.0,
        "position_size_factor": 0.5,
        "stop_loss_atr": 3.5,
        "take_profit_atr": 6.0,
    },
    # Sideways low vol - mean reversion
    RegimeType.SIDEWAYS_LOW_VOL.value: {
        "preferred_signals": [SignalType.MEAN_REVERSION, SignalType.COUNTER_TREND],
        "sma_period": 20,
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "atr_multiplier": 1.5,
        "position_size_factor": 1.0,
        "stop_loss_atr": 1.5,
        "take_profit_atr": 2.0,
    },
    # Sideways high vol - breakout focus
    RegimeType.SIDEWAYS_HIGH_VOL.value: {
        "preferred_signals": [SignalType.BREAKOUT, SignalType.BREAKDOWN],
        "sma_period": 15,
        "rsi_period": 12,
        "rsi_overbought": 68,
        "rsi_oversold": 32,
        "atr_multiplier": 2.0,
        "position_size_factor": 0.8,
        "stop_loss_atr": 2.5,
        "take_profit_atr": 4.0,
    },
    # Crisis - capital preservation
    RegimeType.CRISIS.value: {
        "preferred_signals": [SignalType.DEFENSIVE],
        "sma_period": 5,
        "rsi_period": 7,
        "rsi_overbought": 55,
        "rsi_oversold": 15,
        "atr_multiplier": 4.0,
        "position_size_factor": 0.3,
        "stop_loss_atr": 4.0,
        "take_profit_atr": 8.0,
    },
    # Recovery - aggressive entry
    RegimeType.RECOVERY.value: {
        "preferred_signals": [SignalType.AGGRESSIVE, SignalType.MOMENTUM],
        "sma_period": 10,
        "rsi_period": 10,
        "rsi_overbought": 80,
        "rsi_oversold": 40,
        "atr_multiplier": 1.5,
        "position_size_factor": 1.5,
        "stop_loss_atr": 2.0,
        "take_profit_atr": 3.5,
    },
}


@dataclass
class SignalConfig:
    """Signal generation configuration."""
    
    # Regime detection
    hmm_states: int = 4
    volatility_lookback: int = 20
    trend_lookback: int = 50
    ma_short: int = 20
    ma_long: int = 50
    
    # Signal generation
    min_signal_strength: float = 0.5
    min_confidence: float = 0.6
    signal_expiry_hours: int = 24
    
    # Risk management
    default_stop_loss_pct: float = 2.0
    default_take_profit_pct: float = 4.0
    max_position_size_pct: float = 5.0
    
    # Optimization
    optimization_lookback_days: int = 90
    min_samples_for_optimization: int = 30
    optimization_frequency_days: int = 7


DEFAULT_SIGNAL_CONFIG = SignalConfig()
