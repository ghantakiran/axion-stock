# PRD-17: Portfolio Risk Management Engine

## Overview

Comprehensive portfolio risk management system with VaR/CVaR computation (historical,
parametric, Monte Carlo), stress testing against historical and hypothetical scenarios,
drawdown protection with recovery protocols, pre-trade risk validation, real-time
monitoring, and unified risk dashboard.

---

## Components

### 1. Risk Metrics Calculator
- Portfolio-level: Sharpe, Sortino, Calmar, Information Ratio, Beta, Volatility
- Position-level: unrealized P&L, drawdown, distance to stop, risk contribution
- Concentration: Herfindahl index, top-5 weight, sector exposure, correlation clusters
- Rolling metrics with configurable window (default 60 days)
- Return distribution statistics (skewness, kurtosis)

### 2. Value at Risk (VaR/CVaR)
- Three methodologies: Historical Simulation, Parametric, Monte Carlo
- Confidence levels: 95% and 99%
- Multi-day horizon scaling
- Component VaR (contribution by position)
- Marginal VaR (impact of position removal)
- Expected Shortfall (CVaR) at all confidence levels

### 3. Stress Testing
- 8 historical scenarios (COVID Crash, GFC, Dot-Com, Flash Crash, etc.)
- 6 hypothetical scenarios (Rate Shock, Oil Spike, Tech Correction, etc.)
- Custom shock scenario builder
- Reverse stress testing (find conditions causing target loss)
- Position-level and sector-level impact analysis

### 4. Drawdown Protection
- Portfolio-level drawdown monitoring with tiered thresholds (warning/reduce/emergency)
- Position-level stop-loss enforcement
- Daily loss limit with 24-hour cooldown
- Recovery protocol state machine: Normal → Cooldown → Scaling-In → Reduced Size
- Configurable position size multipliers during recovery

### 5. Pre-Trade Risk Validation
- 11 checks: buying power, position size, sector concentration, top-5 concentration,
  drawdown state, daily loss limit, PDT compliance, ADV participation, stock volatility,
  correlation with existing positions, portfolio beta exposure
- Block vs. warning severity levels
- Order context validation with full portfolio state

### 6. Real-Time Monitor
- Unified risk status: NORMAL, WARNING, ELEVATED, CRITICAL
- Alert generation with severity levels
- Dashboard data aggregation (metrics, VaR, concentration, stress tests)
- Limit utilization tracking
- Trading status and recovery state monitoring
- Callback system for alert actions

### 7. Risk Attribution
- Brinson attribution (allocation, selection, interaction effects)
- Factor attribution (market, value, momentum, quality, growth, volatility, technical)
- Regression-based factor exposure estimation
- Alpha (residual) calculation

### 8. Database Tables
- `risk_snapshots`: Point-in-time risk metric captures
- `risk_alerts`: Historical alert records
- `stress_test_results`: Stored stress test outputs
- `risk_limits`: Configurable risk limit definitions

### 9. Success Metrics
- VaR calculation: <2s for 500-position portfolio
- Stress test suite: <5s for all 14 scenarios
- Pre-trade validation: <100ms per order check
- Drawdown detection latency: <1s from price update

---

*Priority: P0 | Phase: 5*
