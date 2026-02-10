---
name: bot-management
description: Managing the Axion autonomous trading bot -- start/stop/pause/resume, kill switch, monitoring, lifecycle, API/WebSocket control. Covers BotOrchestrator 9-stage pipeline, PersistentStateManager, LifecycleManager, BotController, BotPerformanceTracker, CLI usage, REST API (11 endpoints), WebSocket (5 channels), Docker service, and signal loop operation.
metadata:
  author: axion-platform
  version: "1.0"
---

# Bot Management

## When to use this skill

Use this skill when you need to:
- Start, stop, pause, resume, or kill the trading bot
- Activate or reset the kill switch
- Monitor bot status, open positions, and execution history
- Understand the 9-stage orchestrator pipeline
- Interact via REST API or WebSocket for remote bot control
- Run the bot as a standalone CLI process or Docker service
- Track real-time performance metrics (Sharpe, Sortino, drawdown)
- Debug signal rejections or pipeline failures

## Step-by-step instructions

### 1. Start the bot via CLI

The standalone entry point is `src/bot_pipeline/__main__.py`:

```bash
# Paper mode (default)
python -m src.bot_pipeline --paper

# Live mode with Alpaca broker
python -m src.bot_pipeline --live

# Custom config file
python -m src.bot_pipeline --config bot_config.json --state-dir /data/state

# Custom poll interval and symbol universe
python -m src.bot_pipeline --paper --poll-interval 15 --symbols SPY QQQ AAPL NVDA

# Debug logging
python -m src.bot_pipeline --paper --log-level DEBUG
```

### 2. Start the bot via REST API

```bash
# Start in paper mode
curl -X POST http://localhost:8000/api/v1/bot/start \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ax_your_key" \
  -d '{"paper_mode": true}'

# Get status
curl http://localhost:8000/api/v1/bot/status -H "X-API-Key: ax_your_key"

# Pause signal processing (keeps monitoring positions)
curl -X POST http://localhost:8000/api/v1/bot/pause -H "X-API-Key: ax_your_key"

# Resume
curl -X POST http://localhost:8000/api/v1/bot/resume -H "X-API-Key: ax_your_key"

# Emergency kill switch
curl -X POST http://localhost:8000/api/v1/bot/kill \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ax_your_key" \
  -d '{"reason": "Market flash crash detected"}'

# Reset kill switch
curl -X POST http://localhost:8000/api/v1/bot/kill/reset -H "X-API-Key: ax_your_key"

# Get open positions
curl http://localhost:8000/api/v1/bot/positions -H "X-API-Key: ax_your_key"

# Get execution history (paginated)
curl "http://localhost:8000/api/v1/bot/history?limit=50&offset=0" -H "X-API-Key: ax_your_key"

# Hot-update config
curl -X PUT http://localhost:8000/api/v1/bot/config \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ax_your_key" \
  -d '{"paper_mode": true, "enable_sound_alerts": false}'

# Get current config
curl http://localhost:8000/api/v1/bot/config -H "X-API-Key: ax_your_key"
```

### 3. Connect via WebSocket

```python
import asyncio
import json
import websockets

async def monitor_bot():
    uri = "ws://localhost:8000/ws/bot?user_id=trader1"
    async with websockets.connect(uri) as ws:
        # Receive auto-subscription confirmation
        msg = await ws.recv()
        print(json.loads(msg))  # {"event": "connected", "connection_id": "..."}

        # Subscribe to a specific channel
        await ws.send(json.dumps({"action": "subscribe", "channel": "signals"}))

        # Heartbeat
        await ws.send(json.dumps({"action": "heartbeat"}))

        # Listen for events
        while True:
            event = json.loads(await ws.recv())
            print(f"[{event.get('event')}] {event.get('data')}")

asyncio.run(monitor_bot())
```

WebSocket channels: `signals`, `orders`, `alerts`, `lifecycle`, `metrics`.

Event type to channel mapping:
- `trade_executed`, `position_closed`, `order_submitted` -> `orders`
- `signal_received`, `signal_rejected`, `signal_fused` -> `signals`
- `kill_switch`, `emergency_close`, `daily_loss_warning`, `error` -> `alerts`
- `bot_started`, `bot_stopped`, `bot_paused`, `bot_resumed` -> `lifecycle`
- `performance_snapshot`, `weight_update` -> `metrics`

### 4. Docker service

The bot runs as a standalone Docker service defined in `docker-compose.yml`:

