# PRD-135: Autonomous Trade Executor

## Overview
Fully autonomous order execution engine that consumes signals from the EMA Cloud Signal Engine (PRD-134), manages positions, enforces risk limits, and routes orders to Alpaca and/or Interactive Brokers. The executor handles the complete trade lifecycle: entry → position management → scaling → exit.

## Module
`src/trade_executor/` — Autonomous Trade Executor

---

## Architecture

### Execution Pipeline

```
Signal Queue ──→ Risk Gate ──→ Position Sizer ──→ Order Router ──→ Broker API
                    │                                    │
                    ▼                                    ▼
              [REJECTED]                         [Fill Confirmed]
              - Daily loss limit hit                     │
              - Max positions reached                    ▼
              - Duplicate/conflicting              Position Manager
              - Outside market hours                     │
                                                         ▼
                                                   Exit Monitor
                                                   - Stop loss hit
                                                   - Target reached
                                                   - Momentum exhaustion
                                                   - Cloud flip (reverse)
                                                   - EOD forced close
```

### Risk Parameters (Aggressive Profile)

| Parameter | Value | Description |
|-----------|-------|-------------|
| Max risk per trade | 5% of account equity | Position sized so max loss = 5% |
| Max concurrent positions | 10 | Hard limit on open positions |
| Daily loss limit | 10% of account equity | Kill switch trips, no new trades for the day |
| Max single-stock exposure | 15% of equity | Prevents concentration in one ticker |
| Max sector exposure | 30% of equity | Prevents sector concentration |
| Min account equity | $25,000 | PDT rule compliance |
| Slippage buffer | 0.1% | Accounts for fill price vs signal price |

### Position Sizing

```python
class PositionSizer:
    """Calculate position size based on conviction and risk parameters."""

    def calculate(self, signal: TradeSignal, account: AccountState) -> PositionSize:
        """
        Sizing formula:
        1. risk_amount = account_equity * max_risk_per_trade (5%)
        2. stop_distance = abs(entry_price - stop_loss) / entry_price
        3. raw_shares = risk_amount / (entry_price * stop_distance)
        4. conviction_multiplier:
           - High (75-100): 1.0x (full position)
           - Medium (50-74): 0.5x (half position)
        5. final_shares = min(raw_shares * conviction_multiplier, max_position_shares)
        """
        ...
```

### Entry Strategies

| Strategy | Trigger | Execution |
|----------|---------|-----------|
| **Immediate Market** | High conviction (≥75) + volume confirmed | Market order, fill ASAP |
| **Limit at Cloud** | Medium conviction (50-74) | Limit order at cloud edge, wait for pullback |
| **Scale-In** | Any conviction ≥50 | Enter half position, add half on first pullback to cloud that holds |

### Exit Strategies

| Exit Type | Trigger | Priority |
|-----------|---------|----------|
| **Stop Loss** | Price closes below macro cloud (34/50) for longs | 1 (highest) |
| **Momentum Exhaustion** | 3+ consecutive candles close outside fast cloud, same color | 2 |
| **Cloud Flip** | Fast cloud (5/12) flips direction → reverse signal | 3 |
| **Profit Target** | 2:1 reward-to-risk reached | 4 |
| **Time Stop** | Position open > 2 hours with no progress (day trades) | 5 |
| **EOD Close** | Day trades closed by 3:55 PM ET (no overnight holds for day trades) | 6 |
| **Trailing Stop** | Swing trades: trail stop at pullback cloud (8/9) | 7 |

---

## Source Files

### `src/trade_executor/__init__.py`
Exports: `TradeExecutor`, `RiskGate`, `PositionSizer`, `OrderRouter`, `PositionManager`, `ExitMonitor`

### `src/trade_executor/executor.py` (~350 lines)
Main execution engine.

```python
@dataclass
class AccountState:
    equity: float
    cash: float
    buying_power: float
    open_positions: list[Position]
    daily_pnl: float
    daily_trades: int
    is_pdt_compliant: bool

@dataclass
class Position:
    ticker: str
    direction: Literal["long", "short"]
    entry_price: float
    current_price: float
    shares: int
    stop_loss: float
    target_price: float | None
    entry_time: datetime
    signal_id: str                     # Links back to EMA signal
    unrealized_pnl: float
    trade_type: Literal["day", "swing", "scalp"]

class TradeExecutor:
    """Main execution engine — consumes signals, manages lifecycle."""

    def __init__(self, config: ExecutorConfig, broker: OrderRouter):
        self.config = config
        self.broker = broker
        self.risk_gate = RiskGate(config)
        self.sizer = PositionSizer(config)
        self.position_manager = PositionManager()
        self.exit_monitor = ExitMonitor(config, broker)

    async def process_signal(self, signal: TradeSignal) -> ExecutionResult:
        """Full pipeline: validate → size → route → confirm."""
        ...

    async def run_loop(self):
        """Main event loop — poll signal queue + monitor positions."""
        ...
```

