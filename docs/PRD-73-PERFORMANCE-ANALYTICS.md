# PRD-73: Performance Analytics

## Overview
Comprehensive performance attribution and analytics system with Brinson-Fachler decomposition, factor attribution, Fama-French models, geographic attribution, risk-adjusted metrics, multi-period linking, tear sheet generation, and benchmark comparison.

## Components

### 1. Brinson Analysis (`src/attribution/brinson.py`)
- **BrinsonAnalyzer** — Brinson-Fachler sector-level decomposition with allocation, selection, and interaction effects

### 2. Factor Attribution (`src/attribution/factor_attribution.py`)
- **FactorAnalyzer** — Factor-based return attribution across standard factors (market, value, momentum, quality, growth, volatility, size)

### 3. Benchmark Comparison (`src/attribution/benchmark.py`)
- **BenchmarkAnalyzer** — Active return, tracking error, information ratio, active share, up/down capture, beta, alpha, correlation

### 4. Metrics Calculator (`src/attribution/metrics.py`)
- **MetricsCalculator** — Total return, annualized return, volatility, Sharpe, Sortino, Calmar, max drawdown, VaR, CVaR, skewness, kurtosis, win rate

### 5. Tear Sheet Generator (`src/attribution/tearsheet.py`)
- **TearSheetGenerator** — Complete reports with metrics, benchmark, Brinson, factors, monthly returns, drawdowns

### 6. Risk Decomposition (`src/attribution/risk.py`)
- **RiskDecomposer** — Position-level risk contribution, marginal risk, sector decomposition, tracking error decomposition

### 7. Performance Contribution (`src/attribution/performance.py`)
- **PerformanceContributor** — Position-level return contributions, top/bottom contributors, sector contributions, cumulative analysis
- **PositionContribution** / **ContributionSummary** — Hit rate, concentration metrics

### 8. Multi-Period Attribution (`src/attribution/multi_period.py`)
- **MultiPeriodAttribution** — Multi-period linked attribution with cumulative effects across time periods

### 9. Fama-French Analysis (`src/attribution/fama_french.py`)
- **FamaFrenchAnalyzer** — 3-factor and 5-factor model fitting, alpha summary, model comparison

### 10. Geographic Attribution (`src/attribution/geographic.py`)
- **GeographicAnalyzer** — Country/region-level attribution with currency effects, top/bottom contributors

### 11. Risk-Adjusted Metrics (`src/attribution/risk_adjusted.py`)
- **RiskAdjustedAnalyzer** — Composite score, M-squared, Omega ratio, pain ratio, Martin ratio, tail ratio, strategy comparison

### 12. Configuration (`src/attribution/config.py`)
- **AttributionMethod** — BRINSON_FACHLER, FACTOR, RETURNS_BASED
- **AttributionLevel** — SECTOR, INDUSTRY, SECURITY
- **BenchmarkType** — INDEX, CUSTOM, BLENDED, CASH
- **TimePeriod** — MTD, QTD, YTD, 1M, 3M, 6M, 1Y, 3Y, 5Y, INCEPTION
- **RiskMetricType** — VOLATILITY, SHARPE_RATIO, SORTINO_RATIO, CALMAR_RATIO, TREYNOR_RATIO, INFORMATION_RATIO, TRACKING_ERROR, MAX_DRAWDOWN, BETA, ALPHA
- **STANDARD_FACTORS** — market, value, momentum, quality, growth, volatility, size
- **COMMON_BENCHMARKS** — SPY, QQQ, IWM, AGG, EFA, 60_40

## Database Tables
- `attribution_reports` — Stored attribution analysis results (migration 016)
- `benchmark_definitions` — Benchmark configurations (migration 016)
- `perf_snapshots` — Performance metric captures (migration 016)
- `tear_sheets` — Generated tear sheet data (migration 016)
- `risk_decompositions` — Position-level risk contribution (migration 037)
- `performance_contributions` — Position return contributions (migration 037)
- `linked_attribution` — Multi-period linked attribution results (migration 045)
- `ff_model_results` — Fama-French model results (migration 045)
- `geographic_attribution` — Geographic/country-level attribution (migration 045)
- `risk_adjusted_metrics` — Risk-adjusted performance metrics (migration 045)

## Dashboard
10-tab Streamlit dashboard (`app/pages/attribution.py`):
1. **Summary** — Key metrics and benchmark comparison
2. **Brinson Attribution** — Sector-level allocation/selection effects
3. **Factor Attribution** — Factor exposures and contributions
4. **Risk Decomposition** — Position-level risk breakdown
5. **Performance Contribution** — Top/bottom contributors
6. **Tear Sheet** — Full performance report
7. **Multi-Period Attribution** — Linked attribution across periods
8. **Fama-French Analysis** — 3/5-factor model results
9. **Geographic Attribution** — Country/region-level breakdown
10. **Risk-Adjusted Metrics** — Composite scores and strategy comparison

## Test Coverage
112 tests across 3 test files:
- `tests/test_attribution.py` — Core metrics, Brinson, factor, benchmark, tear sheet
- `tests/test_attribution_ext.py` — Multi-period, Fama-French, geographic, risk-adjusted
- `tests/test_attribution_extended.py` — Risk decomposition, performance contribution, integration