```yaml
bot:
  build: .
  command: python -m src.bot_pipeline --paper --state-dir /data/state
  volumes:
    - bot_state:/data/state
  healthcheck:
    test: ["CMD", "python", "-c", "import json; s=json.load(open('/data/state/bot_state.json')); exit(0 if not s.get('kill_switch_active') else 1)"]
    interval: 30s
```

## Code examples

### Create and use the BotOrchestrator directly

```python
from src.bot_pipeline import BotOrchestrator, PipelineConfig, PipelineResult
from src.bot_pipeline import PersistentStateManager
from src.trade_executor.router import OrderRouter
from src.trade_executor.executor import AccountState
from src.ema_signals.detector import TradeSignal

# Configure the pipeline
config = PipelineConfig(
    enable_signal_recording=True,    # PRD-162 audit trail
    enable_unified_risk=True,        # PRD-163 risk context
    enable_feedback_loop=True,       # PRD-166 signal feedback
    enable_strategy_selection=True,  # PRD-165 strategy selector
    enable_signal_fusion=True,       # PRD-147 signal fusion
    enable_regime_adaptation=True,   # PRD-155 regime adaptive
    enable_alerting=True,            # PRD-174 bot alerts
    enable_analytics=True,           # PRD-175 performance tracking
    max_order_retries=3,
    retry_backoff_base=1.0,
    auto_kill_on_daily_loss=True,
    max_signal_age_seconds=120.0,
    dedup_window_seconds=300.0,
    state_dir=".bot_state",
)

# Create components
state_manager = PersistentStateManager(config.state_dir)
order_router = OrderRouter(primary_broker="paper", paper_mode=True)

# Build orchestrator
orchestrator = BotOrchestrator(
    config=config,
    state_manager=state_manager,
    order_router=order_router,
)

# Process a signal through the pipeline
account = AccountState(
    equity=100_000.0,
    cash=50_000.0,
    buying_power=50_000.0,
    starting_equity=100_000.0,
)

result: PipelineResult = orchestrator.process_signal(signal, account)
if result.success:
    print(f"Position opened: {result.position.ticker} @ ${result.position.entry_price}")
    print(f"Signal ID: {result.signal_id}")
    print(f"Order ID: {result.order_result.order_id}")
else:
    print(f"Rejected at {result.pipeline_stage}: {result.rejection_reason}")
```

### Kill switch management

```python
from src.bot_pipeline import PersistentStateManager

state = PersistentStateManager("/data/state")

# Check kill switch status
if state.kill_switch_active:
    print(f"KILLED: {state.kill_switch_reason}")

# Activate kill switch (persisted to disk immediately)
state.activate_kill_switch("Daily loss limit exceeded: -$5,200")

# Deactivate (manual reset)
state.deactivate_kill_switch()

# Read daily P&L (auto-resets on day rollover)
print(f"Daily P&L: ${state.daily_pnl:.2f}")
print(f"Daily trades: {state.daily_trade_count}")
print(f"Lifetime P&L: ${state.total_realized_pnl:.2f}")
```

### Performance tracking

```python
from src.bot_analytics import BotPerformanceTracker, PerformanceSnapshot

tracker = BotPerformanceTracker(starting_equity=100_000.0)

# Record trades as they close
tracker.record_trade(
    ticker="AAPL", direction="long", pnl=320.50,
    signal_type="ema_bullish_cross", strategy="ema_cloud",
    entry_price=192.0, exit_price=195.20, shares=100,
    exit_reason="target_hit",
)

# Get a performance snapshot
snap: PerformanceSnapshot = tracker.get_snapshot()
print(f"Win rate: {snap.win_rate:.1%}")
print(f"Sharpe: {snap.sharpe:.2f}")
print(f"Sortino: {snap.sortino:.2f}")
print(f"Max drawdown: ${snap.max_drawdown:.2f}")
print(f"By signal type: {snap.by_signal}")
print(f"By strategy: {snap.by_strategy}")
```

## Key classes and methods

### `BotOrchestrator` (src/bot_pipeline/orchestrator.py)
- `process_signal(signal, account, regime, returns_by_ticker) -> PipelineResult`
- `close_position(ticker, exit_reason, exit_price, partial_qty=None) -> Optional[Position]`
- `get_pipeline_stats() -> dict`
- Properties: `positions`, `execution_history`, `config`

