# PRD-57: Tail Risk Hedging

## Overview
Comprehensive tail risk management framework including expected shortfall
(CVaR) computation, tail dependence analysis, hedge construction using
options/VIX, and drawdown-based risk budgeting.

## New Components

### 1. CVaR Calculator (`cvar.py`)
- Historical CVaR (expected shortfall) at configurable confidence
- Parametric CVaR (Gaussian and Cornish-Fisher)
- Conditional tail expectation decomposition by position
- Multi-horizon CVaR scaling
- CVaR contribution per asset

### 2. Tail Dependence Analyzer (`dependence.py`)
- Lower/upper tail dependence coefficients
- Extreme co-movement detection
- Tail correlation vs normal correlation comparison
- Conditional drawdown correlation
- Tail risk contagion scoring

### 3. Hedge Constructor (`hedging.py`)
- Protective put sizing (cost vs protection tradeoff)
- VIX call hedge sizing
- Tail hedge ratio optimization
- Hedge cost estimation
- Hedge effectiveness scoring

### 4. Drawdown Risk Budgeter (`budgeting.py`)
- Maximum drawdown estimation (historical, parametric)
- Conditional drawdown-at-risk (CDaR)
- Drawdown-based position sizing
- Risk budget allocation across assets
- Drawdown recovery analysis

## Data Models
- CVaRResult: expected shortfall with decomposition
- TailDependence: tail correlation metrics
- HedgeRecommendation: hedge instrument and sizing
- DrawdownBudget: per-asset drawdown risk allocation

## Technical Details
- New src/tailrisk/ module
- NumPy/SciPy for tail statistics and optimization
- Dataclass-based models
- Integration with existing risk and options modules
