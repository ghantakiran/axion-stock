# PRD-56: Cross-Asset Signal Generation

## Overview
Analyzes intermarket relationships across equities, bonds, commodities, and
currencies to generate cross-asset momentum, mean-reversion, and composite
trading signals with lead-lag detection.

## New Components

### 1. Intermarket Analyzer (`intermarket.py`)
- Rolling correlation between asset pairs
- Correlation regime detection (normal, decoupled, crisis)
- Relative strength analysis across asset classes
- Divergence detection (when correlations break)
- Beta estimation between asset classes

### 2. Lead-Lag Detector (`leadlag.py`)
- Cross-correlation at multiple lags
- Granger-style predictive relationship testing
- Optimal lag identification per pair
- Lead-lag stability analysis over time
- Signal extraction from leading indicators

### 3. Cross-Asset Momentum (`momentum.py`)
- Time-series momentum per asset class
- Cross-sectional momentum (rank-based)
- Mean-reversion signals from Z-scores
- Carry signals (yield differential)
- Trend strength scoring

### 4. Composite Signal Generator (`signals.py`)
- Weighted combination of intermarket signals
- Confidence scoring based on signal agreement
- Regime-conditional signal filtering
- Signal strength classification
- Historical signal performance tracking

## Data Models
- AssetPairCorrelation: rolling correlation with regime
- LeadLagResult: optimal lag with significance
- MomentumSignal: per-asset momentum/mean-reversion
- CrossAssetSignal: composite signal with components

## Technical Details
- New src/crossasset/ module
- NumPy/SciPy for correlation and statistical tests
- Dataclass-based models
- Integration with regime detection module
