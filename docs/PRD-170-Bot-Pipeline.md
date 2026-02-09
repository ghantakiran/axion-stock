# PRD-170: Bot Pipeline Robustness & Integration

## Overview

Hardens the trading bot with thread safety, persistent state, order validation, position reconciliation, and full integration with PRD-162 through PRD-169 enhancement modules.

## Problem Statement

Analysis of the trading bot revealed 96+ robustness gaps:

- **Race condition** between risk check and position creation (`executor.py`) — no synchronization around `process_signal()` and `close_position()`
- **Kill switch state lost** on process restart — state held in memory only, no persistence layer
- **No order fill validation** — ghost positions created from unfilled or rejected orders
- **No broker position reconciliation** — local position list drifts from broker reality over time
- **DST bug in market hours check** — hardcoded UTC-5 offset ignores Eastern Daylight Time (EDT)
- **Enhancement modules disconnected** — all 5 enhancement modules (PRDs 162-169) have zero production imports into the live pipeline

## Architecture

- **Module**: `src/bot_pipeline/`
- **5 source files**: `orchestrator.py`, `state_manager.py`, `order_validator.py`, `position_reconciler.py`, `__init__.py`
- **4 hardened files**: `executor.py` (lock), `router.py` (retry), `risk_gate.py` (DST), `exit_monitor.py` (DST)

### Pipeline Flow

```
Signal --> PersistentKillSwitch --> SignalRecorder (PRD-162) --> UnifiedRisk (PRD-163)
    --> PositionSizer --> OrderRouter (w/ retry) --> OrderValidator
    --> Position --> SignalFeedback (PRD-166)
```

### Module Dependencies

| Upstream Module | Integration Point | Purpose |
|-----------------|-------------------|---------|
| PRD-162 Signal Recorder | `orchestrator.py` | Audit trail for every signal entering pipeline |
| PRD-163 Unified Risk | `orchestrator.py` | Replaces basic RiskGate with cross-module risk context |
| PRD-166 Signal Feedback | `orchestrator.py` | Adaptive signal source weighting based on outcomes |
| PRD-134 EMA Signals | Input signals | Primary signal source |
| PRD-135 Trade Executor | `executor.py` (hardened) | Core execution engine with thread lock |
| PRD-136 Options Scalper | `router.py` (hardened) | Instrument routing with retry |

## Components

### BotOrchestrator (`orchestrator.py`)

Central pipeline coordinator. Thread-safe via `threading.RLock()`. Integrates enhancement modules into a unified execution flow.

**Responsibilities:**
- Receives signals from EMA Cloud Engine (PRD-134)
- Records signals via SignalRecorder (PRD-162) for audit trail
- Evaluates unified risk context (PRD-163) replacing basic RiskGate
- Routes validated orders through OrderRouter with retry
- Validates fills before position creation
- Reports outcomes to SignalFeedback (PRD-166) for adaptive weighting

**Key Methods:**
| Method | Description |
|--------|-------------|
| `process_signal(signal)` | Full pipeline: record, risk check, size, route, validate, track |
| `check_pipeline_health()` | Returns health status of all pipeline components |
| `get_pipeline_metrics()` | Aggregated metrics across all stages |
| `shutdown()` | Graceful shutdown with state persistence |

### PersistentStateManager (`state_manager.py`)

File-backed JSON state with atomic writes (`tmp` + `os.rename`). Survives process restarts, crashes, and deploys.

**Tracked State:**
| Field | Type | Description |
|-------|------|-------------|
| `kill_switch_active` | `bool` | Kill switch state (survives restarts) |
| `daily_pnl` | `float` | Daily P&L (single source of truth) |
| `consecutive_losses` | `int` | Consecutive loss counter for circuit breaker |
| `circuit_breaker_open` | `bool` | Whether circuit breaker is tripped |
| `circuit_breaker_until` | `str (ISO)` | Circuit breaker cooldown expiry |
| `last_trade_date` | `str (ISO)` | Date of last trade for day rollover |
| `positions` | `list` | Serialized open positions |

**Atomic Write Protocol:**
1. Serialize state to JSON
2. Write to temporary file (`state.json.tmp`)
3. `os.rename()` atomically replaces old file (POSIX guarantee)
4. Auto day rollover resets daily counters when date changes

