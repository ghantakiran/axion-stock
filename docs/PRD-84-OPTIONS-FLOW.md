# PRD-84: Options Flow Analysis

## Overview
Comprehensive options analytics platform with pricing engines, volatility surface modeling, chain analysis, flow detection, unusual activity scanning, strategy building, and options backtesting.

## Components

### 1. Options Pricing Engine (`src/options/pricing.py`)
- **OptionsPricingEngine** — Black-Scholes, binomial tree, Monte Carlo pricing
- Full Greeks: Delta, Gamma, Theta, Vega, Rho
- Newton-Raphson implied volatility solver
- European and American option pricing
- Graceful degradation when scipy unavailable

### 2. Volatility Surface Builder (`src/options/volatility.py`)
- **VolatilitySurfaceBuilder** — IV surface construction from chain data
- SVI (Stochastic Volatility Inspired) parametrization fitting
- Grid interpolation across moneyness and DTE
- IV percentile, IV rank, HV-IV spread analysis
- Volatility cone with rolling windows, term structure analysis

### 3. Chain Analyzer (`src/options/chain.py`)
- **ChainAnalyzer** — Options chain metrics and analysis
- Put-call ratio (volume-based and OI-based)
- Max pain strike calculation
- IV skew (OTM put IV - OTM call IV)
- ATM IV extraction, chain summary metrics
- Contract filtering by minimum volume/OI

### 4. Flow Detector (`src/options/flow.py`)
- **FlowDetector** — Options flow classification and detection
- Flow types: SWEEP, BLOCK, SPLIT, NORMAL
- Activity levels: NORMAL, ELEVATED, UNUSUAL, EXTREME
- Net premium sentiment (BULLISH/BEARISH/NEUTRAL)
- Multi-factor activity scoring (40% vol/OI, 30% premium, 30% volume)

### 5. Unusual Activity Detector (`src/options/activity.py`)
- **UnusualActivityDetector** — 6 signal types
- VOLUME_SPIKE (5x average), OI_SURGE (3x), IV_SPIKE (80th percentile)
- LARGE_BLOCK (1000+ contracts), SWEEP (multi-exchange), PUT_CALL_SKEW
- Severity levels (low/medium/high), symbol-level sentiment summarization

### 6. Strategy Builder (`src/options/strategies.py`)
- **StrategyBuilder** — 15 pre-built strategies
- Long Call/Put, Covered Call, Cash-Secured Put, Bull/Bear Spreads
- Iron Condor, Iron Butterfly, Straddle, Strangle
- Calendar Spread, Diagonal Spread, Jade Lizard, Ratio Spread, Custom
- Payoff diagrams, probability of profit (Monte Carlo 100k sims)
- Expected value, risk/reward ratio, net Greeks aggregation

### 7. Options Backtester (`src/options/backtest.py`)
- **OptionsBacktester** — Strategy backtesting engine
- Entry rules: DTE range, IV rank minimum, day-of-week filters, price bounds
- Exit rules: profit target (50%), stop loss (200%), min DTE exit, max hold days
- Day-by-day simulation with theta decay, delta-targeted strike selection

### 8. Configuration (`src/options/config.py`)
- **FlowType**, **ActivityLevel**, **Sentiment** enums
- 7 config dataclasses: PricingConfig, VolatilityConfig, StrategyConfig, ActivityConfig, BacktestConfig, ChainConfig, FlowConfig

### 9. Models (`src/options/models.py`)
- **OptionGreeks** — Delta, Gamma, Theta, Vega, Rho
- **OptionContract** — Strike, expiry, type, bid/ask, volume, OI, IV, Greeks; properties: mid, spread, vol_oi_ratio
- **ChainSummary** — Aggregate metrics, PCR, max pain, IV skew, sentiment
- **OptionsFlow** — Flow type, premium, side, sentiment
- **UnusualActivity** — Signal type, severity, details

## Database Tables
- `options_chains` — Chain snapshots (migration 008)
- `options_trades` — Trade records (migration 008)
- `iv_surfaces` — IV surface data (migration 008)
- `options_activity` — Activity records (migration 008/019)
- `options_backtests` — Backtest configs (migration 008)
- `options_strategies` — Strategy definitions (migration 019)
- `vol_surfaces` — Volatility surface snapshots (migration 019)
- `options_backtest_results` — Backtest results (migration 019)
- `options_greeks` — Greeks snapshots (migration 029)
- `options_chain_snapshots` — Chain analysis snapshots (migration 029)
- `options_flow` — Flow records (migration 029)
- `options_unusual_activity` — Unusual activity alerts (migration 029)
- `options_flow_aggregates` — Aggregated flow analytics (migration 084)
- `options_smart_alerts` — Alert configuration and history (migration 084)

## Dashboards
- `app/pages/options.py` — Options pricing calculator, strategy builder, vol surface
- `app/pages/options_chain.py` — Chain overview, Greeks, flow, unusual activity

## Test Coverage
86 tests across 2 test files:
- `tests/test_options.py` — 34 tests (pricing engine, Greeks, binomial, Monte Carlo, IV solver, strategies, volatility, activity detector, backtester, config)
- `tests/test_options_chain.py` — 52 tests (config, models, ChainAnalyzer PCR/max pain/IV skew/Greeks/sentiment, FlowDetector classification/sentiment/detection/history, integration)

Additional related test files:
- `tests/test_volatility.py` — Volatility surface construction and SVI fitting
- `tests/test_volatility_surface.py` — Surface interpolation and term structure
- `tests/test_crypto_options.py` — Crypto-specific options tests
