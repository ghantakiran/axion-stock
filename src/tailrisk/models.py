"""Tail Risk Data Models."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CVaRResult:
    """Expected shortfall (CVaR) result."""
    confidence: float = 0.95
    horizon_days: int = 1
    var_pct: float = 0.0
    cvar_pct: float = 0.0
    var_dollar: float = 0.0
    cvar_dollar: float = 0.0
    portfolio_value: float = 0.0
    method: str = "historical"
    n_observations: int = 0
    tail_ratio: float = 0.0

    @property
    def cvar_bps(self) -> float:
        return round(self.cvar_pct * 10000, 2)

    @property
    def excess_over_var(self) -> float:
        """How much worse CVaR is relative to VaR."""
        return self.cvar_pct - self.var_pct if self.var_pct > 0 else 0.0


@dataclass
class CVaRContribution:
    """Per-asset CVaR contribution."""
    asset: str = ""
    weight: float = 0.0
    marginal_cvar: float = 0.0
    component_cvar: float = 0.0
    pct_of_total: float = 0.0


@dataclass
class TailDependence:
    """Tail dependence between two assets."""
    asset_a: str = ""
    asset_b: str = ""
    lower_tail: float = 0.0
    upper_tail: float = 0.0
    normal_correlation: float = 0.0
    tail_correlation: float = 0.0
    contagion_score: float = 0.0

    @property
    def has_tail_dependence(self) -> bool:
        return self.lower_tail > 0.1 or self.upper_tail > 0.1

    @property
    def tail_amplification(self) -> float:
        """How much tail correlation exceeds normal correlation."""
        if abs(self.normal_correlation) < 0.01:
            return 0.0
        return self.tail_correlation / self.normal_correlation if self.normal_correlation != 0 else 0.0


@dataclass
class HedgeRecommendation:
    """Recommended hedge position."""
    instrument: str = "put_option"
    notional: float = 0.0
    cost_pct: float = 0.0
    cost_dollar: float = 0.0
    protection_pct: float = 0.0
    hedge_ratio: float = 0.0
    effectiveness: float = 0.0
    description: str = ""

    @property
    def cost_bps(self) -> float:
        return round(self.cost_pct * 10000, 2)

    @property
    def is_cost_effective(self) -> bool:
        return self.effectiveness > 0.5


@dataclass
class HedgePortfolio:
    """Complete hedge portfolio recommendation."""
    hedges: list[HedgeRecommendation] = field(default_factory=list)
    total_cost_pct: float = 0.0
    total_cost_dollar: float = 0.0
    total_protection_pct: float = 0.0
    portfolio_value: float = 0.0
    unhedged_cvar: float = 0.0
    hedged_cvar: float = 0.0

    @property
    def cvar_reduction_pct(self) -> float:
        if self.unhedged_cvar > 0:
            return round(1.0 - self.hedged_cvar / self.unhedged_cvar, 4)
        return 0.0


@dataclass
class DrawdownStats:
    """Drawdown statistics."""
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    current_drawdown: float = 0.0
    drawdown_duration: int = 0
    recovery_days: int = 0
    cdar: float = 0.0

    @property
    def is_in_drawdown(self) -> bool:
        return self.current_drawdown < -0.001

    @property
    def max_drawdown_pct(self) -> float:
        return round(self.max_drawdown * 100, 2)


@dataclass
class DrawdownBudget:
    """Per-asset drawdown risk budget."""
    asset: str = ""
    weight: float = 0.0
    max_drawdown: float = 0.0
    allocated_budget: float = 0.0
    current_usage: float = 0.0
    remaining_budget: float = 0.0
    recommended_weight: float = 0.0

    @property
    def is_over_budget(self) -> bool:
        return self.current_usage > self.allocated_budget

    @property
    def utilization_pct(self) -> float:
        return self.current_usage / self.allocated_budget if self.allocated_budget > 0 else 0.0