### OrderValidator (`order_validator.py`)

Validates order fills before position creation. Prevents ghost positions from unfilled, rejected, or stale orders.

**Validation Checks:**
| Check | Failure Condition | Action |
|-------|-------------------|--------|
| Order status | `rejected` / `cancelled` / `pending_new` | Reject — do not create position |
| Fill quantity | `filled_qty <= 0` | Reject — no fill received |
| Fill price | `fill_price <= 0` | Reject — invalid price |
| Slippage | `abs(fill - expected) / expected > threshold` | Reject or warn based on config |
| Fill age | `now - fill_timestamp > max_age` | Reject — stale fill |
| Partial fill | `filled_qty < requested_qty` | Accept with adjusted size (if `allow_partial`) |

**Return Value:** `OrderValidationResult` dataclass with `valid`, `reason`, `adjusted_quantity`, `actual_slippage_pct` fields.

### PositionReconciler (`position_reconciler.py`)

Syncs local position state with broker-reported positions. Runs on configurable interval.

**Discrepancy Types:**
| Type | Definition | Resolution |
|------|------------|------------|
| Ghost position | Local position exists, broker has none | Close local position, log alert |
| Orphaned position | Broker reports position, not tracked locally | Import into local state or close at broker |
| Quantity mismatch | Local and broker quantities differ | Update local to match broker (broker is truth) |
| Direction mismatch | Long vs short disagrees | Update local to match broker |
| Price drift | Average price differs significantly | Update local cost basis |

**Reconciliation Report:** Each run produces a `ReconciliationReport` with timestamp, discrepancies found, actions taken, and final sync status. Reports are persisted to `bot_reconciliation_reports` table.

## Hardening Changes

### executor.py: Threading Lock

```python
import threading

class TradeExecutor:
    def __init__(self, ...):
        self._lock = threading.RLock()
        ...

    def process_signal(self, signal):
        with self._lock:
            # risk check + position creation are now atomic
            ...

    def close_position(self, position_id):
        with self._lock:
            # position removal is synchronized
            ...
```

- `RLock` allows re-entrant calls (e.g., close triggered from within process)
- Prevents race between risk check passing and another thread modifying positions
- Lock scope is minimal — only around state-mutating sections

### router.py: Retry with Backoff

```python
def route_order(self, order, max_retries=3, backoff_base=1.0):
    for attempt in range(max_retries):
        try:
            result = self._submit_to_broker(order)
            return result
        except (ConnectionError, TimeoutError) as e:
            if attempt < max_retries - 1:
                wait = backoff_base * (2 ** attempt)
                time.sleep(wait)
            else:
                raise OrderRoutingError(f"Failed after {max_retries} attempts: {e}")
```

- Configurable `max_retries` (default 3)
- Exponential backoff: 1s, 2s, 4s between attempts
- Fallback broker attempted on primary failure
- Configurable `timeout_seconds` per attempt

### risk_gate.py: DST Fix

```python
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except ImportError:
    from datetime import timezone, timedelta
    ET = timezone(timedelta(hours=-5))  # fallback to EST
```

- Uses `zoneinfo.ZoneInfo("America/New_York")` for proper Eastern Time
- Automatically handles EST (UTC-5) and EDT (UTC-4) transitions
- Falls back to UTC-5 only if `zoneinfo` unavailable (Python < 3.9 without backports)
- Market hours check: 09:30-16:00 ET (correct year-round)

### exit_monitor.py: DST Fix

- Same `zoneinfo` fix applied to EOD close time calculation
- EOD close triggers at 15:55 ET (5 min before close) regardless of DST state
- Swing trade exemption logic unchanged

## Database Tables

### bot_pipeline_states

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| snapshot_time | DateTime | When state was captured |
| kill_switch_active | Boolean | Kill switch state |
| daily_pnl | Float | Daily P&L at snapshot time |
| consecutive_losses | Integer | Loss streak count |
| circuit_breaker_open | Boolean | Circuit breaker state |
| open_position_count | Integer | Number of open positions |
| state_json | Text | Full serialized state |
| created_at | DateTime | Record creation time |

