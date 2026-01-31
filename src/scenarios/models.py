"""Portfolio Scenarios Data Models.

Dataclasses for portfolios, trades, scenarios, and goals.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Optional
import uuid

from src.scenarios.config import (
    TradeAction,
    SizeMethod,
    RebalanceStrategy,
    ScenarioType,
    GoalType,
    GoalPriority,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Portfolio Models
# =============================================================================

@dataclass
class Holding:
    """A portfolio holding."""
    symbol: str
    shares: float = 0.0
    cost_basis: float = 0.0
    current_price: float = 0.0
    
    # Classification
    sector: str = ""
    asset_type: str = "stock"
    
    @property
    def market_value(self) -> float:
        return self.shares * self.current_price
    
    @property
    def unrealized_gain(self) -> float:
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_gain_pct(self) -> float:
        if self.cost_basis > 0:
            return self.unrealized_gain / self.cost_basis * 100
        return 0.0


@dataclass
class Portfolio:
    """A portfolio of holdings."""
    portfolio_id: str = field(default_factory=_new_id)
    name: str = ""
    
    # Holdings
    holdings: list[Holding] = field(default_factory=list)
    cash: float = 0.0
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    
    @property
    def total_value(self) -> float:
        return sum(h.market_value for h in self.holdings) + self.cash
    
    @property
    def holdings_value(self) -> float:
        return sum(h.market_value for h in self.holdings)
    
    def get_weight(self, symbol: str) -> float:
        """Get weight of a symbol in portfolio."""
        if self.total_value == 0:
            return 0.0
        for h in self.holdings:
            if h.symbol == symbol:
                return h.market_value / self.total_value
        return 0.0
    
    def get_weights(self) -> dict[str, float]:
        """Get all weights."""
        if self.total_value == 0:
            return {}
        return {h.symbol: h.market_value / self.total_value for h in self.holdings}
    
    def get_holding(self, symbol: str) -> Optional[Holding]:
        """Get holding by symbol."""
        for h in self.holdings:
            if h.symbol == symbol:
                return h
        return None


@dataclass
class HypotheticalPortfolio(Portfolio):
    """A hypothetical/paper portfolio."""
    description: str = ""
    is_template: bool = False
    tags: list[str] = field(default_factory=list)
    target_value: float = 100000.0


# =============================================================================
# Trade Models
# =============================================================================

@dataclass
class ProposedTrade:
    """A proposed trade for simulation."""
    trade_id: str = field(default_factory=_new_id)
    symbol: str = ""
    action: TradeAction = TradeAction.BUY
    
    # Sizing (one of these)
    shares: Optional[float] = None
    dollar_amount: Optional[float] = None
    target_weight: Optional[float] = None
    percent_of_position: Optional[float] = None
    
    # Price
    assumed_price: Optional[float] = None
    
    # Calculated
    calculated_shares: float = 0.0
    calculated_value: float = 0.0
    
    def get_size_method(self) -> SizeMethod:
        if self.shares is not None:
            return SizeMethod.SHARES
        elif self.dollar_amount is not None:
            return SizeMethod.DOLLARS
        elif self.target_weight is not None:
            return SizeMethod.WEIGHT
        elif self.percent_of_position is not None:
            return SizeMethod.PERCENT_OF_POSITION
        return SizeMethod.SHARES


@dataclass
class RiskImpact:
    """Risk impact of a trade or scenario."""
    beta_change: float = 0.0
    volatility_change: float = 0.0
    var_change: float = 0.0
    concentration_change: float = 0.0
    sector_exposure_changes: dict[str, float] = field(default_factory=dict)


@dataclass
class TaxImpact:
    """Tax impact of trades."""
    short_term_gains: float = 0.0
    long_term_gains: float = 0.0
    short_term_losses: float = 0.0
    long_term_losses: float = 0.0
    estimated_tax: float = 0.0
    wash_sale_risk: bool = False


@dataclass
class TradeSimulation:
    """Result of a trade simulation."""
    simulation_id: str = field(default_factory=_new_id)
    
    # Input
    base_portfolio: Optional[Portfolio] = None
    trades: list[ProposedTrade] = field(default_factory=list)
    
    # Output
    resulting_portfolio: Optional[Portfolio] = None
    
    # Impact
    value_change: float = 0.0
    weight_changes: dict[str, float] = field(default_factory=dict)
    risk_impact: Optional[RiskImpact] = None
    tax_impact: Optional[TaxImpact] = None
    
    # Costs
    estimated_commission: float = 0.0
    estimated_slippage: float = 0.0
    total_cost: float = 0.0
    
    # Metadata
    simulated_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Rebalancing Models
# =============================================================================

@dataclass
class TargetAllocation:
    """Target portfolio allocation."""
    allocation_id: str = field(default_factory=_new_id)
    name: str = ""
    
    # Targets
    targets: dict[str, float] = field(default_factory=dict)  # symbol -> weight
    
    # Constraints
    max_single_position: float = 0.25
    min_position_size: float = 0.01
    
    def validate(self) -> tuple[bool, str]:
        """Validate allocation sums to 1."""
        total = sum(self.targets.values())
        if abs(total - 1.0) > 0.001:
            return False, f"Weights sum to {total:.2%}, should be 100%"
        return True, ""


@dataclass
class RebalanceSimulation:
    """Result of a rebalance simulation."""
    simulation_id: str = field(default_factory=_new_id)
    
    # Input
    current_portfolio: Optional[Portfolio] = None
    target_allocation: Optional[TargetAllocation] = None
    strategy: RebalanceStrategy = RebalanceStrategy.TARGET_WEIGHT
    threshold_pct: float = 5.0
    
    # Output
    required_trades: list[ProposedTrade] = field(default_factory=list)
    resulting_portfolio: Optional[Portfolio] = None
    
    # Analysis
    current_drift: dict[str, float] = field(default_factory=dict)
    post_rebalance_drift: dict[str, float] = field(default_factory=dict)
    
    # Costs
    estimated_costs: float = 0.0
    tax_impact: Optional[TaxImpact] = None
    
    # Metadata
    simulated_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Scenario Models
# =============================================================================

@dataclass
class MarketScenario:
    """A market scenario for stress testing."""
    scenario_id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    scenario_type: ScenarioType = ScenarioType.CUSTOM
    
    # Market-wide impact
    market_change_pct: float = 0.0
    
    # Sector impacts (override market change)
    sector_impacts: dict[str, float] = field(default_factory=dict)
    
    # Factor impacts
    factor_impacts: dict[str, float] = field(default_factory=dict)
    
    # Custom symbol impacts (override everything)
    symbol_overrides: dict[str, float] = field(default_factory=dict)
    
    # Metadata
    is_predefined: bool = False


@dataclass
class PositionImpact:
    """Impact of a scenario on a position."""
    symbol: str
    starting_value: float
    ending_value: float
    change: float
    change_pct: float
    sector: str = ""


@dataclass
class ScenarioResult:
    """Result of applying a scenario to a portfolio."""
    result_id: str = field(default_factory=_new_id)
    scenario: Optional[MarketScenario] = None
    portfolio: Optional[Portfolio] = None
    
    # Portfolio impact
    starting_value: float = 0.0
    ending_value: float = 0.0
    value_change: float = 0.0
    pct_change: float = 0.0
    
    # Position impacts
    position_impacts: list[PositionImpact] = field(default_factory=list)
    
    # Analysis
    max_loss: float = 0.0
    positions_down: int = 0
    positions_up: int = 0
    worst_performers: list[str] = field(default_factory=list)
    best_performers: list[str] = field(default_factory=list)
    
    # Metadata
    simulated_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Comparison Models
# =============================================================================

@dataclass
class PortfolioMetrics:
    """Metrics for a portfolio."""
    portfolio_id: str
    
    # Value
    total_value: float = 0.0
    cash_weight: float = 0.0
    
    # Allocation
    num_holdings: int = 0
    top_holding_weight: float = 0.0
    concentration_hhi: float = 0.0  # Herfindahl index
    
    # Sector exposure
    sector_weights: dict[str, float] = field(default_factory=dict)
    
    # Risk
    beta: float = 1.0
    volatility: float = 0.0
    var_95: float = 0.0
    
    # Income
    dividend_yield: float = 0.0
    
    # Quality
    avg_quality_score: float = 0.0


@dataclass
class PortfolioComparison:
    """Comparison between portfolios."""
    comparison_id: str = field(default_factory=_new_id)
    
    # Portfolios
    portfolios: list[Portfolio] = field(default_factory=list)
    portfolio_names: list[str] = field(default_factory=list)
    
    # Metrics for each
    metrics: list[PortfolioMetrics] = field(default_factory=list)
    
    # Differences
    weight_differences: dict[str, list[float]] = field(default_factory=dict)
    
    # Recommendation
    recommended_index: Optional[int] = None
    recommendation_reason: str = ""
    
    # Metadata
    compared_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Goal Models
# =============================================================================

@dataclass
class InvestmentGoal:
    """An investment goal."""
    goal_id: str = field(default_factory=_new_id)
    name: str = ""
    goal_type: GoalType = GoalType.CUSTOM
    priority: GoalPriority = GoalPriority.MEDIUM
    
    # Target
    target_amount: float = 0.0
    target_date: Optional[date] = None
    
    # Current state
    current_amount: float = 0.0
    monthly_contribution: float = 0.0
    
    # Assumptions
    expected_return: float = 0.07
    volatility: float = 0.15
    inflation_rate: float = 0.03
    
    # Results (calculated)
    projected_value: float = 0.0
    probability_of_success: float = 0.0
    shortfall: float = 0.0
    required_monthly: float = 0.0
    months_to_goal: int = 0
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass
class GoalProjection:
    """Projection path for a goal."""
    goal_id: str
    
    # Time series
    months: list[int] = field(default_factory=list)
    projected_values: list[float] = field(default_factory=list)
    contributions: list[float] = field(default_factory=list)
    
    # Confidence bands
    p10_values: list[float] = field(default_factory=list)  # 10th percentile
    p50_values: list[float] = field(default_factory=list)  # Median
    p90_values: list[float] = field(default_factory=list)  # 90th percentile
    
    # Milestones
    target_amount: float = 0.0
    target_month: int = 0
    expected_achievement_month: Optional[int] = None
