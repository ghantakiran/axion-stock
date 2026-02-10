# PRD-172: Bot API & WebSocket Control

## Overview

Exposes the trading bot's full lifecycle and real-time data through a REST API and WebSocket interface. Enables external dashboards, mobile apps, and programmatic control of the autonomous trading bot without direct Python access.

## Problem Statement

The bot is currently controllable only through the Streamlit dashboard or direct Python calls. Production deployments require:

- **Remote control** — Start, stop, pause, and kill the bot from any HTTP client
- **Real-time streaming** — Live signals, order fills, and P&L updates without polling
- **Session management** — Track who initiated bot actions for audit compliance
- **Config hot-reload** — Change risk parameters without restarting the bot process

## Architecture

- **Module**: `src/api/routes/`
- **Source files**: `bot.py` (REST endpoints), `bot_ws.py` (WebSocket handler)
- **Dependencies**: FastAPI, BotOrchestrator (PRD-170), LifecycleManager (PRD-171), PersistentStateManager (PRD-170)

### Request Flow

```
Client --> FastAPI Router (/api/v1/bot/*)
  --> Authentication middleware (JWT)
  --> BotAPIController
    --> BotOrchestrator.process_signal() | .shutdown()
    --> LifecycleManager.emergency_close_all()
    --> PersistentStateManager.load() | .save()
  --> BotAPISessionRecord (audit)
```

### WebSocket Flow

```
Client --> ws://host/ws/bot
  --> JWT handshake
  --> Channel subscription (signals, orders, alerts, lifecycle, metrics)
  --> BotEventBus --> filtered push to subscribed clients
```

## Key Components

### BotAPIController (`src/api/routes/bot.py`)

FastAPI router with full bot lifecycle control.

**REST Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/bot/start` | Start the bot with optional config override |
| `POST` | `/bot/stop` | Graceful stop — close positions, deactivate |
| `POST` | `/bot/pause` | Pause signal processing (keep positions open) |
| `POST` | `/bot/resume` | Resume signal processing after pause |
| `POST` | `/bot/kill` | Activate kill switch immediately |
| `POST` | `/bot/kill/reset` | Reset kill switch and circuit breaker |
| `GET` | `/bot/status` | Current state: running, paused, stopped, killed |
| `GET` | `/bot/positions` | Open positions with real-time P&L |
| `GET` | `/bot/history` | Recent execution history (paginated) |
| `GET` | `/bot/config` | Current pipeline configuration |
| `PUT` | `/bot/config` | Hot-reload configuration parameters |

**Key Methods:**

| Method | Description |
|--------|-------------|
| `start_bot(config)` | Initializes orchestrator, starts lifecycle loop |
| `stop_bot(close_positions)` | Graceful shutdown with optional position close |
| `kill_bot()` | Immediate kill switch activation via PersistentStateManager |
| `get_status()` | Aggregates orchestrator state, positions, P&L |

### BotWebSocketHandler (`src/api/routes/bot_ws.py`)

Manages persistent WebSocket connections with channel-based subscriptions.

**Channels:**

| Channel | Payload | Frequency |
|---------|---------|-----------|
| `signals` | Signal type, ticker, conviction, direction | Per signal received |
| `orders` | Order ID, status, fill price, slippage | Per order state change |
| `alerts` | Alert type, severity, message | Per alert fired |
| `lifecycle` | Bot state transitions (start, stop, pause, kill) | Per state change |
| `metrics` | Equity, daily P&L, drawdown, position count | Every 5 seconds |

**Connection Management:**
- JWT-authenticated handshake
- Per-client channel subscription via `subscribe` / `unsubscribe` messages
- Heartbeat ping/pong every 30 seconds
- Auto-reconnect guidance in close frames
- Maximum 50 concurrent WebSocket connections

## API / Interface

```python
# Start bot with custom config
POST /api/v1/bot/start
{
    "max_positions": 5,
    "daily_loss_limit": -500.0,
    "enable_options": true
}

# Response
{
    "status": "running",
    "started_at": "2026-02-09T14:30:00Z",
    "session_id": "sess_abc123",
    "config": { ... }
}

# WebSocket subscription
ws://host/ws/bot
--> {"action": "subscribe", "channels": ["signals", "orders"]}
<-- {"channel": "signals", "data": {"ticker": "AAPL", "type": "ema_bullish_cross", "conviction": 78}}
```

## Database Schema

### bot_api_sessions

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| session_id | VARCHAR(50) | Unique session identifier |
| user_id | VARCHAR(50) | Authenticated user who initiated |
| action | VARCHAR(30) | start, stop, pause, resume, kill, config_update |
| request_body | Text (JSON) | Full request payload |
| response_status | Integer | HTTP status code returned |
| bot_state_before | VARCHAR(20) | Bot state before action |
| bot_state_after | VARCHAR(20) | Bot state after action |
| ip_address | VARCHAR(45) | Client IP (IPv4/IPv6) |
| created_at | DateTime | Timestamp of action |

**ORM Model:** `BotAPISessionRecord` in `src/db/models.py`

## Migration

- **Revision**: 172
- **Down revision**: 171
- **Chain**: `...170 -> 171 -> 172`
- **File**: `alembic/versions/172_bot_api.py`
- Creates `bot_api_sessions` table
- Index on `session_id`, `user_id`, and `created_at`

## Dashboard

4-tab Streamlit page at `app/pages/bot_api.py`:

| Tab | Contents |
|-----|----------|
| API Sessions | Recent API calls, user breakdown, action frequency |
| WebSocket Monitor | Active connections, channel subscriptions, message throughput |
| Bot Control | Start/stop/pause/kill buttons (calls REST endpoints) |
| Config Editor | Live config viewer with hot-reload form |

## Testing

~45 tests in `tests/test_bot_api.py`:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestBotAPIEndpoints` | ~16 | All REST endpoints, auth, validation |
| `TestBotWebSocket` | ~12 | Connection lifecycle, channel filtering, heartbeat |
| `TestBotAPISession` | ~8 | Session recording, audit trail |
| `TestConfigHotReload` | ~5 | Config update, validation, rollback |
| `TestConcurrentAccess` | ~4 | Simultaneous start/stop, race prevention |

## Dependencies

| Module | Usage |
|--------|-------|
| PRD-170 BotOrchestrator | Pipeline control (start, stop, process) |
| PRD-170 PersistentStateManager | Kill switch, state persistence |
| PRD-171 LifecycleManager | Emergency close, price updates |
| PRD-171 SignalGuard | Signal freshness info for status endpoint |
| PRD-109 Audit Trail | API session records |
| FastAPI | HTTP routing and WebSocket support |
