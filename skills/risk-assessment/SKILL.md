---
name: risk-assessment
description: Enterprise risk management including VaR (historical, parametric, Monte Carlo), stress testing (COVID, GFC, rate hikes), drawdown protection, correlation guard, VaR-based position sizing, regime-adaptive limits, and unified 7-check risk context. Use when validating trades, computing portfolio risk metrics, running stress tests, or sizing positions based on tail risk.
metadata:
  author: axion-platform
  version: "1.0"
---

# Risk Assessment

## When to use this skill

Use this skill when you need to:
- Calculate portfolio risk metrics (Sharpe, Sortino, beta, drawdown, VaR)
- Run Value at Risk using historical, parametric, or Monte Carlo methods
- Stress test a portfolio against historical events (COVID crash, GFC) or hypothetical shocks
- Perform unified pre-trade risk validation (7 checks in a single pass)
- Guard against correlated position clusters
- Size positions dynamically using VaR/CVaR risk budgeting
- Apply regime-adaptive risk limits (bull, bear, sideways, crisis)

## Step-by-step instructions

### 1. Calculate Portfolio Risk Metrics

Compute standard risk metrics from return data:

**Source files:**
- `src/risk/metrics.py` -- RiskMetricsCalculator (Sharpe, Sortino, beta, drawdown)
- `src/risk/var.py` -- VaRCalculator (historical, parametric, Monte Carlo)
- `src/risk/stress_test.py` -- StressTestEngine with pre-built scenarios
- `src/risk/drawdown.py` -- DrawdownProtection and RecoveryProtocol
- `src/risk/pre_trade.py` -- PreTradeRiskChecker
- `src/risk/attribution.py` -- Brinson and factor attribution
- `src/risk/monitor.py` -- Real-time risk monitoring

### 2. Run Unified Risk Assessment

The unified risk context consolidates all risk subsystems into a single `assess()` call:

**Source files:**
- `src/unified_risk/context.py` -- RiskContext with 7 checks
- `src/unified_risk/correlation.py` -- CorrelationGuard (Pearson-based)
- `src/unified_risk/var_sizer.py` -- VaRPositionSizer
- `src/unified_risk/regime_limits.py` -- RegimeRiskAdapter

### 3. Stress Test Under Adverse Scenarios

Apply historical or hypothetical shocks to assess portfolio resilience:

**Source files:**
- `src/risk/stress_test.py` -- StressTestEngine, HISTORICAL_SCENARIOS, HYPOTHETICAL_SCENARIOS
- `src/risk/scenario_builder.py` -- ScenarioBuilder for custom scenarios
- `src/risk/shock_propagation.py` -- ShockPropagationEngine for factor shocks

## Code examples

### Portfolio Risk Metrics

```python
import pandas as pd
from src.risk import (
    RiskMetricsCalculator,
    PortfolioRiskMetrics,
    RiskConfig,
)

# Initialize with configuration
config = RiskConfig(
    risk_free_rate=0.05,
    benchmark_symbol="SPY",
    lookback_days=252,
)
calculator = RiskMetricsCalculator(config)

# Compute from return series
portfolio_returns = returns_df["portfolio"]
benchmark_returns = returns_df["SPY"]

metrics = calculator.compute(
    portfolio_returns=portfolio_returns,
    benchmark_returns=benchmark_returns,
    positions=current_positions,
)
print(f"Sharpe: {metrics.sharpe_ratio:.2f}")
print(f"Sortino: {metrics.sortino_ratio:.2f}")
print(f"Calmar: {metrics.calmar_ratio:.2f}")
print(f"Beta: {metrics.portfolio_beta:.2f}")
print(f"Max Drawdown: {metrics.max_drawdown:.2%}")
print(f"VaR 95%: {metrics.var_95:.2%}")
print(f"CVaR 95%: {metrics.cvar_95:.2%}")
```

### Value at Risk (3 Methods)

