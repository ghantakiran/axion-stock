"""Macro Regime Analysis Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class RegimeType(Enum):
    """Macro economic regime."""
    EXPANSION = "expansion"
    SLOWDOWN = "slowdown"
    CONTRACTION = "contraction"
    RECOVERY = "recovery"


class CurveShape(Enum):
    """Yield curve shape."""
    NORMAL = "normal"
    FLAT = "flat"
    INVERTED = "inverted"
    HUMPED = "humped"


class IndicatorType(Enum):
    """Economic indicator classification."""
    LEADING = "leading"
    COINCIDENT = "coincident"
    LAGGING = "lagging"


class MacroFactor(Enum):
    """Macro factor type."""
    GROWTH = "growth"
    INFLATION = "inflation"
    RATES = "rates"
    RISK = "risk"
    LIQUIDITY = "liquidity"


@dataclass
class IndicatorConfig:
    """Indicator tracking configuration."""
    momentum_window: int = 6  # months
    trend_window: int = 12  # months
    surprise_threshold: float = 1.0  # std devs for significant surprise
    composite_weights: dict = field(default_factory=lambda: {
        "leading": 0.5,
        "coincident": 0.3,
        "lagging": 0.2,
    })


@dataclass
class YieldCurveConfig:
    """Yield curve analysis configuration."""
    tenors: list[str] = field(default_factory=lambda: [
        "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y",
    ])
    flat_threshold: float = 0.20  # < 20 bps spread = flat
    inversion_threshold: float = -0.05  # < -5 bps = inverted
    key_spread_short: str = "2Y"
    key_spread_long: str = "10Y"


@dataclass
class RegimeConfig:
    """Regime detection configuration."""
    n_regimes: int = 4
    lookback_months: int = 24
    min_regime_duration: int = 3  # months
    transition_smoothing: float = 0.1  # smoothing for transition probs
    consensus_threshold: float = 0.6  # % of indicators agreeing


@dataclass
class FactorConfig:
    """Macro factor model configuration."""
    factors: list[str] = field(default_factory=lambda: [
        "growth", "inflation", "rates", "risk", "liquidity",
    ])
    estimation_window: int = 60  # months
    momentum_window: int = 12  # months for factor momentum
    min_observations: int = 24


@dataclass
class MacroConfig:
    """Top-level macro configuration."""
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    yieldcurve: YieldCurveConfig = field(default_factory=YieldCurveConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    factors: FactorConfig = field(default_factory=FactorConfig)


DEFAULT_INDICATOR_CONFIG = IndicatorConfig()
DEFAULT_YIELDCURVE_CONFIG = YieldCurveConfig()
DEFAULT_REGIME_CONFIG = RegimeConfig()
DEFAULT_FACTOR_CONFIG = FactorConfig()
DEFAULT_CONFIG = MacroConfig()
