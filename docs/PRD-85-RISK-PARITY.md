# PRD-85: Risk Parity & Volatility Targeting

## Overview
Risk parity portfolio construction system with equal risk contribution optimization, volatility targeting, drawdown-based risk budgeting, hierarchical risk parity, cross-asset risk allocation, and pre-built portfolio templates.

## Components

### 1. Risk Parity Optimizer (`src/optimizer/objectives.py`)
- **RiskParityOptimizer** — Equal risk contribution optimization via SLSQP
- Iterative algorithm matching marginal risk contributions to targets
- Flexible weight bounds (default 1%-30% per asset)
- `get_risk_contributions()` — Per-asset risk contribution computation
- **MeanVarianceOptimizer** — Max Sharpe, min variance, efficient frontier
- **HRPOptimizer** — Hierarchical Risk Parity (correlation-based clustering, no matrix inversion)

### 2. Position Sizer (`src/execution/position_sizer.py`)
- **PositionSizer.risk_parity()** — Equal risk contribution at position level
- **PositionSizer.volatility_targeted()** — Inverse volatility weighting with target vol
- Additional methods: equal_weight, score_weighted, kelly_criterion
- Constraints: max position 15%, max sector 35%, min $500, 2% cash buffer

### 3. Drawdown Risk Budgeter (`src/tailrisk/budgeting.py`)
- **DrawdownRiskBudgeter** — Drawdown-based risk budget allocation
- Three methods: EQUAL, PROPORTIONAL, INVERSE_VOL
- Budget utilization tracking and weight recommendations
- Allocation based on max drawdown history

### 4. Cross-Asset Optimizer (`src/multi_asset/cross_asset.py`)
- **CrossAssetOptimizer.risk_budget_allocation()** — Multi-asset risk budgeting
- Iterative risk parity algorithm (100 iterations) across asset classes
- Covariance matrix building, risk contribution by asset class
- Support: equities, bonds, commodities, crypto, futures, international

### 5. Unified Risk Manager (`src/multi_asset/risk.py`)
- **UnifiedRiskManager** — Cross-asset VaR, risk contribution, margin monitoring
- Correlation regime detection, currency risk analysis

### 6. Portfolio Templates (`src/optimizer/templates.py`)
- 8 pre-built templates: risk_parity, all_weather, aggressive_alpha, balanced_factor, quality_income, momentum_rider, value_contrarian, low_volatility

### 7. Portfolio Analytics (`src/optimizer/analytics.py`)
- **PortfolioAnalytics** — Risk contribution calculation, portfolio X-ray
- **WhatIfAnalyzer** — Scenario analysis with trade impact

### 8. Tail Risk (`src/tailrisk/`)
- **CVaRCalculator** — Historical, parametric, Monte Carlo CVaR
- **HedgeConstructor** — Hedge portfolio construction, put strategies
- **TailDependenceAnalyzer** — Tail correlation, contagion scoring

### 9. Regime-Aware Allocation (`src/regime/allocation.py`)
- **RegimeAllocator** — Per-regime target weights (Bull/Bear/Sideways/Crisis)
- Blended weights using regime probabilities, smooth transitions

## Database Tables
- Risk system tables (migration 006), risk management (018), performance attribution (037)
- Credit risk (039), liquidity risk (040/048/064), tail risk hedging (043)
- `risk_parity_snapshots` — Risk parity allocation snapshots (migration 085)
- `vol_target_history` — Volatility targeting adjustment log (migration 085)

## Dashboards
- `app/pages/risk.py` — Enterprise risk dashboard (status, metrics, stress tests, concentration)
- `app/pages/volatility.py` — Volatility analysis
- `app/pages/tailrisk.py` — Tail risk dashboard
- `app/pages/liquidity_risk.py` — Liquidity risk dashboard

## Test Coverage
173 tests across 3 test files:
- `tests/test_optimizer.py` — 71 tests (MVO, RiskParity, HRP, Black-Litterman, constraints, tax, templates, analytics, what-if)
- `tests/test_tailrisk.py` — 43 tests (CVaR, drawdown budgeting, hedge construction, tail dependence)
- `tests/test_multi_asset.py` — 59 tests (cross-asset optimization, risk budgeting, unified risk, crypto/futures/international)
