# PRD-51: Portfolio Attribution

## Overview
Portfolio attribution module providing Brinson-Fachler return attribution,
risk-based decomposition, factor attribution, and performance contribution
analysis for understanding sources of portfolio returns and risk.

## Components

### 1. Brinson-Fachler Attribution (`brinson.py`)
- Allocation effect: (Wp - Wb) * (Rb - Rb_total)
- Selection effect: Wb * (Rp - Rb)
- Interaction effect: (Wp - Wb) * (Rp - Rb)
- Sector-level and total portfolio attribution
- Multi-period linking support

### 2. Risk Decomposition (`risk.py`)
- Component risk contribution (Euler decomposition)
- Marginal risk contribution
- Percentage of total risk by position/sector
- Covariance-based and VaR-based decomposition
- Sector-level risk aggregation

### 3. Factor Attribution (`factor.py`)
- OLS regression-based factor decomposition
- Alpha and residual risk isolation
- Factor exposure (beta) estimation with t-statistics
- CAPM, Fama-French 3/5 factor model support
- R-squared and model diagnostics

### 4. Performance Contribution (`performance.py`)
- Position-level return contribution (weight * return)
- Top/bottom contributor ranking
- Cumulative contribution over time
- Relative contribution vs benchmark
- Sector-level aggregation

## Data Models
- BrinsonAttribution: sector-level attribution effects
- RiskDecomposition: per-position risk contribution
- FactorAttribution: per-factor return attribution
- FactorResult: full model output (alpha, R², factors)
- PerformanceContribution: position contribution
- AttributionSummary: portfolio-level summary

## Technical Details
- In-memory storage pattern
- NumPy for matrix operations (covariance, OLS)
- Dataclass-based models
- Configurable via dataclass configs

## Migration
- Table: brinson_attributions
- Table: risk_decompositions
- Table: factor_attributions
- Table: performance_contributions
