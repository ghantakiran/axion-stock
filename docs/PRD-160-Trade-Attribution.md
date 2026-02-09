# PRD-160: Live Trade Attribution

## Overview

Links executed trades back to their originating signals, decomposes P&L into component factors, and tracks signal-type performance over rolling windows for continuous strategy optimization.

## Problem Statement

After trades execute, there is no systematic way to determine which signals drove the best outcomes. Without attribution, traders cannot identify which signal types to emphasize or deprecate.

## Solution

A three-layer attribution pipeline:

1. **Trade-Signal Linker** — Matches completed trades to signals via exact ID or fuzzy time-proximity matching
2. **P&L Decomposer** — Breaks each trade's P&L into entry quality, market movement, exit timing, and transaction costs
3. **Signal Performance Tracker** — Maintains rolling statistics per signal type across configurable windows with regime awareness

## Architecture

```
Signal Registration → Buffer (last 1000)
                         ↓
Trade Completion → Link (fuzzy match) → LinkedTrade
                         ↓
                    Decompose P&L → PnLBreakdown
                         ↓
                    Track Performance → RollingSignalStats
                         ↓
                    Attribution Report
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `AttributionConfig` | `src/trade_attribution/config.py` | Configuration: method, windows, costs |
| `TradeSignalLinker` | `src/trade_attribution/linker.py` | Fuzzy trade→signal matching |
| `TradeDecomposer` | `src/trade_attribution/decomposer.py` | P&L decomposition (simple/VWAP/implementation) |
| `SignalPerformanceTracker` | `src/trade_attribution/tracker.py` | Rolling window performance stats |
| `AttributionEngine` | `src/trade_attribution/engine.py` | Unified orchestrator |

## P&L Decomposition Formula (Simple Method)

- **Entry Quality** = (bar_midpoint - entry_price) * shares * direction
- **Market Movement** = (exit_midpoint - entry_midpoint) * shares * direction
- **Exit Timing** = (exit_price - exit_midpoint) * shares * direction
- **Transaction Costs** = round-trip commission + sqrt market impact
- **Residual** = total_pnl - sum(components)

## Database Tables

- `trade_attribution_links` — Trade-to-signal linkage records (21 columns)
- `trade_pnl_decomposition` — P&L breakdown per trade (14 columns)
- `signal_performance_snapshots` — Rolling performance snapshots (15 columns)

## Dashboard

4-tab Streamlit page (`app/pages/trade_attribution.py`):
1. Trade Linkage — Signal registration and trade linking
2. P&L Decomposition — Component breakdown visualization
3. Signal Performance — Rolling stats by signal type
4. Live Report — Full attribution report with export

## Dependencies

- PRD-134 (EMA Signals) — Signal types
- PRD-135 (Trade Executor) — Trade execution records
- PRD-155 (Regime Adaptive) — Regime context

## Testing

~55 tests in `tests/test_trade_attribution.py` covering all components.
