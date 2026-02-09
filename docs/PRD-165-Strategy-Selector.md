# PRD-165: Multi-Strategy Selector & Mean-Reversion Engine

## Overview

Adds a strategy selection layer that dynamically chooses between momentum (EMA Cloud) and a new mean-reversion engine based on detected market regime. Implements Bollinger Band and RSI-based mean-reversion signals, a regime-aware router, and blended conviction scoring for range-bound markets.

## Problem Statement

The bot currently runs a single strategy (EMA Cloud momentum). In sideways or range-bound markets, momentum signals generate excessive whipsaws and false breakouts. The platform lacks a mean-reversion strategy and has no mechanism to automatically switch strategies based on market conditions.

## Solution

Three new components layered on top of existing infrastructure:

1. **Mean-Reversion Engine** — Generates signals from Bollinger Band touches, RSI extremes, and Z-score reversals with position sizing based on distance-to-mean
2. **Regime Router** — Consumes regime state from PRD-155 and selects the active strategy (momentum, mean-reversion, or blended)
3. **Strategy Selector** — Manages strategy lifecycle, blends conviction scores when regimes are transitional, and routes final signals to the executor

## Architecture

```
Market Data
    ↓
┌───────────────┐    ┌───────────────┐
│ EMA Cloud     │    │ Mean-Reversion│
│ (Momentum)    │    │ (BB/RSI/Z)    │
│ PRD-134       │    │ PRD-165       │
└───────┬───────┘    └───────┬───────┘
        │                    │
        └────────┬───────────┘
                 ↓
          RegimeRouter (PRD-155)
                 ↓
          StrategySelector
           ┌─────┴─────┐
           │            │
        Momentum    Mean-Rev    Blended
           │            │          │
           └────────┬───┘──────────┘
                    ↓
            Trade Executor (PRD-135)
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `StrategyConfig` | `src/strategy_selector/config.py` | Regime thresholds, blend weights, indicator params |
| `MeanReversionEngine` | `src/strategy_selector/mean_reversion.py` | BB/RSI/Z-score signal generation with conviction scoring |
| `RegimeRouter` | `src/strategy_selector/router.py` | Maps regime state to strategy selection |
| `StrategySelector` | `src/strategy_selector/selector.py` | Lifecycle management, conviction blending, signal routing |
| `IndicatorCalculator` | `src/strategy_selector/indicators.py` | Bollinger Bands, RSI, Z-score calculations |

## Data Models

- `StrategySelectionRecord` -> `strategy_selections` (16 columns) — selection_id, timestamp, ticker, regime, chosen_strategy, momentum_conviction, meanrev_conviction, blended_conviction, blend_weight, etc.
- `MeanReversionSignal` -> `mean_reversion_signals` (14 columns) — signal_id, ticker, indicator_type, direction, distance_to_mean, z_score, rsi_value, bb_position, conviction, timestamp

## Implementation

### Source Files
- `src/strategy_selector/__init__.py` — Public API exports
- `src/strategy_selector/config.py` — Configuration with default indicator parameters
- `src/strategy_selector/mean_reversion.py` — BB touch, RSI extreme, and Z-score reversal detection
- `src/strategy_selector/router.py` — Regime-to-strategy mapping with transition smoothing
- `src/strategy_selector/selector.py` — Strategy orchestrator with conviction blending
- `src/strategy_selector/indicators.py` — Technical indicator calculations

### Database
- Migration `alembic/versions/165_strategy_selector.py` — revision `165`, down_revision `164`

### Dashboard
- `app/pages/strategy_selector.py` — 4 tabs: Active Strategy, Mean-Reversion Signals, Regime Map, Blend Analysis

### Tests
- `tests/test_strategy_selector.py` — ~55 tests covering mean-reversion signal generation, regime routing, conviction blending, strategy transitions, and indicator edge cases

## Dependencies

- Depends on: PRD-134 (EMA Cloud Signals), PRD-155 (Regime Adaptive), PRD-135 (Trade Executor)
- Depended on by: PRD-166 (Signal Feedback Loop), PRD-167 (Enhanced Backtest)

## Success Metrics

- Mean-reversion strategy achieves > 55% win rate in range-bound regimes
- Strategy switching reduces max drawdown by > 15% vs. momentum-only in choppy markets
- Regime transition blending produces smoother equity curves (lower daily return variance)
- Signal generation latency < 10ms per ticker per bar