```python
from src.risk import VaRCalculator, VaRResult

var_calc = VaRCalculator()

# Historical VaR
historical = var_calc.historical_var(
    returns=portfolio_returns.tolist(),
    confidence=0.95,
    holding_period=1,
)
print(f"Historical VaR 95%: {historical.var_95:.2%}")
print(f"CVaR 95%: {historical.cvar_95:.2%}")

# Parametric VaR (normal distribution)
parametric = var_calc.parametric_var(
    returns=portfolio_returns.tolist(),
    confidence=0.95,
)
print(f"Parametric VaR 95%: {parametric.var_95:.2%}")

# Monte Carlo VaR
mc_var = var_calc.monte_carlo_var(
    returns=portfolio_returns.tolist(),
    confidence=0.95,
    n_simulations=10_000,
)
print(f"MC VaR 95%: {mc_var.var_95:.2%}")
print(f"MC VaR 99%: {mc_var.var_99:.2%}")
```

### Stress Testing

```python
from src.risk import (
    StressTestEngine,
    StressScenario,
    HISTORICAL_SCENARIOS,
    HYPOTHETICAL_SCENARIOS,
)

engine = StressTestEngine()

# Run against pre-built historical scenarios
for scenario in HISTORICAL_SCENARIOS:
    # Scenarios include: COVID Crash, 2022 Bear Market, GFC, etc.
    result = engine.run(
        scenario=scenario,
        portfolio_weights={"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25, "JPM": 0.25},
        portfolio_value=100_000,
        historical_returns=returns_data,
    )
    print(f"{result.scenario_name}: {result.portfolio_impact_pct:+.1%} "
          f"(${result.portfolio_impact_dollars:+,.0f})")
    print(f"  Worst: {result.worst_position_symbol} ({result.worst_position_impact_pct:+.1%})")

# Custom hypothetical scenario
custom = StressScenario(
    name="Tech Crash + Rate Hike",
    description="30% tech decline with 200bps rate increase",
    scenario_type="hypothetical",
    market_shock=-0.15,
    sector_shocks={"Technology": -0.30, "Financials": 0.05},
    interest_rate_shock_bps=200,
    volatility_shock=1.5,
)
result = engine.run(
    scenario=custom,
    portfolio_weights=weights,
    portfolio_value=100_000,
    historical_returns=returns_data,
)
```

### Unified Risk Context (7 Checks)

```python
from src.unified_risk import (
    RiskContext,
    RiskContextConfig,
    CorrelationConfig,
    VaRConfig,
    UnifiedRiskAssessment,
)

# Configure unified risk
config = RiskContextConfig(
    max_daily_loss_pct=10.0,
    max_concurrent_positions=10,
    max_single_stock_pct=15.0,
    max_sector_pct=30.0,
    correlation_config=CorrelationConfig(
        max_pairwise_correlation=0.80,
        max_cluster_size=4,
        lookback_days=60,
    ),
    var_config=VaRConfig(
        confidence_level=0.95,
        max_portfolio_var_pct=2.0,
        max_position_var_pct=0.5,
        use_cvar=True,
    ),
    enable_correlation_guard=True,
    enable_var_sizing=True,
)

# Create context with current equity
ctx = RiskContext(config=config, equity=100_000)
ctx.record_pnl(-300.0)  # Record daily losses

# Run all 7 checks in a single call
assessment = ctx.assess(
    ticker="NVDA",
    direction="long",
    positions=[
        {"symbol": "AAPL", "market_value": 15_000},
        {"symbol": "MSFT", "market_value": 12_000},
    ],
    returns_by_ticker={
        "NVDA": daily_returns_nvda,
        "AAPL": daily_returns_aapl,
        "MSFT": daily_returns_msft,
    },
    regime="bull",
    circuit_breaker_status="closed",
    kill_switch_active=False,
)

if assessment.approved:
    print(f"APPROVED: max position size ${assessment.max_position_size:,.0f}")
    print(f"Regime: {assessment.regime}")
    print(f"Concentration: {assessment.concentration_score:.0f}/100")
    if assessment.portfolio_var:
        print(f"VaR: {assessment.portfolio_var.var_pct:.2f}%")
    if assessment.warnings:
        print(f"Warnings: {assessment.warnings}")
else:
    print(f"REJECTED: {assessment.rejection_reason}")

print(f"Checks run: {assessment.checks_run}")
```

