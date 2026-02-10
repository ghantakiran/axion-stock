---
name: order-execution
description: Execute trades through the signal-to-order pipeline with 8-check risk gate, 7 exit strategies, instrument routing (options/ETFs/stocks), multi-broker routing, and the hardened bot orchestrator. Covers TradeExecutor, RiskGate, ExitMonitor, InstrumentRouter, OrderRouter, SmartRouter, and the BotOrchestrator pipeline. Use when building or debugging trade execution, order routing, or bot pipeline flows.
metadata:
  author: axion-platform
  version: "1.0"
---

# Order Execution

## When to use this skill

Use this skill when you need to:
- Execute the full signal-to-order pipeline (validate, size, route, monitor, exit)
- Validate trade signals against the 8-check risk gate
- Monitor open positions with 7 exit strategies
- Route signals to the correct instrument (options, leveraged ETFs, stocks)
- Submit orders through the multi-broker order router with retry logic
- Use the hardened BotOrchestrator pipeline with kill switch, signal guard, and audit trail
- Debug order fill validation or position reconciliation

## Step-by-step instructions

### 1. Understand the Execution Pipeline

The autonomous trade executor follows this flow:

```
TradeSignal -> RiskGate (8 checks) -> PositionSizer -> InstrumentRouter
    -> OrderRouter (broker submission) -> ExitMonitor (7 strategies) -> Journal
```

The hardened BotOrchestrator extends this with:

```
Signal -> PersistentKillSwitch -> SignalGuard (fresh+dedup)
    -> SignalRecorder (PRD-162) -> UnifiedRisk (PRD-163)
    -> InstrumentRouter -> PositionSizer -> OrderRouter (w/ retry)
    -> OrderValidator -> Position -> Journal -> Feedback -> DailyLossCheck
```

**Source files:**
- `src/trade_executor/executor.py` -- TradeExecutor, ExecutorConfig, AccountState, Position
- `src/trade_executor/risk_gate.py` -- RiskGate (8 checks)
- `src/trade_executor/exit_monitor.py` -- ExitMonitor (7 strategies)
- `src/trade_executor/instrument_router.py` -- InstrumentRouter, LEVERAGED_ETF_CATALOG
- `src/trade_executor/router.py` -- OrderRouter (broker submission)
- `src/trade_executor/journal.py` -- TradeJournalWriter
- `src/trade_executor/etf_sizer.py` -- LeveragedETFSizer
- `src/bot_pipeline/orchestrator.py` -- BotOrchestrator, PipelineConfig, PipelineResult
- `src/bot_pipeline/state_manager.py` -- PersistentStateManager
- `src/bot_pipeline/signal_guard.py` -- SignalGuard (freshness + dedup)
- `src/bot_pipeline/order_validator.py` -- OrderValidator (fill validation)
- `src/bot_pipeline/position_reconciler.py` -- PositionReconciler
- `src/bot_pipeline/lifecycle_manager.py` -- LifecycleManager

### 2. Higher-Level Execution Services

For non-bot trading (manual or rebalance), use the execution module:

**Source files:**
- `src/execution/trading_service.py` -- TradingService (high-level buy/sell/rebalance)
- `src/execution/paper_broker.py` -- PaperBroker (simulation)
- `src/execution/alpaca_broker.py` -- AlpacaBroker (live/paper)
- `src/execution/order_manager.py` -- OrderManager, SmartOrderRouter
- `src/smart_router/router.py` -- SmartRouter (venue scoring and splitting)

## Code examples

### Risk Gate Validation (8 Checks)