### `src/trade_executor/risk_gate.py` (~200 lines)
Pre-trade risk validation.

```python
class RiskGate:
    """Gate that rejects signals violating risk parameters."""

    def validate(self, signal: TradeSignal, account: AccountState) -> RiskDecision:
        """
        Checks (all must pass):
        1. daily_pnl > -daily_loss_limit
        2. len(open_positions) < max_concurrent_positions
        3. No existing position in same ticker (unless adding to winner)
        4. No conflicting signals (long + short same ticker)
        5. Sector exposure check
        6. Market hours check
        7. Account equity > min_equity (PDT compliance)
        8. Sufficient buying power for the position
        """
        ...

@dataclass
class RiskDecision:
    approved: bool
    reason: str | None             # Rejection reason if not approved
    adjustments: dict | None       # e.g., reduced size due to exposure limits
```

### `src/trade_executor/router.py` (~300 lines)
Broker routing and order management.

```python
class OrderRouter:
    """Routes orders to Alpaca or IBKR based on configuration."""

    def __init__(self, alpaca_client=None, ibkr_client=None, primary_broker: str = "alpaca"):
        self.alpaca = alpaca_client
        self.ibkr = ibkr_client
        self.primary = primary_broker

    async def submit_order(self, order: Order) -> OrderResult:
        """Submit order to primary broker, fallback to secondary on failure."""
        ...

    async def cancel_order(self, order_id: str) -> bool: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_account(self) -> AccountState: ...

    # Broker-specific implementations
    async def _submit_alpaca(self, order: Order) -> OrderResult: ...
    async def _submit_ibkr(self, order: Order) -> OrderResult: ...

@dataclass
class Order:
    ticker: str
    side: Literal["buy", "sell"]
    qty: int
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: float | None
    stop_price: float | None
    time_in_force: Literal["day", "gtc", "ioc"]
    signal_id: str
    metadata: dict

@dataclass
class OrderResult:
    order_id: str
    status: Literal["filled", "partial", "pending", "rejected", "cancelled"]
    filled_qty: int
    filled_price: float
    broker: str
    timestamp: datetime
```

### `src/trade_executor/exit_monitor.py` (~250 lines)
Continuous position monitoring for exit conditions.

```python
class ExitMonitor:
    """Monitor open positions for exit signals."""

    async def monitor_loop(self, positions: list[Position]):
        """Continuously check exit conditions for all positions."""
        ...

    def check_stop_loss(self, position: Position, current_price: float) -> bool: ...
    def check_momentum_exhaustion(self, position: Position, bars: pd.DataFrame) -> bool: ...
    def check_cloud_flip(self, position: Position, cloud_states: list[CloudState]) -> bool: ...
    def check_profit_target(self, position: Position, current_price: float) -> bool: ...
    def check_time_stop(self, position: Position) -> bool: ...
    def check_eod_close(self, position: Position) -> bool: ...
    def check_trailing_stop(self, position: Position, bars: pd.DataFrame) -> bool: ...
```

### `src/trade_executor/journal.py` (~150 lines)
Automated trade journaling.

```python
class TradeJournalWriter:
    """Automatically log every trade with signal context, execution details, and P&L."""

    def record_entry(self, signal: TradeSignal, order_result: OrderResult, position: Position): ...
    def record_exit(self, position: Position, exit_reason: str, order_result: OrderResult): ...
    def get_daily_summary(self, date: date) -> DailySummary: ...
    def get_trade_history(self, ticker: str = None, days: int = 30) -> list[TradeRecord]: ...
```

---

## Data Models (ORM)

```python
class TradeExecutionRecord(Base):
    __tablename__ = "trade_executions"

    id = Column(Integer, primary_key=True)
    signal_id = Column(String(50), index=True)           # Links to ema_signals
    ticker = Column(String(10), nullable=False, index=True)
    direction = Column(String(10), nullable=False)
    trade_type = Column(String(10), nullable=False)       # day, swing, scalp
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    shares = Column(Integer, nullable=False)
    stop_loss = Column(Float)
    target_price = Column(Float)
    conviction = Column(Integer)
    status = Column(String(20), nullable=False, default="open")  # open, closed, cancelled
    exit_reason = Column(String(50))                      # stop_loss, target, exhaustion, etc.
    pnl = Column(Float)                                   # Realized P&L
    pnl_pct = Column(Float)                               # Realized P&L %
    broker = Column(String(20))                           # alpaca, ibkr
    order_id = Column(String(100))
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    metadata_json = Column(Text)                          # JSON: cloud states, account snapshot
    created_at = Column(DateTime, default=func.now())

class DailyPnLRecord(Base):
    __tablename__ = "daily_pnl"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    starting_equity = Column(Float, nullable=False)
    ending_equity = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    total_trades = Column(Integer, nullable=False)
    winning_trades = Column(Integer, nullable=False)
    losing_trades = Column(Integer, nullable=False)
    max_drawdown = Column(Float)
    kill_switch_triggered = Column(Boolean, default=False)
    metadata_json = Column(Text)
```