### Correlation Guard

```python
from src.unified_risk import CorrelationGuard, CorrelationConfig

guard = CorrelationGuard(CorrelationConfig(
    max_pairwise_correlation=0.80,
    max_cluster_size=4,
    cluster_threshold=0.70,
    min_data_points=20,
))

# Compute correlation matrix from daily returns
returns_by_ticker = {
    "AAPL": aapl_returns,
    "MSFT": msft_returns,
    "GOOGL": googl_returns,
    "NVDA": nvda_returns,
}
matrix = guard.compute_matrix(returns_by_ticker)
print(f"Max correlation: {matrix.max_correlation:.2f}")
print(f"Clusters: {matrix.clusters}")

# Check if adding a new position is safe
approved, reason = guard.check_new_trade(
    new_ticker="AMD",
    corr_matrix=matrix,
    current_holdings=["NVDA", "AAPL"],
)
print(f"Approved: {approved}, Reason: {reason}")

# Get portfolio concentration score (0-100)
score = guard.get_portfolio_concentration_score(
    matrix, ["AAPL", "MSFT", "GOOGL"]
)
print(f"Concentration: {score:.0f}/100")
```

### VaR-Based Position Sizing

```python
from src.unified_risk import VaRPositionSizer, VaRConfig

sizer = VaRPositionSizer(
    config=VaRConfig(
        confidence_level=0.95,
        max_portfolio_var_pct=2.0,
        max_position_var_pct=0.5,
        use_cvar=True,
    ),
    equity=100_000,
)

# Compute VaR for a specific ticker
result = sizer.compute_var(returns=nvda_daily_returns)
print(f"VaR 95%: {result.var_pct:.2f}%")
print(f"CVaR: {result.cvar_pct:.2f}%")
print(f"Risk budget remaining: {result.risk_budget_remaining:.2f}%")

# Size a new position
max_dollars = sizer.size_position(
    ticker_returns=nvda_daily_returns,
    current_price=850.0,
    existing_var_pct=1.2,  # Current portfolio VaR
)
print(f"Max position: ${max_dollars:,.0f}")

# Portfolio-level VaR
port_var = sizer.compute_portfolio_var(
    positions_returns={"AAPL": aapl_rets, "MSFT": msft_rets},
    weights={"AAPL": 0.60, "MSFT": 0.40},
)
print(f"Portfolio VaR: {port_var.var_pct:.2f}%")
```

### Drawdown Protection

```python
from src.risk import DrawdownProtection, DrawdownRule, RecoveryProtocol

protection = DrawdownProtection(rules=[
    DrawdownRule(threshold=-0.05, action="reduce_exposure", reduce_by=0.25),
    DrawdownRule(threshold=-0.10, action="halt_new_trades"),
    DrawdownRule(threshold=-0.15, action="liquidate_all"),
])

# Check current drawdown level
state = protection.evaluate(current_drawdown=-0.08)
print(f"Action: {state.action}")  # "reduce_exposure"
print(f"Reduce by: {state.reduce_by:.0%}")

# Recovery protocol
recovery = RecoveryProtocol()
recovery_plan = recovery.assess(
    current_drawdown=-0.12,
    equity_curve=equity_series,
)
```

## Key classes and methods

