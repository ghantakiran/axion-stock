# PRD-38: Volatility Analysis

## Overview
Comprehensive volatility analysis system providing historical and implied volatility estimation,
term structure analysis, volatility surface/smile modeling, and vol regime detection.

## Components

### 1. Volatility Engine (`src/volatility/engine.py`)
- **Historical volatility**: Close-to-close standard deviation with configurable windows
- **EWMA volatility**: Exponentially weighted with decay parameter (lambda)
- **Parkinson volatility**: High-low range-based estimator (more efficient than close-to-close)
- **Garman-Klass volatility**: OHLC-based estimator (most efficient single-day estimator)
- **Volatility cone**: Percentile bands across multiple windows for context
- **Implied vs realized**: Vol risk premium computation

### 2. Surface Analyzer (`src/volatility/surface.py`)
- **Volatility smile**: IV across strikes for a single tenor
- **Volatility surface**: Full strike x tenor IV grid
- **Skew**: 25-delta put/call skew measurement
- **Butterfly**: 25-delta butterfly spread (wing convexity)
- **Term structure**: IV across tenors at ATM, contango/backwardation detection

### 3. Regime Detector (`src/volatility/regime.py`)
- **Regime classification**: LOW / NORMAL / HIGH / EXTREME based on z-score
- **Percentile ranking**: Current vol vs historical distribution
- **Regime persistence**: Days in current regime tracking
- **Transition detection**: Regime change signals

## Data Models
- `VolEstimate` — Single volatility measurement with method, window, percentile
- `TermStructurePoint` — One tenor on the term structure curve
- `TermStructure` — Full term structure with contango/backwardation classification
- `VolSmilePoint` — Single strike point on the smile
- `VolSurface` — Complete strike x tenor surface grid
- `VolRegimeState` — Current regime classification with context

## Database Tables (Migration 024)
- `vol_estimates` — Historical volatility computations
- `vol_surfaces` — Stored surface snapshots
- `vol_regimes` — Regime history
- `vol_term_structures` — Term structure snapshots

## Configuration
- `VolMethod` enum: HISTORICAL, EWMA, PARKINSON, GARMAN_KLASS
- `VolRegime` enum: LOW, NORMAL, HIGH, EXTREME
- Configurable windows, decay factors, regime thresholds, annualization

## Dashboard (`app/pages/volatility.py`)
4-tab layout: Overview | Surface | Term Structure | Regime