### `PersistentStateManager` (src/bot_pipeline/state_manager.py)
- `activate_kill_switch(reason)` / `deactivate_kill_switch()`
- `record_trade_pnl(pnl)` / `record_signal_time()` / `record_trade_time()`
- `set_circuit_breaker(status, reason)` / `get_snapshot() -> dict`
- Properties: `kill_switch_active`, `kill_switch_reason`, `daily_pnl`, `daily_trade_count`, `total_realized_pnl`, `circuit_breaker_status`

### `BotController` (src/bot_dashboard/state.py)
- `start(paper_mode)` / `pause()` / `resume()` / `kill(reason)` / `reset_kill_switch()`
- `update_config(updates)` / `update_state(**kwargs)` / `get_events(limit, severity)`
- Properties: `state -> BotState`, `config -> DashboardConfig`

### `LifecycleManager` (src/bot_pipeline/lifecycle_manager.py)
- `update_prices(price_map)` -- refresh all open position prices
- `check_exits(price_map) -> list[ExitSignal]` -- run exit monitor
- `emergency_close_all(reason) -> int` -- close everything, activate kill switch
- `get_portfolio_snapshot() -> PortfolioSnapshot`

### `BotPerformanceTracker` (src/bot_analytics/tracker.py)
- `record_trade(ticker, direction, pnl, signal_type, strategy, ...)`
- `get_snapshot() -> PerformanceSnapshot`
- `get_equity() -> float` / `get_trade_count() -> int` / `get_recent_trades(limit)`

### `PipelineConfig` (src/bot_pipeline/orchestrator.py)
Key fields: `executor_config`, `enable_signal_recording`, `enable_unified_risk`, `enable_feedback_loop`, `max_order_retries`, `retry_backoff_base`, `state_dir`, `max_signal_age_seconds`, `dedup_window_seconds`, `enable_strategy_selection`, `enable_signal_fusion`, `enable_regime_adaptation`, `enable_alerting`, `enable_analytics`, `auto_kill_on_daily_loss`, `feedback_adjust_every_n_trades`

### `PipelineResult` (src/bot_pipeline/orchestrator.py)
Fields: `success`, `signal`, `position`, `order_result`, `fill_validation`, `rejection_reason`, `signal_id`, `decision_id`, `execution_id`, `risk_assessment`, `pipeline_stage`

## Common patterns

### The 9-stage pipeline (with sub-stages)

```
Stage 1:    Kill switch check (persistent, survives restart)
Stage 1.5:  Signal guard (freshness + deduplication)
Stage 0.5:  Regime adaptation (PRD-155 via RegimeBridge)
Stage 2:    Signal recording (PRD-162 audit trail)
Stage 3:    Risk assessment (PRD-163 unified risk or basic check)
Stage 3.5:  Instrument routing (options/ETF/stock)
Stage 4:    Position sizing (standard or leveraged ETF)
Stage 5:    Order submission (with exponential backoff retry)
Stage 6:    Fill validation (reject ghost positions)
Stage 7:    Position creation (only after validated fill)
Stage 8:    Execution recording + journal + alerting
Stage 9:    Feedback tracking + daily loss limit check
```

### Rejection pipeline stages

When `PipelineResult.success` is False, check `pipeline_stage`:
- `kill_switch` -- bot is halted
- `signal_guard` -- stale or duplicate signal
- `risk_assessment` -- unified risk rejected (correlation, VaR, position limits)
- `basic_risk_check` -- max concurrent positions exceeded
- `fill_validation` -- broker fill failed validation
- `risk_assessment_error` -- risk module threw an exception

### Graceful shutdown pattern

```python
# The CLI runner handles SIGINT/SIGTERM
signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# On shutdown, close all open positions
for pos in list(orchestrator.positions):
    orchestrator.close_position(pos.ticker, "graceful_shutdown", pos.current_price)
```

### Bot state file format

The kill switch, daily P&L, and circuit breaker persist in `.bot_state/bot_state.json`:

```json
{
  "kill_switch_active": false,
  "kill_switch_reason": null,
  "daily_pnl": -1250.00,
  "daily_trade_count": 7,
  "daily_date": "2026-02-09",
  "consecutive_losses": [-180.0, -220.0],
  "circuit_breaker_status": "closed",
  "total_realized_pnl": 3450.00,
  "last_signal_time": "2026-02-09T14:30:00+00:00",
  "last_trade_time": "2026-02-09T14:28:15+00:00"
}
```

