---
name: portfolio-optimization
description: Optimize portfolios using mean-variance (Markowitz), Black-Litterman, risk parity, and hierarchical risk parity (HRP). Includes tax-loss harvesting, drift monitoring, threshold/tax-aware rebalancing, strategy blending, and 8 pre-built templates (Aggressive Alpha through All-Weather). Use when constructing portfolios, rebalancing, or computing efficient frontiers.
metadata:
  author: axion-platform
  version: "1.0"
---

# Portfolio Optimization

## When to use this skill

Use this skill when you need to:
- Optimize portfolio weights using mean-variance, risk parity, or HRP
- Incorporate investor views via Black-Litterman
- Monitor portfolio drift and plan rebalance trades
- Perform tax-loss harvesting and tax-aware rebalancing
- Use pre-built portfolio templates (Aggressive Alpha, Balanced Factor, etc.)
- Blend multiple strategy portfolios with custom allocations
- Generate efficient frontier curves

## Step-by-step instructions

### 1. Choose an Optimization Method

Select based on your requirements:

| Method | Class | Best For |
|---|---|---|
| Mean-Variance | `MeanVarianceOptimizer` | Max Sharpe, min variance, target return |
| Risk Parity | `RiskParityOptimizer` | Equal risk contribution from each asset |
| HRP | `HRPOptimizer` | Stable weights, no matrix inversion needed |
| Black-Litterman | `BlackLittermanModel` | Combining market equilibrium with views |

**Source files:**
- `src/optimizer/objectives.py` -- MeanVariance, RiskParity, HRP optimizers
- `src/optimizer/black_litterman.py` -- Black-Litterman model
- `src/optimizer/config.py` -- OptimizationConfig, ConstraintConfig, TaxConfig
- `src/optimizer/constraints.py` -- Constraint engine (position, sector, turnover)
- `src/optimizer/templates.py` -- 8 pre-built portfolio templates
- `src/optimizer/tax.py` -- Tax-loss harvesting and tax-aware rebalancing
- `src/optimizer/analytics.py` -- Portfolio X-Ray and what-if analysis

### 2. Monitor Drift and Plan Rebalance

After initial allocation, monitor and rebalance:

```
DriftMonitor.compute_drift(holdings) -> PortfolioDrift
RebalancePlanner.plan_threshold_rebalance(holdings, value) -> RebalancePlan
```

**Source files:**
- `src/rebalancing/drift.py` -- DriftMonitor (absolute/relative drift)
- `src/rebalancing/planner.py` -- Full, threshold, and tax-aware rebalance plans
- `src/rebalancing/scheduler.py` -- Calendar and threshold-based scheduling
- `src/rebalancing/models.py` -- Holding, DriftAnalysis, RebalancePlan
- `src/rebalancing/config.py` -- DriftConfig, CostConfig, TaxConfig

## Code examples

### Mean-Variance Optimization (Max Sharpe)

```python
import pandas as pd
import numpy as np
from src.optimizer import (
    MeanVarianceOptimizer,
    OptimizationConfig,
    OptimizationResult,
)

# Prepare inputs
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM"]
expected_returns = pd.Series(
    [0.12, 0.10, 0.14, 0.11, 0.08],
    index=tickers,
)
# Covariance matrix from historical returns
cov_matrix = returns_df[tickers].cov() * 252  # Annualized

# Max Sharpe ratio portfolio
config = OptimizationConfig(risk_free_rate=0.05, max_iterations=1000)
optimizer = MeanVarianceOptimizer(config)
result = optimizer.max_sharpe(
    expected_returns, cov_matrix,
    min_weight=0.05,  # At least 5% per position
    max_weight=0.30,  # At most 30% per position
)
print(f"Sharpe: {result.sharpe_ratio:.2f}")
print(f"Return: {result.expected_return:.2%}")
print(f"Volatility: {result.expected_volatility:.2%}")
print(f"Weights: {result.weights}")

# Target return optimization (min variance for 10% return)
result_10pct = optimizer.optimize(
    expected_returns, cov_matrix,
    target_return=0.10,
    min_weight=0.05,
    max_weight=0.30,
)

# Efficient frontier (20 points)
frontier = optimizer.efficient_frontier(
    expected_returns, cov_matrix,
    n_points=20,
    min_weight=0.05,
    max_weight=0.30,
)
for point in frontier:
    print(f"  Return={point.expected_return:.2%}, Vol={point.expected_volatility:.2%}")
```

