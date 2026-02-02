# PRD-48: Macro Regime Analysis

## Overview
Macro regime analysis module for tracking economic indicators, analyzing
yield curves, detecting cross-asset regimes, and building macro factor
models for regime-aware portfolio positioning.

## Components

### 1. Indicator Tracker (`src/macro/indicators.py`)
- Economic indicator ingestion and tracking
- Surprise computation (actual vs consensus)
- Momentum and trend scoring
- Leading/lagging indicator classification
- Composite economic index

### 2. Yield Curve Analyzer (`src/macro/yieldcurve.py`)
- Yield curve shape classification (normal, flat, inverted)
- Term spread computation (2s10s, 3m10y)
- Slope and curvature metrics
- Inversion detection and duration tracking
- Nelson-Siegel curve fitting (level, slope, curvature)

### 3. Regime Detector (`src/macro/regime.py`)
- Regime classification (expansion, slowdown, contraction, recovery)
- Hidden Markov Model-based regime detection
- Transition probability estimation
- Regime duration and persistence scoring
- Multi-indicator regime consensus

### 4. Factor Model (`src/macro/factors.py`)
- Macro factor construction (growth, inflation, rates, risk)
- Factor exposure estimation
- Factor return decomposition
- Regime-conditional factor behavior
- Factor momentum signals

## Database Tables
- `macro_indicators` — Economic indicator snapshots
- `yield_curve_snapshots` — Yield curve data points
- `macro_regimes` — Detected regime records
- `macro_factors` — Factor model outputs

## Dashboard
4-tab layout: Indicators | Yield Curve | Regimes | Factor Model
