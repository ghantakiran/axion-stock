# PRD-18: Options Analytics Platform

## Overview

Full-featured options analytics platform with Black-Scholes, binomial tree, and Monte
Carlo pricing models, volatility surface construction with SVI parametrization, 15
pre-built strategy templates with payoff diagrams, unusual activity detection, and
options-specific backtesting engine.

---

## Components

### 1. Options Pricing Engine
- Black-Scholes: European option pricing with full Greeks (delta, gamma, theta, vega, rho)
- Binomial Tree: American option pricing with early exercise support (configurable steps)
- Monte Carlo: Path-dependent pricing via Geometric Brownian Motion (100k simulations)
- Implied Volatility solver: Newton-Raphson method with configurable convergence
- Unified pricing interface with automatic model selection

### 2. Volatility Surface
- Surface construction from options chain data or pre-computed IVs
- SVI parametrization fitting (5 parameters: a, b, rho, m, sigma)
- Grid interpolation across moneyness and DTE dimensions
- Vol analytics: ATM IV, 25-delta skew, term structure, IV percentile/rank
- Realized volatility (30/60-day) and HV-IV spread
- Volatility cone with rolling window statistics

### 3. Strategy Builder
- 15 pre-built strategies: Long Call/Put, Covered Call, Cash-Secured Put, Bull/Bear
  Spreads, Iron Condor, Iron Butterfly, Straddle, Strangle, Calendar/Diagonal Spreads,
  Jade Lizard, Ratio Spread, Custom
- Payoff diagram generation with breakeven calculation
- Probability of Profit via Monte Carlo simulation (100k paths)
- Expected value and risk/reward ratio computation
- Net Greeks aggregation across legs
- Capital requirement and annualized return calculation
- Side-by-side strategy comparison

### 4. Unusual Activity Detection
- Volume spike detection (5x average threshold)
- Open interest surge detection (3x threshold)
- IV spike detection (IV rank > 80%)
- Large block trade identification (>= 1,000 contracts)
- Put/call ratio skew analysis (bullish < 0.3, bearish > 2.0)
- Near-expiry volume anomalies
- Signal severity classification (low/medium/high)
- Symbol-level sentiment summarization (bullish/bearish/neutral)

### 5. Options Backtesting
- Strategy-specific backtesting (short put, iron condor, custom)
- Entry rules: DTE range, IV rank minimum, day-of-week filters, price bounds
- Exit rules: profit target (50%), stop loss (200%), min DTE exit, max hold days
- Day-by-day simulation with theta decay and price movement
- Delta-targeted strike selection via bisection search
- Result statistics: win rate, profit factor, Sharpe, max drawdown

### 6. Database Tables
- `options_strategies`: Saved strategy analyses with legs and metrics
- `vol_surfaces`: Stored volatility surface snapshots
- `options_activity`: Unusual activity signal records
- `options_backtest_results`: Options backtest run results and trades

### 7. Success Metrics
- Black-Scholes pricing: <1ms per option
- Monte Carlo pricing: <2s for 100k paths
- IV solver convergence: <50 iterations
- Vol surface build: <5s from chain data
- Strategy analysis: <3s with PoP calculation

---

*Priority: P1 | Phase: 9*
