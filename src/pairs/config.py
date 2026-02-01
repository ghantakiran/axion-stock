"""Pairs Trading Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class PairSignalType(Enum):
    """Pair trading signal type."""
    LONG_SPREAD = "long_spread"
    SHORT_SPREAD = "short_spread"
    EXIT = "exit"
    NO_SIGNAL = "no_signal"


class SpreadMethod(Enum):
    """Spread computation method."""
    RATIO = "ratio"
    DIFFERENCE = "difference"


class HedgeMethod(Enum):
    """Hedge ratio estimation method."""
    OLS = "ols"
    TLS = "tls"


class PairStatus(Enum):
    """Pair relationship status."""
    COINTEGRATED = "cointegrated"
    WEAK = "weak"
    NOT_COINTEGRATED = "not_cointegrated"


@dataclass
class CointegrationConfig:
    """Cointegration testing configuration."""
    pvalue_threshold: float = 0.05
    min_correlation: float = 0.50
    lookback_window: int = 252
    adf_max_lags: int = 12
    hedge_method: HedgeMethod = HedgeMethod.OLS


@dataclass
class SpreadConfig:
    """Spread analysis configuration."""
    method: SpreadMethod = SpreadMethod.DIFFERENCE
    zscore_window: int = 20
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    stop_zscore: float = 3.5
    max_half_life: int = 60
    min_half_life: int = 1
    hurst_max: float = 0.5  # Below 0.5 = mean-reverting


@dataclass
class SelectorConfig:
    """Pair selection configuration."""
    max_pairs: int = 20
    min_score: float = 50.0
    weight_cointegration: float = 0.35
    weight_half_life: float = 0.25
    weight_correlation: float = 0.20
    weight_hurst: float = 0.20


@dataclass
class PairsConfig:
    """Combined pairs trading configuration."""
    cointegration: CointegrationConfig = field(default_factory=CointegrationConfig)
    spread: SpreadConfig = field(default_factory=SpreadConfig)
    selector: SelectorConfig = field(default_factory=SelectorConfig)


DEFAULT_COINTEGRATION_CONFIG = CointegrationConfig()
DEFAULT_SPREAD_CONFIG = SpreadConfig()
DEFAULT_SELECTOR_CONFIG = SelectorConfig()
DEFAULT_CONFIG = PairsConfig()