```python
from src.trade_executor import (
    RiskGate,
    RiskDecision,
    ExecutorConfig,
    AccountState,
    Position,
)
from src.ema_signals import TradeSignal, SignalType

# Configure risk parameters
config = ExecutorConfig(
    max_risk_per_trade=0.05,
    max_concurrent_positions=10,
    daily_loss_limit=0.10,          # 10% daily loss limit
    max_single_stock_exposure=0.15,  # 15% per ticker
    max_sector_exposure=0.30,        # 30% per sector
    min_account_equity=25_000.0,     # PDT compliance
)

# Current account state
account = AccountState(
    equity=100_000,
    cash=50_000,
    buying_power=150_000,
    open_positions=[
        Position(
            ticker="AAPL", direction="long",
            entry_price=180.0, current_price=185.0,
            shares=100, stop_loss=175.0,
        ),
    ],
    daily_pnl=-500.0,
    starting_equity=100_000,
)

# Create a trade signal
signal = TradeSignal(
    signal_type=SignalType.CLOUD_CROSS_BULLISH,
    direction="long",
    ticker="NVDA",
    timeframe="5m",
    conviction=75,
    entry_price=850.0,
    stop_loss=830.0,
)

# Run all 8 risk checks
gate = RiskGate(config)
decision = gate.validate(signal, account)

if decision.approved:
    print("Signal APPROVED for execution")
    if decision.adjustments:
        print(f"Adjustments: {decision.adjustments}")
else:
    print(f"Signal REJECTED: {decision.reason}")

# The 8 checks are:
# 1. Daily P&L above loss limit
# 2. Open positions below max (10)
# 3. No duplicate ticker (unless adding to winner)
# 4. No conflicting signals (long + short same ticker)
# 5. Sector exposure within limits (30%)
# 6. Market hours check (9:30-16:00 ET)
# 7. Account equity above minimum ($25K PDT)
# 8. Sufficient buying power
```

### Exit Monitoring (7 Strategies)

```python
from src.trade_executor import ExitMonitor, ExitSignal, ExecutorConfig, Position

monitor = ExitMonitor(ExecutorConfig(
    reward_to_risk_target=2.0,
    time_stop_minutes=120,
    eod_close_time="15:55",
    trailing_stop_cloud="pullback",
))

position = Position(
    ticker="AAPL", direction="long",
    entry_price=180.0, current_price=170.0,
    shares=100, stop_loss=175.0,
    target_price=190.0,
)

# Check all 7 exit conditions
exit_signal = monitor.check_all(
    position=position,
    current_price=170.0,
    cloud_states=current_cloud_states,  # For cloud flip detection
    bars=recent_bars_df,                # For trailing stop, exhaustion
)

if exit_signal:
    print(f"EXIT: {exit_signal.exit_type} (priority {exit_signal.priority})")
    print(f"Reason: {exit_signal.reason}")
else:
    print("No exit signal -- hold position")

# Individual exit checks (available separately)
stop = monitor.check_stop_loss(position, current_price=170.0)
target = monitor.check_profit_target(position, current_price=195.0)
time_exit = monitor.check_time_stop(position)
eod = monitor.check_eod_close(position)
```

### Instrument Routing (Options / ETFs / Stocks)

```python
from src.trade_executor import (
    InstrumentRouter,
    InstrumentDecision,
    ExecutorConfig,
    InstrumentMode,
    LEVERAGED_ETF_CATALOG,
)
from src.ema_signals import TradeSignal, SignalType

# Route based on instrument mode
config = ExecutorConfig(instrument_mode=InstrumentMode.BOTH)
router = InstrumentRouter(config)

signal = TradeSignal(
    signal_type=SignalType.TREND_ALIGNED_LONG,
    direction="long",
    ticker="NVDA",
    timeframe="5m",
    conviction=80,
    entry_price=850.0,
    stop_loss=830.0,
)

decision = router.route(signal)
print(f"Instrument: {decision.instrument_type}")  # "leveraged_etf" or "options"
print(f"Symbol: {decision.symbol}")               # e.g., "SOXL" (semiconductor 3x bull)
print(f"Reason: {decision.reason}")

# ETF catalog maps sectors to leveraged ETFs:
# TQQQ/SQQQ (NASDAQ 3x), SPXL/SPXS (S&P 3x), SOXL/SOXS (Semis 3x),
# TECL/TECS (Tech 3x), FAS/FAZ (Financials 3x), TNA/TZA (Russell 3x), etc.
```

### Bot Orchestrator Pipeline