### Risk Parity Optimization

```python
from src.optimizer import RiskParityOptimizer

rp_optimizer = RiskParityOptimizer()
rp_result = rp_optimizer.optimize(
    cov_matrix,
    min_weight=0.05,
    max_weight=0.30,
)
print(f"Weights: {rp_result.weights}")
print(f"Portfolio vol: {rp_result.expected_volatility:.2%}")

# Verify equal risk contributions
weights_series = pd.Series(rp_result.weights)
risk_contrib = rp_optimizer.get_risk_contributions(weights_series, cov_matrix)
print(f"Risk contributions: {risk_contrib.to_dict()}")
# All should be approximately equal (~0.20 for 5 assets)
```

### Hierarchical Risk Parity (HRP)

```python
from src.optimizer import HRPOptimizer

# HRP uses raw returns, not covariance matrix
hrp = HRPOptimizer()
hrp_result = hrp.optimize(returns_df[tickers])
print(f"HRP weights: {hrp_result.weights}")
print(f"Method: {hrp_result.method}")  # "hrp"
```

### Black-Litterman with Investor Views

```python
from src.optimizer import BlackLittermanModel, View

bl = BlackLittermanModel()

# Define views
views = [
    # Absolute: "AAPL will return 12% annually"
    View(assets=["AAPL"], weights=[1], expected_return=0.12, confidence=0.8),
    # Relative: "NVDA will outperform INTC by 5%"
    View(assets=["NVDA", "INTC"], weights=[1, -1], expected_return=0.05, confidence=0.6),
]

# Market cap weights (from index)
market_weights = pd.Series(
    {"AAPL": 0.30, "MSFT": 0.25, "GOOGL": 0.20, "NVDA": 0.15, "INTC": 0.10}
)

# Compute posterior returns
bl_result = bl.compute_posterior(
    cov_matrix=cov_matrix,
    market_weights=market_weights,
    views=views,
    tau=0.05,
)
print("Prior (equilibrium):")
print(bl_result.prior_returns)
print("Posterior (with views):")
print(bl_result.posterior_returns)

# Feed posterior into mean-variance optimizer
optimizer = MeanVarianceOptimizer()
final_weights = optimizer.max_sharpe(
    bl_result.posterior_returns,
    bl_result.posterior_cov,
)
```

### Portfolio Templates

```python
from src.optimizer import PortfolioTemplate, StrategyBlender, TEMPLATES

# Available templates:
# "aggressive_alpha", "balanced_factor", "quality_income",
# "momentum_rider", "value_contrarian", "low_volatility",
# "risk_parity", "all_weather"

# Use a template to select universe and generate weights
spec = TEMPLATES["aggressive_alpha"]
template = PortfolioTemplate(spec)
selected, scores = template.select_universe(factor_scores_df, universe_size=500)
weights = template.generate_initial_weights(selected, scores)
print(f"Selected {len(selected)} stocks, max weight: {weights.max():.2%}")

# Blend multiple strategies
blender = StrategyBlender()
combined = blender.blend_from_templates(
    template_allocations=[
        ("aggressive_alpha", 0.60),
        ("quality_income", 0.40),
    ],
    factor_scores=factor_scores_df,
)
analysis = blender.analyze_blend([
    ("aggressive_alpha", aa_weights, 0.60),
    ("quality_income", qi_weights, 0.40),
])
print(f"Positions: {analysis['num_positions']}")
print(f"HHI: {analysis['hhi']:.0f}")
print(f"Top-5 concentration: {analysis['top5_concentration']:.2%}")
```

