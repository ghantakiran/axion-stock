# PRD-44: Pairs Trading

## Overview
Statistical pairs trading system providing cointegration testing (Engle-Granger),
spread analysis with z-score signals, half-life estimation, pair selection/scoring,
and trade signal generation.

## Components

### 1. Cointegration Tester (`src/pairs/cointegration.py`)
- **Engle-Granger Test**: Two-step residual-based cointegration test
- **Hedge Ratio**: OLS regression-based hedge ratio computation
- **ADF Test**: Augmented Dickey-Fuller on spread residuals
- **Correlation Filter**: Pre-filter pairs by minimum correlation

### 2. Spread Analyzer (`src/pairs/spread.py`)
- **Spread Computation**: Price spread with hedge ratio adjustment
- **Z-Score**: Normalized spread distance from mean
- **Half-Life**: Mean-reversion speed (Ornstein-Uhlenbeck)
- **Hurst Exponent**: Mean-reversion tendency measure

### 3. Pair Selector (`src/pairs/selector.py`)
- **Universe Screening**: Test all pairs in a universe
- **Scoring**: Multi-factor pair quality score
- **Ranking**: Sorted by cointegration strength, half-life, spread stability
- **Filtering**: Min correlation, max half-life, p-value threshold

## Data Models
- `CointegrationResult`: Test statistic, p-value, hedge ratio, is_cointegrated
- `SpreadAnalysis`: Z-score, half-life, hurst exponent, current signal
- `PairScore`: Composite scoring with component breakdown
- `PairSignal`: Entry/exit signals with position sizing
- `PairTrade`: Active pair trade tracking

## Configuration
- `CointegrationConfig`: P-value threshold, min correlation, lookback window
- `SpreadConfig`: Z-score entry/exit thresholds, half-life bounds
- `SelectorConfig`: Scoring weights, max pairs, min score threshold

## Database Tables
- `cointegration_tests`: Cointegration test results
- `spread_snapshots`: Spread analysis snapshots
- `pair_scores`: Pair quality scores
- `pair_signals`: Generated trading signals

## Dashboard
4-tab Streamlit page: Cointegration, Spread, Pair Selection, Signals