---

## Kill Switch

```python
class KillSwitch:
    """Emergency stop for the trading bot."""

    def check(self, account: AccountState) -> bool:
        """Returns True if bot should halt all trading.

        Triggers:
        1. Daily loss exceeds 10% of starting equity
        2. Manual kill switch toggled via dashboard
        3. Broker API connectivity lost for > 60 seconds
        4. Account equity drops below $25K (PDT violation risk)
        5. More than 3 consecutive losing trades with >3% loss each
        """
        ...

    def activate(self, reason: str) -> None:
        """Halt all trading, close all day trade positions, alert user."""
        ...

    def deactivate(self) -> None:
        """Re-enable trading (manual only via dashboard)."""
        ...
```

---

## Configuration

```python
@dataclass
class ExecutorConfig:
    # Risk parameters (Aggressive)
    max_risk_per_trade: float = 0.05          # 5% of equity
    max_concurrent_positions: int = 10
    daily_loss_limit: float = 0.10            # 10% of equity
    max_single_stock_exposure: float = 0.15   # 15% of equity
    max_sector_exposure: float = 0.30         # 30% of equity
    min_account_equity: float = 25_000.0      # PDT compliance

    # Execution
    primary_broker: str = "alpaca"            # "alpaca" or "ibkr"
    fallback_broker: str = "ibkr"
    slippage_buffer: float = 0.001            # 0.1%
    default_time_in_force: str = "day"

    # Entry
    high_conviction_order_type: str = "market"  # Market for high conviction
    medium_conviction_order_type: str = "limit"  # Limit for medium conviction
    scale_in_enabled: bool = True
    scale_in_initial_pct: float = 0.5         # Enter 50% initially

    # Exit
    reward_to_risk_target: float = 2.0        # 2:1 R:R
    time_stop_minutes: int = 120              # 2 hours
    eod_close_time: str = "15:55"             # 3:55 PM ET
    trailing_stop_cloud: str = "pullback"     # Use 8/9 cloud for trailing

    # Kill switch
    consecutive_loss_threshold: int = 3
    consecutive_loss_pct: float = 0.03        # 3% each
    api_timeout_seconds: int = 60
```

---

## Integration Points

| System | Integration |
|--------|-------------|
| **EMA Signal Engine** (PRD-134) | Consumes signals from signal queue |
| **Options Scalper** (PRD-136) | Scalper uses same router + risk gate for options orders |
| **Bot Dashboard** (PRD-137) | Exposes position state, P&L, kill switch control |
| **Alpaca API** | `src/brokers/alpaca_broker.py` — existing Axion integration |
| **IBKR API** | `src/brokers/ib_broker.py` — existing Axion integration |
| **Trade Journal** | `src/journal/` — existing Axion module augmented with auto-logging |
| **Alert System** | `src/alerting/` — alerts on fills, stops, kill switch |

---

## Alembic Migration
`alembic/versions/135_trade_executor.py`
- Creates `trade_executions` table
- Creates `daily_pnl` table
- Indexes on `(ticker, status)`, `(signal_id)`, `(date)`

---

## Tests
`tests/test_trade_executor.py` (~350 lines)

| Test Class | Tests |
|-----------|-------|
| `TestRiskGate` | All 8 validation checks, boundary conditions, rejection reasons |
| `TestPositionSizer` | Conviction-based sizing, max position caps, edge cases |
| `TestOrderRouter` | Alpaca/IBKR routing, fallback on failure, order types |
| `TestExitMonitor` | Each exit condition (stop, exhaustion, flip, target, time, EOD, trail) |
| `TestKillSwitch` | All 5 trigger conditions, activate/deactivate |
| `TestTradeExecutor` | Full pipeline: signal → risk → size → route → fill → monitor → exit |
| `TestTradeJournal` | Record entry/exit, daily summary, history queries |

---

## Dashboard Page
`app/pages/trade_executor.py` — added to nav_config.py under "Trading & Execution"

**Tabs:**
1. **Active Positions** — Live P&L, entry/stop/target levels, time in trade
2. **Order Book** — Pending orders, recent fills, order history
3. **Risk Dashboard** — Current exposure, daily P&L curve, drawdown, kill switch toggle
4. **Trade Journal** — Auto-logged trade history with signal attribution and P&L
