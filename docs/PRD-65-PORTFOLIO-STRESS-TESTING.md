# PRD-65: Portfolio Stress Testing

## Overview
Comprehensive portfolio stress testing framework with shock propagation analysis, drawdown tracking, recovery estimation, and custom scenario building.

## Components

### 1. Shock Propagation Engine (`src/risk/shock_propagation.py`)
- **FactorShock** — Individual factor shock with severity classification
- **PropagatedShock** — Per-position shock result with direct/indirect decomposition
- **PortfolioShockResult** — Aggregated portfolio shock with amplification metrics
- **ContagionPath** — Shock transmission path between correlated factors
- **ShockPropagationEngine** — Multi-hop shock propagation with decay, contagion tracing, sensitivity analysis
- 22 default factor correlations (market, growth, value, momentum, quality, size, volatility, interest_rate, credit_spread, oil, dollar, etc.)

### 2. Drawdown Analysis (`src/risk/drawdown_analysis.py`)
- **DrawdownEvent** — Single drawdown episode with severity classification (minor/moderate/significant/severe)
- **DrawdownMetrics** — Comprehensive stats: max DD, avg DD, Calmar ratio, Ulcer index, % time underwater, risk score
- **UnderwaterCurve** — Time-series drawdown tracking with running maximum
- **ConditionalDrawdown** — CVaR 1%/5% tail risk metrics
- **DrawdownAnalyzer** — Computes underwater curves, identifies events, compares across assets

### 3. Recovery Estimation (`src/risk/recovery_estimation.py`)
- **RecoveryEstimate** — Expected days to recovery with probability bands (30d/90d/180d)
- **RecoveryPath** — Simulated/historical recovery trajectory
- **RecoveryAnalysis** — Combined analytical + Monte Carlo + historical analysis
- **BreakevenAnalysis** — Required gain, compounding effect, days to breakeven
- **RecoveryEstimator** — Multi-method estimation (analytical drift-diffusion, Monte Carlo, historical matching)

### 4. Scenario Builder (`src/risk/scenario_builder.py`)
- **MacroShock** — Macro variable shock component (rates, inflation, growth, dollar)
- **SectorRotation** — Sector-specific impact specification
- **CorrelationShift** — Regime change with contagion detection
- **CustomScenario** — Full scenario with severity scoring, component counting
- **ScenarioTemplate** — Pre-built templates (Recession, Rate Shock, Inflation, Tech Correction, Geopolitical, Credit Crisis, Stagflation)
- **ScenarioBuilder** — Template-based, macro-derived, and combined scenario construction with validation

## Database Tables
- `stress_test_runs` — Stress test run history with parameters and results
- `shock_propagation_results` — Shock propagation results per scenario
- `drawdown_metrics_snapshots` — Periodic drawdown metric snapshots
- `recovery_estimates` — Recovery time predictions
- `custom_stress_scenarios` — User-defined scenario configurations

## Dashboard
5-tab Streamlit dashboard (`app/pages/stress_testing.py`):
1. **Shock Propagation** — Factor shock input, propagation results, contagion visualization
2. **Drawdown Analysis** — Underwater curve, drawdown events, risk metrics
3. **Recovery Estimation** — Analytical/Monte Carlo estimates, breakeven analysis
4. **Scenario Builder** — Template-based and custom scenario construction
5. **Sensitivity** — Factor sensitivity analysis with heatmap

## Test Coverage
46 tests in `tests/test_stress_testing.py` covering all components.