### Enterprise Risk (`src/risk/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `RiskMetricsCalculator` | `compute(portfolio_returns, benchmark_returns, positions)` | Full risk metrics suite |
| `VaRCalculator` | `historical_var()`, `parametric_var()`, `monte_carlo_var()` | Three VaR methodologies |
| `StressTestEngine` | `run(scenario, portfolio_weights, value, returns)` | Historical/hypothetical stress tests |
| `DrawdownProtection` | `evaluate(current_drawdown)` | Automated drawdown rules |
| `PreTradeRiskChecker` | `validate(order, portfolio)` | Pre-trade risk validation |
| `AttributionAnalyzer` | `brinson_attribution()`, `factor_attribution()` | Performance attribution |
| `RiskMonitor` | `update()`, `get_dashboard_data()` | Real-time risk monitoring |
| `ShockPropagationEngine` | `propagate(shock, portfolio)` | Factor shock propagation |
| `DrawdownAnalyzer` | `analyze(equity_curve)` | Drawdown event analysis |
| `RecoveryEstimator` | `estimate(drawdown, equity)` | Recovery path estimation |
| `ScenarioBuilder` | `build(shocks)` | Custom scenario construction |

### Unified Risk (`src/unified_risk/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `RiskContext` | `assess(ticker, direction, positions, ...)`, `record_pnl()`, `reset_daily()` | 7-check unified assessment |
| `CorrelationGuard` | `compute_matrix(returns)`, `check_new_trade()`, `get_portfolio_concentration_score()` | Correlation cluster guard |
| `VaRPositionSizer` | `compute_var(returns)`, `size_position()`, `compute_portfolio_var()` | VaR-based dynamic sizing |
| `RegimeRiskAdapter` | `set_regime()`, `get_limits()`, `adjust_max_positions()`, `adjust_position_size()` | Regime-adaptive limits |

## Common patterns

### The 7 Unified Risk Checks

The `RiskContext.assess()` method runs these checks in order:

| # | Check | Rejects When |
|---|---|---|
| 1 | Kill switch | Kill switch is active |
| 2 | Circuit breaker | Circuit breaker is OPEN |
| 3 | Daily loss limit | Daily loss >= `max_daily_loss_pct` (default 10%) |
| 4 | Max positions | Open positions >= regime-adjusted maximum |
| 5 | Single stock concentration | Ticker exposure >= `max_single_stock_pct` (default 15%) |
| 6 | Correlation guard | Pairwise correlation > 0.80 or cluster too large |
| 7 | VaR sizing | Computes max position size from VaR budget |

### Regime-Adaptive Limits

| Regime | Position Size Multiplier | Max Positions Adjust |
|---|---|---|
| `bull` | 1.0x (full size) | No reduction |
| `sideways` | 0.8x | -1 position |
| `bear` | 0.5x | -3 positions |
| `crisis` | 0.25x | -5 positions |

### Pre-Built Historical Scenarios

| Scenario | Period | Market Impact |
|---|---|---|
| COVID Crash | Feb-Mar 2020 | -34% S&P 500 |
| 2022 Bear Market | Jan-Oct 2022 | -25% S&P 500 |
| Global Financial Crisis | Sep 2008-Mar 2009 | -57% S&P 500 |
| Dot-Com Crash | Mar 2000-Oct 2002 | -78% NASDAQ |
| Flash Crash | May 6, 2010 | -9.2% intraday |

### Key Configuration Defaults

```python
RiskContextConfig(
    max_daily_loss_pct=10.0,
    max_concurrent_positions=10,
    max_single_stock_pct=15.0,
    max_sector_pct=30.0,
)
CorrelationConfig(
    max_pairwise_correlation=0.80,
    max_cluster_size=4,
    lookback_days=60,
    min_data_points=20,
    cluster_threshold=0.70,
)
VaRConfig(
    confidence_level=0.95,
    max_portfolio_var_pct=2.0,
    max_position_var_pct=0.5,
    lookback_days=252,
    use_cvar=True,
    decay_factor=0.97,
)
```

### Typical Risk Pipeline

1. Compute `PortfolioRiskMetrics` daily for dashboard
2. Before each trade, call `RiskContext.assess()` for unified validation
3. Use `VaRPositionSizer` to dynamically cap position sizes
4. Monitor `CorrelationGuard` to prevent cluster concentration
5. Run weekly stress tests with `StressTestEngine`
6. Apply `DrawdownProtection` rules when drawdown thresholds are hit
7. `RegimeRiskAdapter` auto-adjusts limits based on current market regime
