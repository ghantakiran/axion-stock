# PRD-63: Regime-Aware Signals

## Overview
Signal generation system that adapts to detected market regimes, providing regime-conditional trading signals with dynamic parameter adjustment.

## Features

### 1. Regime Detection
- **HMM-based detection**: Hidden Markov Model regime classification
- **Volatility clustering**: GARCH-based regime identification
- **Trend strength**: ADX and moving average regime detection
- **Multi-timeframe**: Regime analysis across timeframes

### 2. Signal Generation
- **Regime-conditional signals**: Signals adapted to current regime
- **Dynamic parameters**: Indicator parameters adjust by regime
- **Signal strength scoring**: Confidence-weighted signals
- **Multi-factor signals**: Combined signal from multiple indicators

### 3. Signal Types
- **Momentum signals**: Trend-following in trending regimes
- **Mean reversion signals**: Counter-trend in ranging regimes
- **Breakout signals**: Volatility expansion detection
- **Defensive signals**: Risk-off positioning in crisis regimes

### 4. Signal Analytics
- **Regime transition alerts**: Regime change notifications
- **Historical accuracy**: Signal performance by regime
- **Signal attribution**: Performance breakdown by signal type
- **Regime statistics**: Duration and frequency analysis

## Technical Implementation

### Database Tables
- `regime_states`: Historical regime classifications
- `regime_signals`: Generated signals with regime context
- `signal_performance`: Signal accuracy tracking
- `regime_parameters`: Dynamic parameter configurations

### API Endpoints
- `GET /api/regimes/current` - Current regime state
- `GET /api/regimes/history` - Historical regime data
- `GET /api/signals/regime-aware` - Regime-conditional signals
- `GET /api/signals/performance` - Signal performance metrics

### Backend Module
- `RegimeDetector`: Multi-method regime detection
- `SignalGenerator`: Regime-aware signal generation
- `ParameterOptimizer`: Dynamic parameter adjustment
- `PerformanceTracker`: Signal accuracy tracking

## Success Metrics
- Regime detection accuracy > 70%
- Signal accuracy improvement > 15% vs static signals
- Regime transition detection latency < 1 day
- Parameter optimization cycle < 24 hours
