# PRD-171: Bot Lifecycle Hardening

## Overview

PRD-171 closes 10 production robustness gaps identified in a full code audit
of the 12 bot files (PRD-134 through PRD-170). These gaps would cause
real-money losses or operational failures in a live trading environment.

## Problems Solved

| # | Problem | Impact | Solution |
|---|---------|--------|----------|
| 1 | Stale signals executed | Trades on outdated market data | `SignalGuard.is_fresh()` with configurable max_age |
| 2 | Duplicate signals | Multiple entries on same bar | `SignalGuard.is_duplicate()` with dedup window |
| 3 | Paper mode $100 fill | Corrupted P&L calculations | `router.py` fallback chain: limit → stop → entry_price |
| 4 | Journal disconnected | No trade history | Wired `TradeJournalWriter` into orchestrator |
| 5 | Frozen position prices | Stale P&L, broken exits | `LifecycleManager.update_prices()` |
| 6 | Exit monitor not running | Positions never auto-close | `LifecycleManager.check_exits()` |
| 7 | No daily loss auto-kill | Unlimited daily losses | `_check_daily_loss_limit()` in close_position |
| 8 | Instrument routing bypassed | Always trades stocks | Wired `InstrumentRouter` + `LeveragedETFSizer` |
| 9 | No graceful shutdown | Kill switch leaves positions open | `LifecycleManager.emergency_close_all()` |
| 10 | Unbounded execution_history | Memory leak in long runs | `collections.deque(maxlen=max_history_size)` |

## Architecture

### New Components

#### SignalGuard (`src/bot_pipeline/signal_guard.py`)
- **Freshness check**: Rejects signals older than `max_age_seconds` (default: 120s)
- **Deduplication**: Rejects same (ticker, signal_type, direction) within `dedup_window_seconds` (default: 300s)
- Thread-safe via `threading.Lock`
- Uses `time.monotonic()` for dedup timestamps (immune to clock adjustments)

#### LifecycleManager (`src/bot_pipeline/lifecycle_manager.py`)
- **update_prices()**: Refreshes `current_price` on all open positions
- **check_exits()**: Runs `ExitMonitor.check_all()` across all positions
- **execute_exits()**: Closes positions for triggered exit signals
- **emergency_close_all()**: Graceful shutdown — close all, activate kill switch
- **get_portfolio_snapshot()**: Real-time P&L and exposure summary

### Modified Components

#### BotOrchestrator (`src/bot_pipeline/orchestrator.py`)
New pipeline stages:
- Stage 1.5: SignalGuard (between kill switch and signal recording)
- Stage 3.5: InstrumentRouter (between risk assessment and sizing)
- Stage 8.5: Journal entry recording (after execution recording)
- Daily loss auto-kill in `close_position()`
- `execution_history` is now a bounded `deque(maxlen=10_000)`

New PipelineConfig fields:
- `max_signal_age_seconds`, `dedup_window_seconds`
- `enable_instrument_routing`, `enable_journaling`
- `max_history_size`, `auto_kill_on_daily_loss`

#### PersistentStateManager (`src/bot_pipeline/state_manager.py`)
- `total_realized_pnl`: Lifetime P&L (survives daily resets)
- `last_signal_time`: ISO timestamp of last signal received
- `last_trade_time`: ISO timestamp of last trade executed

#### OrderRouter (`src/trade_executor/router.py`)
- Paper mode `_simulate_fill()` now uses fallback chain:
  `limit_price → stop_price → metadata["entry_price"] → 100.0`
- Orders carry `metadata={"entry_price": signal.entry_price}`

## Pipeline Flow (Updated)

```
Signal
  → Stage 1:   Kill Switch (persistent)
  → Stage 1.5: SignalGuard (freshness + dedup)    ← NEW
  → Stage 2:   Signal Recording (PRD-162)
  → Stage 3:   Unified Risk Assessment (PRD-163)
  → Stage 3.5: Instrument Routing (options/ETF)   ← NEW
  → Stage 4:   Position Sizing (standard or ETF)
  → Stage 5:   Order Submission (with retry)
  → Stage 6:   Fill Validation
  → Stage 7:   Position Creation
  → Stage 8:   Execution Recording (PRD-162)
  → Stage 8.5: Journal Entry                      ← NEW
  → Stage 9:   Feedback Tracking (PRD-166)
  → Close:     Journal Exit + Daily Loss Check     ← NEW
```

## Configuration

```python
PipelineConfig(
    # Signal guards
    max_signal_age_seconds=120.0,   # Reject signals older than 2 min
    dedup_window_seconds=300.0,     # Reject duplicates within 5 min

    # Lifecycle
    enable_instrument_routing=True,  # Route to options/ETFs/stocks
    enable_journaling=True,          # Record all trades in journal
    max_history_size=10_000,         # Cap execution history

    # Auto-kill
    auto_kill_on_daily_loss=True,    # Kill switch on daily loss limit
)
```

## Database

### Table: `bot_lifecycle_events`
| Column | Type | Description |
|--------|------|-------------|
| event_id | VARCHAR(50) | Unique event identifier |
| event_type | VARCHAR(30) | signal_guard_reject, exit, emergency_close, etc. |
| ticker | VARCHAR(20) | Affected symbol |
| direction | VARCHAR(10) | long/short |
| details_json | TEXT | Event-specific details |
| pipeline_run_id | VARCHAR(50) | Links to pipeline execution |
| event_time | TIMESTAMP | When the event occurred |

## Dashboard

4-tab Streamlit page at `app/pages/bot_lifecycle.py`:
1. **Signal Guard Stats** — Rejection rates, active dedup entries
2. **Position Lifecycle** — Live prices, unrealized P&L, exposure
3. **Exit Monitor** — Exit signals by type, frequency
4. **Emergency Controls** — Kill switch, emergency close, daily limit

## Testing

~50 tests in `tests/test_bot_lifecycle.py`:
- `TestSignalGuard` (~15 tests): freshness, dedup, window expiry, concurrent access
- `TestLifecycleManager` (~14 tests): price updates, exit detection, emergency close
- `TestOrchestratorLifecycle` (~14 tests): guard wiring, journal, routing, auto-kill
- `TestPaperModeFix` (~8 tests): market order pricing, fallback chain
- `TestStateManagerLifecycle` (~5 tests): lifetime P&L, timestamps

## Migration

- Revision: `171`
- Down revision: `170`
- Migration chain: `...167 → 170 → 171`
