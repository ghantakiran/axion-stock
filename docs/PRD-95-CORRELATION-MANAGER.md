# PRD-95: Correlation Manager

## Overview
Correlation analysis system with multi-method matrix computation, regime-aware correlation detection, rolling correlation tracking, portfolio diversification scoring, and eigenvalue decomposition.

## Components

### 1. Correlation Engine (`src/correlation/engine.py`)
- **CorrelationEngine** — Core computation
- `compute_matrix()` — Pearson, Spearman, Kendall correlation matrices
- `get_top_pairs()` / `get_highly_correlated()` — Pair ranking and threshold filtering
- `compute_rolling()` — Time-series correlations with fixed/exponential/expanding windows
- `compute_eigenvalues()` — Matrix decomposition for stability analysis

### 2. Regime Detector (`src/correlation/regime.py`)
- **CorrelationRegimeDetector** — 4-state regime classification
- Regimes: LOW, NORMAL, HIGH, CRISIS (based on average correlation)
- Significant shift detection, days-in-regime tracking
- Regime history with transition logging

### 3. Diversification Analyzer (`src/correlation/diversification.py`)
- **DiversificationAnalyzer** — Portfolio diversification assessment
- Diversification ratio, effective number of bets (ENB, entropy-based)
- Concentrated pair identification, custom weights/volatilities
- Multi-portfolio comparison and ranking

### 4. Configuration (`src/correlation/config.py`)
- CorrelationMethod (PEARSON/SPEARMAN/KENDALL)
- RegimeType (LOW/NORMAL/HIGH/CRISIS)
- DiversificationLevel (POOR/FAIR/GOOD/EXCELLENT)
- WindowType (FIXED/EXPANDING/EXPONENTIAL)
- CorrelationConfig, RollingConfig, RegimeConfig, DiversificationConfig

### 5. Models (`src/correlation/models.py`)
- **CorrelationMatrix** — N×N matrix with avg/max/min correlation properties
- **CorrelationPair** — Individual pair with stability metric
- **RollingCorrelation** — Time series with percentile tracking
- **CorrelationRegime** — Regime classification with change detection
- **DiversificationScore** — Portfolio assessment with ratio, effective bets, pair flags

## Database Tables
- `correlation_matrices` — Matrix snapshots with JSON data (migration 023)
- `correlation_pairs` — Pairwise correlation records (migration 023)
- `correlation_regimes` — Regime history (migration 023)
- `diversification_scores` — Portfolio assessments (migration 023)
- `correlation_breakdowns` — Regime-specific correlation breakdowns (migration 095)
- `correlation_alerts` — Correlation shift alert log (migration 095)

## Dashboard
Streamlit dashboard (`app/pages/correlation.py`) with 4 tabs:
1. **Matrix** — Heatmap with avg/max/min metrics
2. **Pairs** — Most/least correlated pairs, high correlation flags (>0.70)
3. **Regime** — Current regime, dispersion, transition history
4. **Diversification** — Ratio, effective bets, concentrated pairs

## Test Coverage
54 tests in `tests/test_correlation.py` covering config (6), models (11), CorrelationEngine (11), CorrelationRegimeDetector (9), DiversificationAnalyzer (11), integration (2), module imports (1).