### Drift Monitoring and Rebalancing

```python
from src.rebalancing import (
    DriftMonitor,
    RebalancePlanner,
    Holding,
    DriftConfig,
    DriftMethod,
)

# Define current holdings
holdings = [
    Holding(symbol="AAPL", current_weight=0.32, target_weight=0.25, price=185.0),
    Holding(symbol="MSFT", current_weight=0.18, target_weight=0.25, price=380.0),
    Holding(symbol="GOOGL", current_weight=0.28, target_weight=0.25, price=140.0),
    Holding(symbol="JPM", current_weight=0.22, target_weight=0.25, price=195.0),
]

# Monitor drift
monitor = DriftMonitor(DriftConfig(
    threshold=0.05,           # 5% absolute drift triggers rebalance
    critical_threshold=0.10,  # 10% is critical
    method=DriftMethod.ABSOLUTE,
))
drift = monitor.compute_drift(holdings)
print(f"Max drift: {drift.max_drift:.2%}")
print(f"Needs rebalance: {drift.needs_rebalance}")
print(f"Assets exceeding threshold: {drift.n_exceeding_threshold}")

# Plan threshold rebalance (only trade drifted assets)
planner = RebalancePlanner()
plan = planner.plan_threshold_rebalance(holdings, portfolio_value=100_000)
print(f"Trades: {plan.n_trades}")
print(f"Turnover: ${plan.total_turnover:,.2f}")
print(f"Estimated cost: ${plan.estimated_cost:.2f}")
for trade in plan.trades:
    print(f"  {trade.side} {trade.shares} {trade.symbol} (${trade.value:,.2f})")

# Tax-aware rebalance (avoids short-term gains)
tax_plan = planner.plan_tax_aware_rebalance(holdings, portfolio_value=100_000)
print(f"Tax impact: ${tax_plan.estimated_tax:.2f}")
```

### Tax-Loss Harvesting

```python
from src.optimizer import TaxLossHarvester, TaxAwareRebalancer, Position, TaxConfig

# Identify harvest candidates
harvester = TaxLossHarvester(TaxConfig(
    short_term_rate=0.37,
    long_term_rate=0.20,
    min_harvest_loss=500.0,
))
positions = [
    Position(symbol="META", shares=50, cost_basis=340.0,
             current_price=290.0, purchase_date="2024-08-15", sector="Technology"),
    Position(symbol="AAPL", shares=100, cost_basis=150.0,
             current_price=185.0, purchase_date="2023-01-10", sector="Technology"),
]
candidates = harvester.identify_candidates(positions, recent_sales=["GOOGL"])
for c in candidates:
    print(f"{c.position.symbol}: loss=${c.unrealized_loss:,.2f}, "
          f"savings=${c.estimated_tax_savings:,.2f}, "
          f"wash_sale_risk={c.wash_sale_risk}")

# Estimate annual savings
savings = harvester.estimate_annual_savings(candidates)
print(f"Total tax savings: ${savings['total_tax_savings']:,.2f}")

# Tax-aware rebalance trades
rebalancer = TaxAwareRebalancer()
trades = rebalancer.generate_trades(
    current_weights=pd.Series({"META": 0.30, "AAPL": 0.40, "JPM": 0.30}),
    target_weights=pd.Series({"META": 0.20, "AAPL": 0.40, "JPM": 0.40}),
    positions=positions,
    portfolio_value=100_000,
)
tax_summary = rebalancer.estimate_rebalance_tax(trades)
print(f"Net tax impact: ${tax_summary['net_tax_impact']:,.2f}")
```

## Key classes and methods