### REST API endpoints summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/bot/start` | write | Start bot (paper/live) |
| POST | `/api/v1/bot/stop` | write | Graceful stop |
| POST | `/api/v1/bot/pause` | write | Pause signal processing |
| POST | `/api/v1/bot/resume` | write | Resume processing |
| POST | `/api/v1/bot/kill` | write | Emergency kill switch |
| POST | `/api/v1/bot/kill/reset` | write | Reset kill switch |
| GET | `/api/v1/bot/status` | read | Full status snapshot |
| GET | `/api/v1/bot/positions` | read | Open positions |
| GET | `/api/v1/bot/history` | read | Execution history |
| PUT | `/api/v1/bot/config` | write | Hot-update config |
| GET | `/api/v1/bot/config` | read | Get current config |

### Strategy API Endpoints (`src/api/routes/strategies.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/strategies` | read | List all registered strategies |
| GET | `/api/v1/strategies/stats` | read | A/B comparison stats from StrategySelector |
| GET | `/api/v1/strategies/{name}` | read | Get single strategy details |
| PUT | `/api/v1/strategies/{name}/enable` | write | Enable a strategy |
| PUT | `/api/v1/strategies/{name}/disable` | write | Disable a strategy |
| POST | `/api/v1/strategies/{name}/analyze` | write | Run strategy on OHLCV data |

### Strategy Routing (StrategySelector + StrategyBridge)

The `StrategySelector` (`src/strategy_selector/selector.py`) uses ADX to gate between trending and ranging strategies. When EMA Cloud is selected and OHLCV data is available, it further refines to specific Ripster sub-strategies via `refine_ema_strategy()`:

1. **Strong trend + ORB breakout** → TrendDayStrategy (confidence 90)
2. **Moderate+ trend + pullback** → PullbackToCloudStrategy (confidence 80)
3. **Any trend + session match** → SessionScalpStrategy (confidence 65)
4. **Fallback** → generic EMA Cloud signals (confidence 70)

The `StrategyBridge` (`src/bot_pipeline/strategy_bridge.py`) passes full OHLCV arrays to `StrategySelector.select()` for Ripster refinement.

### Source files

- `src/bot_pipeline/__init__.py` -- public API exports
- `src/bot_pipeline/__main__.py` -- CLI entry point
- `src/bot_pipeline/orchestrator.py` -- BotOrchestrator, PipelineConfig, PipelineResult
- `src/bot_pipeline/state_manager.py` -- PersistentStateManager
- `src/bot_pipeline/signal_guard.py` -- SignalGuard (freshness + dedup)
- `src/bot_pipeline/lifecycle_manager.py` -- LifecycleManager, PortfolioSnapshot
- `src/bot_pipeline/order_validator.py` -- OrderValidator, FillValidation
- `src/bot_pipeline/position_reconciler.py` -- PositionReconciler
- `src/bot_pipeline/regime_bridge.py` -- RegimeBridge (PRD-173)
- `src/bot_pipeline/fusion_bridge.py` -- FusionBridge (PRD-173)
- `src/bot_pipeline/strategy_bridge.py` -- StrategyBridge (PRD-173)
- `src/bot_pipeline/alert_bridge.py` -- BotAlertBridge (PRD-174)
- `src/bot_pipeline/feedback_bridge.py` -- FeedbackBridge (PRD-176)
- `src/bot_dashboard/state.py` -- BotController, BotState, DashboardConfig
- `src/bot_analytics/tracker.py` -- BotPerformanceTracker
- `src/bot_analytics/snapshot.py` -- PerformanceSnapshot
- `src/bot_analytics/metrics.py` -- sharpe_ratio, sortino_ratio, calmar_ratio, max_drawdown
- `src/api/routes/bot.py` -- REST API router (11 endpoints)
- `src/api/routes/bot_ws.py` -- WebSocket endpoint (/ws/bot)
- `src/api/routes/strategies.py` -- Strategy registry REST API (6 endpoints)
- `src/strategy_selector/selector.py` -- ADX-gated strategy routing with Ripster refinement
- `src/strategies/` -- BotStrategy protocol, StrategyRegistry, 6 built-in strategies
- `src/qullamaggie/` -- 3 Qullamaggie strategies (breakout, EP, parabolic short) + 5 scanner presets

## See Also

- **ripster-ema-trading** — Ripster EMA Cloud signal detection and cloud layers
- **qullamaggie-momentum** — Qullamaggie breakout/EP/parabolic short momentum strategies
- **trading-signal-generation** — Signal pipeline, fusion weights, and strategy registration
