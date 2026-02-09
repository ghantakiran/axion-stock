# PRD-138: Bot Strategy Backtesting Integration

## Overview

Bridges the backtesting engine (`src/backtesting/`) with the autonomous trading bot's EMA Cloud Signal Engine (`src/ema_signals/`) + Trade Executor (`src/trade_executor/`). Enables historical validation of bot strategies with signal-type attribution, walk-forward optimization, and replay analysis.

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  EMA Cloud       │     │  EMACloudStrategy │     │  BacktestEngine  │
│  Signal Engine   │────▶│  (Adapter)        │────▶│  (Event Loop)    │
│  PRD-134         │     │  PRD-138          │     │  Existing        │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                │                         │
                                ▼                         ▼
                         ┌──────────────────┐     ┌──────────────────┐
                         │  Signal           │     │  BacktestResult  │
                         │  Attribution      │◀────│  (Trades, Equity)│
                         │  Report           │     └──────────────────┘
                         └──────────────────┘
                                │
                                ▼
                         ┌──────────────────┐
                         │  Signal Replay    │
                         │  (Risk Gate A/B)  │
                         └──────────────────┘
```

## Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/bot_backtesting/__init__.py` | ~40 | Public API exports |
| `src/bot_backtesting/strategy.py` | ~300 | EMACloudStrategy adapter (Strategy Protocol) |
| `src/bot_backtesting/runner.py` | ~200 | BotBacktestRunner with OHLCV support |
| `src/bot_backtesting/attribution.py` | ~180 | SignalAttributor for per-type performance |
| `src/bot_backtesting/replay.py` | ~180 | SignalReplay for risk config A/B testing |

## ORM Models

- `BacktestRunRecord` → `bot_backtest_runs` (19 columns)
- `SignalAttributionRecord` → `bot_signal_attribution` (12 columns)

## Migration

- `alembic/versions/138_bot_backtesting.py` — revision `138`, down_revision `137`

## Dashboard

- `app/pages/bot_backtesting.py` — 4 tabs: Run Backtest, Signal Attribution, Walk-Forward, Replay Analysis

## Tests

- `tests/test_bot_backtesting.py` — 8 test classes, ~55 tests
- Run: `python3 -m pytest tests/test_bot_backtesting.py -v`

## Key Design Decisions

1. **OHLCV streaming**: Runner bypasses `engine.run()` and calls `_process_event()` directly with `stream_ohlcv_bars()` since EMA clouds need real OHLCV, not close-only data
2. **Weight mapping**: `weight = max(0.02, min(conviction/100 * 0.15, 0.15))` — maps conviction linearly to 2-15% weight
3. **Exit strategies**: 4 of 7 implemented (stop loss, target, cloud flip, exhaustion) — time stop and EOD not meaningful for daily bars
4. **Walk-forward compat**: Strategy accepts `**kwargs` in `__init__` for `WalkForwardOptimizer` compatibility
5. **Replay isolation**: Each replay creates fresh account state, enabling fair A/B comparison