### bot_reconciliation_reports

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| reconciliation_time | DateTime | When reconciliation ran |
| ghost_positions | Integer | Count of ghost positions found |
| orphaned_positions | Integer | Count of orphaned positions found |
| quantity_mismatches | Integer | Count of quantity mismatches |
| direction_mismatches | Integer | Count of direction mismatches |
| actions_taken | Text (JSON) | List of corrective actions |
| final_status | String | `synced` / `partial` / `failed` |
| created_at | DateTime | Record creation time |

## Migration

- **Revision**: 170
- **Down revision**: 167
- **Chain**: `...167 -> 170`
- **File**: `alembic/versions/170_bot_pipeline.py`
- Creates `bot_pipeline_states` and `bot_reconciliation_reports` tables
- Indexes on `snapshot_time` and `reconciliation_time` for time-range queries

## Configuration

### PipelineConfig

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enable_signal_recording` | `True` | Record signals via PRD-162 SignalRecorder |
| `enable_unified_risk` | `True` | Use unified risk (PRD-163) vs basic RiskGate |
| `enable_feedback_loop` | `True` | Track signal source performance via PRD-166 |
| `max_order_retries` | `3` | Retry attempts for order submission |
| `retry_backoff_base` | `1.0` | Base seconds for exponential backoff |
| `state_dir` | `.bot_state` | Directory for persistent state files |
| `reconciliation_interval` | `300` | Seconds between reconciliation runs |
| `state_snapshot_interval` | `60` | Seconds between DB state snapshots |

### OrderValidatorConfig

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_slippage_pct` | `2.0` | Max acceptable slippage percentage |
| `max_fill_age_seconds` | `300` | Max fill timestamp age before rejection |
| `allow_partial` | `True` | Accept partial fills with adjusted quantity |
| `min_partial_fill_pct` | `50.0` | Minimum partial fill percentage to accept |

### ReconcilerConfig

| Parameter | Default | Description |
|-----------|---------|-------------|
| `auto_close_ghosts` | `False` | Automatically close ghost positions |
| `auto_import_orphans` | `False` | Automatically import orphaned positions |
| `price_drift_threshold` | `5.0` | Percentage drift before flagging |
| `broker_is_truth` | `True` | Broker state takes precedence on mismatch |

## Testing

- **~62 tests** across 5 test classes
- All self-contained (no DB, broker, or network dependencies)
- Test file: `tests/test_bot_pipeline.py`

### Test Classes

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestBotOrchestrator` | ~18 | Pipeline flow, module integration, shutdown |
| `TestPersistentStateManager` | ~12 | Atomic writes, day rollover, crash recovery |
| `TestOrderValidator` | ~14 | All rejection paths, slippage, partial fills |
| `TestPositionReconciler` | ~10 | Ghost/orphan detection, mismatch resolution |
| `TestThreadSafety` | ~8 | Concurrent `process_signal` / `close_position` |

### Thread Safety Tests

```python
def test_concurrent_signal_processing(self):
    """Verify no race between simultaneous process_signal calls."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(executor.process_signal, sig) for sig in signals]
        results = [f.result() for f in futures]
    # Assert no duplicate positions, no lost signals
```

## Dashboard

- **Page**: `app/pages/bot_pipeline.py`
- **Navigation section**: Trading Bot

### Tabs

| Tab | Contents |
|-----|----------|
| Pipeline Health | Component status indicators, signal flow diagram, error rates |
| Order Validation | Recent validation results, rejection reasons, slippage histogram |
| Position Reconciliation | Last reconciliation report, discrepancy history, sync status |
| State Management | Current persistent state, kill switch toggle, circuit breaker status |

## Risk Considerations

- **Atomic state writes** prevent corrupted state files on crash
- **Thread locks** prevent position count races under concurrent signals
- **Order validation** prevents capital allocation to unfilled orders
- **Reconciliation** catches broker/local drift before it causes incorrect risk calculations
- **DST fix** prevents early/late market hour trades twice per year
- **Retry with backoff** prevents order loss during transient broker outages

## Future Enhancements

- Distributed locking (Redis) for multi-process deployments
- Order fill streaming via WebSocket instead of polling
- Reconciliation webhooks for real-time broker sync
- State replication to secondary storage for HA
