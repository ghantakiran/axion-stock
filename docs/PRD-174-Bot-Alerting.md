# PRD-174: Bot Alerting & Notifications

## Overview

Connects the trading bot's lifecycle events to the platform alerting system (PRD-114). A single `BotAlertBridge` component maps 7 bot event types to `AlertManager.fire()` calls with deduplication, severity classification, and structured payloads for multi-channel dispatch.

## Problem Statement

The bot generates critical operational events (kill switch activation, emergency closes, error spikes) that are logged but not surfaced through the platform's alerting infrastructure:

- **No proactive notification** when the kill switch activates — operators discover it on next dashboard check
- **No escalation** for repeated guard rejections that may indicate data feed issues
- **No trade notifications** for completed executions or position closes
- **Error events** are logged to file but not routed to Slack, email, or PagerDuty

## Architecture

- **Module**: `src/bot_pipeline/`
- **Source file**: `alert_bridge.py`
- **Dependencies**: AlertManager (PRD-114), BotOrchestrator (PRD-170)

### Event Flow

```
BotOrchestrator / LifecycleManager
  --> BotAlertBridge.on_<event>()
    --> severity classification
    --> dedup_key generation
    --> AlertManager.fire(alert)
      --> routing rules (PRD-114)
        --> Slack / Email / PagerDuty / Webhook
```

## Key Components

### BotAlertBridge (`src/bot_pipeline/alert_bridge.py`)

Central event handler that translates bot events into platform alerts. Stateless — all deduplication is handled by `AlertManager` via `dedup_key`.

**Event Handlers:**

| Handler | Trigger | Severity | Dedup Key |
|---------|---------|----------|-----------|
| `on_trade_executed(trade)` | Order filled, position created | `info` | `trade_{ticker}_{direction}_{timestamp_minute}` |
| `on_position_closed(position, pnl)` | Position exit completed | `info` / `warning` | `close_{ticker}_{position_id}` |
| `on_kill_switch(reason)` | Kill switch activated | `critical` | `kill_switch_{date}` |
| `on_daily_loss_warning(pnl, limit)` | Daily P&L exceeds 80% of limit | `warning` | `daily_loss_{date}` |
| `on_guard_rejection_spike(count, window)` | >5 rejections in 60 seconds | `warning` | `guard_spike_{window_start}` |
| `on_emergency_close(positions_closed)` | Emergency close all triggered | `critical` | `emergency_{timestamp}` |
| `on_error(error, context)` | Unhandled exception in pipeline | `error` | `error_{error_type}_{minute}` |

**Severity Classification:**

| Severity | Routing | Examples |
|----------|---------|----------|
| `info` | Slack #bot-trades | Trade executed, position closed with profit |
| `warning` | Slack #bot-alerts + email | Daily loss warning, guard rejection spike, loss close |
| `error` | Slack #bot-alerts + email + on-call | Pipeline exceptions, broker errors |
| `critical` | Slack #bot-alerts + email + PagerDuty | Kill switch, emergency close |

**Implementation:**

```python
class BotAlertBridge:
    def __init__(self, alert_manager: AlertManager):
        self._alert_manager = alert_manager

    def on_kill_switch(self, reason: str):
        self._alert_manager.fire(
            name="bot_kill_switch_activated",
            severity="critical",
            message=f"Kill switch activated: {reason}",
            dedup_key=f"kill_switch_{date.today().isoformat()}",
            metadata={"reason": reason, "component": "bot_pipeline"}
        )

    def on_daily_loss_warning(self, current_pnl: float, limit: float):
        pct = abs(current_pnl / limit) * 100
        self._alert_manager.fire(
            name="bot_daily_loss_warning",
            severity="warning",
            message=f"Daily P&L ${current_pnl:.2f} is {pct:.0f}% of limit ${limit:.2f}",
            dedup_key=f"daily_loss_{date.today().isoformat()}",
            metadata={"pnl": current_pnl, "limit": limit, "pct_of_limit": pct}
        )

    def on_guard_rejection_spike(self, count: int, window_seconds: int):
        window_start = int(time.time()) - window_seconds
        self._alert_manager.fire(
            name="bot_guard_rejection_spike",
            severity="warning",
            message=f"{count} signal rejections in {window_seconds}s — possible data feed issue",
            dedup_key=f"guard_spike_{window_start // 60}",
            metadata={"rejection_count": count, "window_seconds": window_seconds}
        )
```

### Orchestrator Integration

The `BotOrchestrator` calls `BotAlertBridge` at each relevant pipeline event:

```python
class BotOrchestrator:
    def __init__(self, ..., alert_bridge: BotAlertBridge = None):
        self._alert_bridge = alert_bridge

    def process_signal(self, signal):
        # ... existing stages ...
        if self._alert_bridge and trade_result.filled:
            self._alert_bridge.on_trade_executed(trade_result)

    def close_position(self, position_id, reason):
        # ... existing logic ...
        if self._alert_bridge:
            self._alert_bridge.on_position_closed(position, realized_pnl)
```

## API / Interface

```python
# Setup
from src.alerting import AlertManager
from src.bot_pipeline.alert_bridge import BotAlertBridge

alert_manager = AlertManager(routing_rules=bot_routing_config)
alert_bridge = BotAlertBridge(alert_manager)

# Wire into orchestrator
orchestrator = BotOrchestrator(
    ...,
    alert_bridge=alert_bridge
)

# Manual trigger (for testing)
alert_bridge.on_kill_switch(reason="Daily loss limit exceeded")
```

## Database Schema

### bot_alert_history

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| alert_id | VARCHAR(50) | Unique alert identifier |
| event_type | VARCHAR(30) | trade_executed, kill_switch, error, etc. |
| severity | VARCHAR(10) | info, warning, error, critical |
| message | Text | Human-readable alert message |
| dedup_key | VARCHAR(100) | Deduplication key used |
| metadata_json | Text | Structured event payload |
| dispatched_to | Text (JSON) | List of channels alert was sent to |
| acknowledged_at | DateTime | When operator acknowledged (null if pending) |
| created_at | DateTime | Alert creation timestamp |

**ORM Model:** `BotAlertHistoryRecord` in `src/db/models.py`

## Migration

- **Revision**: 174
- **Down revision**: 173
- **Chain**: `...172 -> 173 -> 174`
- **File**: `alembic/versions/174_bot_alerting.py`
- Creates `bot_alert_history` table
- Indexes on `event_type`, `severity`, `dedup_key`, and `created_at`

## Dashboard

4-tab Streamlit page at `app/pages/bot_alerting.py`:

| Tab | Contents |
|-----|----------|
| Alert Feed | Live alert stream with severity badges, filtering |
| Alert History | Paginated history with search, date range, severity filter |
| Routing Config | Current routing rules, channel assignments per severity |
| Statistics | Alert volume by type/severity, acknowledgment latency |

## Testing

~40 tests in `tests/test_bot_alerting.py`:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestBotAlertBridge` | ~18 | All 7 event handlers, severity, dedup keys |
| `TestAlertDeduplication` | ~8 | Same-key suppression, window expiry, key format |
| `TestOrchestratorAlertWiring` | ~8 | Bridge called at correct pipeline points |
| `TestAlertPayloads` | ~6 | Metadata structure, message formatting |

## Dependencies

| Module | Usage |
|--------|-------|
| PRD-114 AlertManager | Alert dispatch, dedup, routing |
| PRD-170 BotOrchestrator | Event source (trades, kills, errors) |
| PRD-171 LifecycleManager | Emergency close events |
| PRD-171 SignalGuard | Guard rejection counts |
