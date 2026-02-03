"""Tail Risk Hedging Configuration."""

from dataclasses import dataclass
from enum import Enum


class CVaRMethod(str, Enum):
    """CVaR computation method."""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    CORNISH_FISHER = "cornish_fisher"


class HedgeInstrument(str, Enum):
    """Hedge instrument type."""
    PUT_OPTION = "put_option"
    VIX_CALL = "vix_call"
    INVERSE_ETF = "inverse_etf"
    CASH = "cash"


class DrawdownMethod(str, Enum):
    """Drawdown estimation method."""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"


class RiskBudgetMethod(str, Enum):
    """Risk budget allocation method."""
    EQUAL = "equal"
    PROPORTIONAL = "proportional"
    INVERSE_VOL = "inverse_vol"


@dataclass(frozen=True)
class CVaRConfig:
    """CVaR configuration."""
    confidence: float = 0.95
    method: CVaRMethod = CVaRMethod.HISTORICAL
    min_observations: int = 60
    horizon_days: int = 1


@dataclass(frozen=True)
class DependenceConfig:
    """Tail dependence configuration."""
    tail_threshold: float = 0.05
    min_observations: int = 100
    extreme_quantile: float = 0.10


@dataclass(frozen=True)
class HedgingConfig:
    """Hedge construction configuration."""
    max_hedge_cost_pct: float = 0.02
    target_protection_pct: float = 0.10
    vix_hedge_ratio: float = 0.10
    put_otm_pct: float = 0.05
    hedge_horizon_days: int = 30


@dataclass(frozen=True)
class BudgetingConfig:
    """Drawdown risk budgeting configuration."""
    max_portfolio_drawdown: float = 0.20
    method: RiskBudgetMethod = RiskBudgetMethod.INVERSE_VOL
    confidence: float = 0.95
    lookback_days: int = 252