```python
from src.bot_pipeline import (
    BotOrchestrator,
    PipelineConfig,
    PipelineResult,
    PersistentStateManager,
    SignalGuard,
)
from src.trade_executor import ExecutorConfig, AccountState, InstrumentMode

# Configure the hardened pipeline
pipeline_config = PipelineConfig(
    executor_config=ExecutorConfig(
        instrument_mode=InstrumentMode.BOTH,
        max_concurrent_positions=10,
        daily_loss_limit=0.10,
    ),
    enable_signal_recording=True,    # PRD-162 audit trail
    enable_unified_risk=True,        # PRD-163 unified risk
    enable_feedback_loop=True,       # PRD-166 performance feedback
    max_order_retries=3,
    retry_backoff_base=1.0,
    state_dir=".bot_state",
    max_signal_age_seconds=120.0,    # Reject stale signals
    dedup_window_seconds=300.0,      # Reject duplicate signals
    auto_kill_on_daily_loss=True,
    enable_alerting=True,            # PRD-174 alert dispatch
    enable_analytics=True,           # PRD-175 live analytics
    feedback_adjust_every_n_trades=50,  # PRD-176 adaptive feedback
)

# Create orchestrator
account = AccountState(equity=100_000, cash=50_000, buying_power=150_000)
orchestrator = BotOrchestrator(config=pipeline_config, account=account)

# Process a signal through the full pipeline
result = orchestrator.process_signal(signal)

if result.success:
    print(f"Position created: {result.position.ticker}")
    print(f"Order: {result.order_result}")
    print(f"Signal ID: {result.signal_id}")      # Audit trail
    print(f"Pipeline stage: {result.pipeline_stage}")
else:
    print(f"Rejected at stage '{result.pipeline_stage}': {result.rejection_reason}")

# Kill switch management
state = orchestrator.get_state()
orchestrator.activate_kill_switch("Manual halt")
orchestrator.deactivate_kill_switch()
```

### Persistent State Manager

```python
from src.bot_pipeline import PersistentStateManager

# State survives process restarts (atomic JSON file)
state_mgr = PersistentStateManager(state_dir=".bot_state")

# Kill switch
state_mgr.activate_kill_switch("Daily loss limit exceeded")
is_active = state_mgr.is_kill_switch_active()
state_mgr.deactivate_kill_switch()

# Daily P&L tracking
state_mgr.record_pnl(150.0)
daily_pnl = state_mgr.get_daily_pnl()

# Circuit breaker
state_mgr.increment_circuit_breaker()
cb_status = state_mgr.get_circuit_breaker_status()

# Day rollover
state_mgr.check_day_rollover()
```

### Position Reconciliation

```python
from src.bot_pipeline import PositionReconciler, ReconciliationReport

reconciler = PositionReconciler()

# Compare internal positions with broker positions
report = reconciler.reconcile(
    internal_positions=[
        {"symbol": "AAPL", "shares": 100, "direction": "long"},
        {"symbol": "MSFT", "shares": 50, "direction": "long"},
    ],
    broker_positions=[
        {"symbol": "AAPL", "shares": 100},
        {"symbol": "GOOGL", "shares": 25},  # Ghost position (not in internal)
    ],
)
print(f"Matches: {report.matches}")
print(f"Mismatches: {len(report.mismatches)}")
for m in report.mismatches:
    print(f"  {m.symbol}: {m.mismatch_type} - {m.description}")
# Types: "ghost" (broker only), "orphan" (internal only), "quantity_mismatch"
```

### High-Level Trading Service

```python
from src.execution import TradingService, TradingConfig

config = TradingConfig(paper_trading=True, initial_cash=100_000)
service = TradingService(config)
await service.connect()

# Simple buy/sell
result = await service.buy("AAPL", dollars=5_000)
result = await service.sell("AAPL", shares=25)

# Rebalance to target weights
target = {"AAPL": 0.30, "MSFT": 0.30, "GOOGL": 0.40}
proposal = await service.preview_rebalance(target)
print(f"Trades needed: {len(proposal.trades)}")
print(f"Estimated cost: ${proposal.estimated_cost:.2f}")
proposal.approved = True
await service.execute_rebalance(proposal)
```

## Key classes and methods

### Trade Executor (`src/trade_executor/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `TradeExecutor` | `process_signal(signal, account)` | Full signal-to-position pipeline |
| `RiskGate` | `validate(signal, account)` | 8-check pre-trade validation |
| `ExitMonitor` | `check_all(position, price, clouds, bars)` | 7 exit strategy checks |
| `InstrumentRouter` | `route(signal)` | Options / ETF / stock routing |
| `OrderRouter` | `submit(order)`, `cancel(order_id)` | Broker order submission |
| `PositionSizer` | `size(signal, account)` | Risk-based position sizing |
| `LeveragedETFSizer` | `compute_shares(signal, account)` | ETF-specific sizing with leverage |
| `TradeJournalWriter` | `record(trade)`, `daily_summary()` | Trade audit logging |
| `KillSwitch` | `activate()`, `deactivate()`, `is_active()` | Emergency halt |

