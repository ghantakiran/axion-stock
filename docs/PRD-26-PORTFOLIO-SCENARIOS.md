# PRD-26: Portfolio Scenarios

**Priority**: P1 | **Phase**: 15 | **Status**: Draft

---

## Problem Statement

Investors need to understand how potential changes would affect their portfolio before executing trades. They want to answer questions like "What if I sell AAPL and buy MSFT?", "How would a 20% market crash affect me?", or "What's the optimal rebalancing strategy?". A portfolio scenarios tool enables what-if analysis, hypothetical portfolio construction, and rebalancing simulation without risking real capital.

---

## Goals

1. **What-If Analysis** - Simulate trade impacts before execution
2. **Hypothetical Portfolios** - Create and compare paper portfolios
3. **Rebalancing Simulation** - Test rebalancing strategies
4. **Scenario Stress Testing** - Apply market scenarios to portfolio
5. **Comparison Tools** - Compare current vs proposed portfolios
6. **Goal-Based Planning** - Model paths to investment goals

---

## Detailed Requirements

### R1: What-If Trade Analysis

#### R1.1: Trade Simulation
```python
@dataclass
class TradeSimulation:
    simulation_id: str
    base_portfolio: Portfolio
    
    # Proposed trades
    trades: list[ProposedTrade]
    
    # Results
    resulting_portfolio: Portfolio
    
    # Impact analysis
    value_change: float
    weight_changes: dict[str, float]
    risk_impact: RiskImpact
    tax_impact: TaxImpact
    
    # Costs
    estimated_commission: float
    estimated_slippage: float
    total_cost: float
```

#### R1.2: Proposed Trade
```python
@dataclass
class ProposedTrade:
    symbol: str
    action: str  # buy, sell, sell_all
    
    # Quantity specification
    quantity: Optional[float] = None
    dollar_amount: Optional[float] = None
    target_weight: Optional[float] = None
    
    # Price assumptions
    assumed_price: Optional[float] = None
    use_limit: bool = False
    limit_price: Optional[float] = None
```

### R2: Hypothetical Portfolios

#### R2.1: Portfolio Model
```python
@dataclass
class HypotheticalPortfolio:
    portfolio_id: str
    name: str
    description: Optional[str] = None
    
    # Holdings
    holdings: list[HypotheticalHolding]
    cash: float = 0.0
    
    # Constraints
    total_value: float = 100000.0
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    is_template: bool = False
    tags: list[str] = field(default_factory=list)
```

#### R2.2: Holding Model
```python
@dataclass
class HypotheticalHolding:
    symbol: str
    
    # Position sizing (one of these)
    shares: Optional[float] = None
    weight: Optional[float] = None  # 0-1
    dollar_value: Optional[float] = None
    
    # Current data
    current_price: float = 0.0
    
    # Calculated
    market_value: float = 0.0
    actual_weight: float = 0.0
```

### R3: Rebalancing Simulation

#### R3.1: Rebalancing Strategies
| Strategy | Description |
|----------|-------------|
| **Target Weight** | Rebalance to target allocation |
| **Threshold** | Rebalance when drift exceeds threshold |
| **Calendar** | Rebalance on schedule (monthly, quarterly) |
| **Tax-Aware** | Minimize tax impact while rebalancing |
| **Cash Flow** | Rebalance using new deposits/withdrawals |

#### R3.2: Rebalancing Model
```python
@dataclass
class RebalanceSimulation:
    simulation_id: str
    
    # Current state
    current_portfolio: Portfolio
    target_allocation: dict[str, float]  # symbol -> weight
    
    # Strategy
    strategy: RebalanceStrategy
    threshold_pct: float = 5.0  # For threshold strategy
    
    # Results
    required_trades: list[ProposedTrade]
    estimated_costs: float
    tax_impact: TaxImpact
    
    # Before/After comparison
    current_drift: dict[str, float]
    post_rebalance_drift: dict[str, float]
```

### R4: Market Scenarios

#### R4.1: Predefined Scenarios
| Scenario | Description |
|----------|-------------|
| **Market Crash (-20%)** | Broad market decline |
| **Bear Market (-35%)** | Extended downturn |
| **Sector Rotation** | Tech sells off, value rallies |
| **Interest Rate Spike** | Bonds down, financials up |
| **Recession** | Cyclicals down, defensives up |
| **Inflation Surge** | Commodities up, growth down |
| **Black Swan (-50%)** | Extreme market event |

#### R4.2: Scenario Model
```python
@dataclass
class MarketScenario:
    scenario_id: str
    name: str
    description: str
    
    # Market-wide impact
    market_change_pct: float
    
    # Sector impacts
    sector_impacts: dict[str, float]  # sector -> change %
    
    # Factor impacts
    factor_impacts: dict[str, float]  # factor -> change %
    
    # Custom symbol impacts
    symbol_overrides: dict[str, float] = field(default_factory=dict)
```

#### R4.3: Scenario Results
```python
@dataclass
class ScenarioResult:
    scenario: MarketScenario
    portfolio: Portfolio
    
    # Portfolio impact
    starting_value: float
    ending_value: float
    value_change: float
    pct_change: float
    
    # Position impacts
    position_impacts: list[PositionImpact]
    
    # Risk metrics
    max_loss: float
    positions_down: int
    worst_performers: list[str]
    best_performers: list[str]
```

### R5: Portfolio Comparison

#### R5.1: Comparison Metrics
| Category | Metrics |
|----------|---------|
| **Allocation** | Weight distribution, sector exposure, concentration |
| **Risk** | Beta, volatility, VaR, max drawdown |
| **Return** | Expected return, historical return, risk-adjusted |
| **Income** | Dividend yield, income generation |
| **Quality** | Factor exposures, quality scores |
| **Costs** | Expense ratios, transaction costs |

#### R5.2: Comparison Model
```python
@dataclass
class PortfolioComparison:
    comparison_id: str
    
    portfolios: list[Portfolio]  # 2 or more
    
    # Comparison data
    metrics: dict[str, dict[str, float]]  # portfolio_id -> metric -> value
    
    # Differences
    allocation_differences: dict[str, float]
    risk_differences: dict[str, float]
    
    # Recommendation
    recommended_portfolio: Optional[str] = None
    recommendation_reason: str = ""
```

### R6: Goal-Based Planning

#### R6.1: Investment Goal
```python
@dataclass
class InvestmentGoal:
    goal_id: str
    name: str
    
    # Target
    target_amount: float
    target_date: date
    
    # Current state
    current_amount: float
    monthly_contribution: float
    
    # Assumptions
    expected_return: float = 0.07  # 7% annual
    inflation_rate: float = 0.03  # 3% annual
    
    # Results
    projected_value: float = 0.0
    probability_of_success: float = 0.0
    shortfall: float = 0.0
```

#### R6.2: Goal Scenarios
- Monte Carlo simulation for probability of success
- Required contribution calculator
- Required return calculator
- Time to goal calculator

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Simulation accuracy | Within 1% of actual |
| Scenario coverage | 10+ predefined scenarios |
| User adoption | 40%+ use what-if analysis |
| Planning completion | 30%+ set investment goals |

---

## Dependencies

- Portfolio management (PRD-08)
- Risk management (PRD-04/17)
- Tax optimization (PRD-20)
- Market data (PRD-01)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
