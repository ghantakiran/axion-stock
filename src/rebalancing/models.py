"""Portfolio Rebalancing Data Models."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.rebalancing.config import RebalanceStatus, DriftMethod


@dataclass
class Holding:
    """Single portfolio holding."""
    symbol: str = ""
    shares: float = 0.0
    price: float = 0.0
    market_value: float = 0.0
    current_weight: float = 0.0
    target_weight: float = 0.0
    cost_basis: float = 0.0
    acquisition_date: Optional[date] = None

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - (self.cost_basis * self.shares) if self.shares > 0 else 0.0

    @property
    def is_short_term(self) -> bool:
        if self.acquisition_date is None:
            return True
        return (date.today() - self.acquisition_date).days < 365


@dataclass
class DriftAnalysis:
    """Drift analysis for a single asset."""
    symbol: str = ""
    target_weight: float = 0.0
    current_weight: float = 0.0
    drift: float = 0.0
    drift_pct: float = 0.0
    needs_rebalance: bool = False
    is_critical: bool = False

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "target_weight": round(self.target_weight, 4),
            "current_weight": round(self.current_weight, 4),
            "drift": round(self.drift, 4),
            "drift_pct": round(self.drift_pct, 2),
            "needs_rebalance": self.needs_rebalance,
            "is_critical": self.is_critical,
        }


@dataclass
class PortfolioDrift:
    """Portfolio-level drift summary."""
    asset_drifts: list[DriftAnalysis] = field(default_factory=list)
    max_drift: float = 0.0
    mean_drift: float = 0.0
    rmse_drift: float = 0.0
    n_exceeding_threshold: int = 0
    n_critical: int = 0
    needs_rebalance: bool = False
    date: Optional[date] = None

    def to_dict(self) -> dict:
        return {
            "max_drift": round(self.max_drift, 4),
            "mean_drift": round(self.mean_drift, 4),
            "rmse_drift": round(self.rmse_drift, 4),
            "n_exceeding": self.n_exceeding_threshold,
            "n_critical": self.n_critical,
            "needs_rebalance": self.needs_rebalance,
            "assets": [a.to_dict() for a in self.asset_drifts],
        }


@dataclass
class RebalanceTrade:
    """Single trade in a rebalance plan."""
    symbol: str = ""
    side: str = "buy"  # "buy" or "sell"
    shares: int = 0
    value: float = 0.0
    from_weight: float = 0.0
    to_weight: float = 0.0
    estimated_cost: float = 0.0
    tax_impact: float = 0.0
    is_tax_loss_harvest: bool = False

    @property
    def weight_change(self) -> float:
        return self.to_weight - self.from_weight

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "shares": self.shares,
            "value": round(self.value, 2),
            "from_weight": round(self.from_weight, 4),
            "to_weight": round(self.to_weight, 4),
            "estimated_cost": round(self.estimated_cost, 2),
            "tax_impact": round(self.tax_impact, 2),
        }


@dataclass
class RebalancePlan:
    """Complete rebalance plan."""
    trades: list[RebalanceTrade] = field(default_factory=list)
    total_turnover: float = 0.0
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    estimated_cost: float = 0.0
    estimated_tax: float = 0.0
    drift_before: float = 0.0
    drift_after: float = 0.0
    n_trades: int = 0
    status: RebalanceStatus = RebalanceStatus.PENDING
    date: Optional[date] = None

    @property
    def drift_reduction(self) -> float:
        if self.drift_before > 0:
            return round((self.drift_before - self.drift_after) / self.drift_before * 100, 1)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "n_trades": self.n_trades,
            "total_turnover": round(self.total_turnover, 2),
            "total_buy_value": round(self.total_buy_value, 2),
            "total_sell_value": round(self.total_sell_value, 2),
            "estimated_cost": round(self.estimated_cost, 2),
            "estimated_tax": round(self.estimated_tax, 2),
            "drift_before": round(self.drift_before, 4),
            "drift_after": round(self.drift_after, 4),
            "drift_reduction": self.drift_reduction,
            "status": self.status.value,
            "trades": [t.to_dict() for t in self.trades],
        }


@dataclass
class ScheduleState:
    """Rebalance scheduler state."""
    last_rebalance: Optional[date] = None
    next_scheduled: Optional[date] = None
    trigger_active: bool = False
    days_until_next: int = 0
    threshold_breached: bool = False

    def to_dict(self) -> dict:
        return {
            "last_rebalance": self.last_rebalance.isoformat() if self.last_rebalance else None,
            "next_scheduled": self.next_scheduled.isoformat() if self.next_scheduled else None,
            "trigger_active": self.trigger_active,
            "days_until_next": self.days_until_next,
            "threshold_breached": self.threshold_breached,
        }