### Bot Pipeline (`src/bot_pipeline/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `BotOrchestrator` | `process_signal(signal)`, `get_state()`, `activate_kill_switch()` | Hardened pipeline coordinator |
| `PersistentStateManager` | `activate_kill_switch()`, `record_pnl()`, `check_day_rollover()` | Atomic file-backed state |
| `SignalGuard` | `check(signal)` | Freshness + deduplication |
| `OrderValidator` | `validate(order, fill)` | Fill validation (ghost detection) |
| `PositionReconciler` | `reconcile(internal, broker)` | Ghost/orphan/mismatch detection |
| `LifecycleManager` | `update_positions()`, `check_exits()`, `emergency_close_all()` | Active position management |

### Execution Module (`src/execution/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `TradingService` | `buy()`, `sell()`, `preview_rebalance()`, `execute_rebalance()` | High-level trading API |
| `PaperBroker` | `submit_order()`, `get_positions()` | Paper trading simulation |
| `AlpacaBroker` | `submit_order()`, `get_positions()` | Live Alpaca integration |
| `SmartOrderRouter` | `route(order)` | Multi-venue order routing |

### Smart Router (`src/smart_router/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `SmartRouter` | `route(order)`, `split_order()` | Venue scoring and order splitting |
| `RouteScorer` | `score(venues, order)` | Score venues by fill probability and cost |
| `CostOptimizer` | `optimize(routes)` | Minimize execution cost across venues |

## Common patterns

### The 8 Risk Gate Checks

| # | Check | Default Threshold |
|---|---|---|
| 1 | Daily P&L limit | 10% of starting equity |
| 2 | Max open positions | 10 concurrent |
| 3 | Duplicate ticker | Block unless adding to winner |
| 4 | Conflicting signals | No long+short on same ticker |
| 5 | Sector/stock exposure | 15% single stock, 30% sector |
| 6 | Market hours | 9:30 AM - 4:00 PM ET (bypass for daily TF) |
| 7 | Minimum equity | $25,000 (PDT compliance) |
| 8 | Buying power | Sufficient for minimum position |

### The 7 Exit Strategies (by Priority)

| Priority | Strategy | Trigger |
|---|---|---|
| 1 | Stop loss | Price hits stop level |
| 2 | Momentum exhaustion | 3+ candles outside fast cloud |
| 3 | Cloud flip | Cloud color changes against position |
| 4 | Profit target | Price hits R:R target (default 2:1) |
| 5 | Time stop | Position held > 120 minutes |
| 6 | EOD close | 3:55 PM ET for day trades |
| 7 | Trailing stop | Price drops below pullback cloud |

### Instrument Mode Selection

```python
# Options: route to options contracts
InstrumentMode.OPTIONS

# Leveraged ETFs: route to sector-matched leveraged ETFs (TQQQ, SOXL, etc.)
InstrumentMode.LEVERAGED_ETF

# Both: choose based on conviction, liquidity, and sector
InstrumentMode.BOTH
```

### Bot Pipeline vs. Direct Executor

| Feature | TradeExecutor | BotOrchestrator |
|---|---|---|
| Thread safety | Single RLock | Full pipeline RLock |
| Kill switch | In-memory | Persistent (file-backed) |
| Signal validation | Basic | Freshness + dedup guard |
| Risk assessment | RiskGate (8 checks) | UnifiedRisk (7 checks + correlation + VaR) |
| Order submission | Single attempt | Retry with exponential backoff |
| Fill validation | None | OrderValidator (ghost detection) |
| Audit trail | Journal only | Full signal record (PRD-162) |
| Feedback | None | Rolling Sharpe weight adjustment |

### Key ExecutorConfig Defaults

```python
ExecutorConfig(
    instrument_mode=InstrumentMode.BOTH,
    max_risk_per_trade=0.05,
    max_concurrent_positions=10,
    daily_loss_limit=0.10,
    max_single_stock_exposure=0.15,
    primary_broker="alpaca",
    fallback_broker="ibkr",
    reward_to_risk_target=2.0,
    time_stop_minutes=120,
    eod_close_time="15:55",
    consecutive_loss_threshold=3,
)
```