### Optimization (`src/optimizer/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `MeanVarianceOptimizer` | `optimize(returns, cov, target_return)`, `max_sharpe()`, `min_variance()`, `efficient_frontier()` | Markowitz optimization |
| `RiskParityOptimizer` | `optimize(cov_matrix)`, `get_risk_contributions(weights, cov)` | Equal risk contribution |
| `HRPOptimizer` | `optimize(returns_df)` | Hierarchical clustering-based allocation |
| `BlackLittermanModel` | `compute_posterior(cov, mkt_weights, views)`, `implied_equilibrium_returns()` | Bayesian return estimation |
| `TaxLossHarvester` | `identify_candidates(positions)`, `find_replacement()`, `estimate_annual_savings()` | Tax-loss harvesting |
| `TaxAwareRebalancer` | `generate_trades(current, target, positions)`, `estimate_rebalance_tax()` | Tax-optimized rebalancing |
| `PortfolioTemplate` | `select_universe(factor_scores)`, `generate_initial_weights()` | Template-based construction |
| `StrategyBlender` | `blend(allocations)`, `blend_from_templates()`, `analyze_blend()` | Combine multiple strategies |
| `ConstraintEngine` | `apply(weights)` | Position, sector, turnover, count constraints |
| `PortfolioAnalytics` | `compute_xray()`, `what_if_analysis()` | Portfolio transparency |

### Rebalancing (`src/rebalancing/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `DriftMonitor` | `compute_drift(holdings)`, `get_history()` | Track weight drift from targets |
| `RebalancePlanner` | `plan_full_rebalance()`, `plan_threshold_rebalance()`, `plan_tax_aware_rebalance()` | Generate trade plans |
| `RebalanceScheduler` | `should_rebalance(holdings)`, `get_next_date()` | Calendar/threshold scheduling |

## Common patterns

### Pre-Built Template Specifications

| Template | Positions | Max Weight | Rebalance | Method |
|---|---|---|---|---|
| `aggressive_alpha` | 10-15 | 15% | Monthly | Max Sharpe |
| `balanced_factor` | 25-30 | 6% | Monthly | Max Sharpe |
| `quality_income` | 20-25 | 8% | Quarterly | Min Variance |
| `momentum_rider` | 10-15 | 12% | Biweekly | Max Sharpe |
| `value_contrarian` | 15-20 | 10% | Monthly | Max Sharpe |
| `low_volatility` | 25-30 | 6% | Quarterly | Min Variance |
| `risk_parity` | 20-30 | 10% | Monthly | Risk Parity |
| `all_weather` | 10-20 | 12% | Quarterly | Risk Parity |

### Optimization Method Selection Guide

- **Max Sharpe** -- Best risk-adjusted returns; sensitive to estimation error
- **Min Variance** -- Lowest volatility; tends to concentrate in low-vol assets
- **Risk Parity** -- Robust; equal risk contribution; ignores expected returns
- **HRP** -- Most stable; no matrix inversion; good for correlated assets
- **Black-Litterman** -- Reduces estimation error by anchoring to market equilibrium

### Key Configuration Defaults

```python
OptimizationConfig(risk_free_rate=0.05, max_iterations=1000, risk_aversion=2.5, tau=0.05)
DriftConfig(threshold=0.05, critical_threshold=0.10, method=DriftMethod.ABSOLUTE)
CostConfig(commission_per_trade=0.0, spread_cost_bps=2.0, min_trade_dollars=100)
TaxConfig(short_term_rate=0.37, long_term_rate=0.20, min_harvest_loss=500.0)
```

### Typical Workflow

1. Compute expected returns and covariance from historical data
2. Optionally apply Black-Litterman with investor views
3. Optimize using the chosen method (MVO, RP, HRP)
4. Apply constraints (position limits, sector caps, turnover)
5. Use `PortfolioTemplate` for pre-built factor-based strategies
6. Monitor drift with `DriftMonitor`
7. Rebalance using `RebalancePlanner` when thresholds are breached
8. Use `TaxLossHarvester` before year-end for tax efficiency
