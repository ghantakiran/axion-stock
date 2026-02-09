# PRD-161: Social Signal Backtester

## Overview

Validates social trading signals against historical price data by archiving signals, measuring outcomes at multiple horizons, computing score-return correlations, and running backtestable strategies.

## Problem Statement

Social intelligence (PRD-141) generates trading signals from social media data, but there is no way to measure whether these signals actually predict price movements. Without validation, social signals cannot be trusted for live trading.

## Solution

A four-layer validation pipeline:

1. **Signal Archive** — Stores social signals with timestamps for replay
2. **Outcome Validator** — Measures direction accuracy at 1d/5d/10d/30d horizons
3. **Correlation Analyzer** — Finds optimal lag between signal and price reaction
4. **Backtest Strategy** — Simulates a trading strategy driven by signal scores

## Architecture

```
SocialTradingSignal (PRD-141)
        ↓
    Archive (store with timestamp)
        ↓
    Replay (chronological)
        ↓
  ┌─────┴─────┐
  │            │
Validate    Correlate
(hit rates)  (lag analysis)
  │            │
  └─────┬─────┘
        ↓
    Backtest (simulate P&L)
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `BacktesterConfig` | `src/social_backtester/config.py` | Horizons, thresholds, significance |
| `SignalArchive` | `src/social_backtester/archive.py` | Signal storage and replay |
| `OutcomeValidator` | `src/social_backtester/validator.py` | Direction accuracy and hit rates |
| `CorrelationAnalyzer` | `src/social_backtester/correlation.py` | Score-return lag correlations |
| `SocialSignalStrategy` | `src/social_backtester/strategy.py` | Backtestable strategy engine |

## Validation Metrics

- **Hit Rate** — % of signals where predicted direction matched actual return
- **Score Correlation** — Pearson r between signal score and forward return
- **Optimal Lag** — Days delay that maximizes score-return correlation
- **High vs Low Score** — Hit rate comparison for signals above/below threshold

## Database Tables

- `social_signal_archive` — Archived signals for replay (15 columns)
- `social_signal_outcomes` — Outcome measurements per signal (14 columns)
- `social_correlation_cache` — Cached correlation results (10 columns)

## Dashboard

4-tab Streamlit page (`app/pages/social_backtester.py`):
1. Signal Archive — Stats, timeline, direction distribution
2. Outcome Validation — Hit rates by horizon, per-ticker breakdown
3. Correlation Analysis — Lag charts, significance heatmap
4. Backtest — Strategy config, equity curve, trade log

## Dependencies

- PRD-141 (Social Intelligence) — `SocialTradingSignal` input
- PRD-140 (Social Crawler) — Raw social data collection

## Testing

~55 tests in `tests/test_social_backtester.py` covering all components.
