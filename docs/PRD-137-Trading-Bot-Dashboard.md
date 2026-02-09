# PRD-137: Trading Bot Dashboard & Control Center

## Overview
Unified Streamlit dashboard for monitoring and controlling the autonomous trading bot. Combines real-time P&L tracking, position monitoring, signal visualization, EMA cloud charts, and a kill switch into a single command center. This is the human oversight layer for the fully autonomous system.

## Module
`src/bot_dashboard/` — Trading Bot Dashboard & Control Center

---

## Architecture

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  AXION BOT CONTROL CENTER           [🟢 LIVE] [⏸ PAUSE] [🛑 KILL]  │
├──────────────────────┬──────────────────────────────────────────┤
│  Today's P&L: +$1,247│  Win Rate: 68%  │  Trades: 12  │  Open: 4│
│  ████████████████░░░░│  Equity: $52,341 │  Exposure: 32%        │
├──────────────────────┴──────────────────────────────────────────┤
│  [Tab: Command Center] [Tab: Positions] [Tab: Signals]          │
│  [Tab: Cloud Charts] [Tab: Performance] [Tab: Configuration]    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Source Files

### `src/bot_dashboard/__init__.py`
Exports: `BotState`, `BotController`, `DashboardData`

### `src/bot_dashboard/state.py` (~200 lines)
Centralized bot state management.

```python
@dataclass
class BotState:
    """Current state of the trading bot, refreshed every tick."""
    status: Literal["live", "paused", "killed", "paper"]
    instrument_mode: Literal["options", "leveraged_etf", "both"]
    uptime_seconds: int
    account_equity: float
    starting_equity: float                    # Today's starting equity
    daily_pnl: float
    daily_pnl_pct: float
    unrealized_pnl: float
    realized_pnl: float
    open_positions: list[Position]
    open_scalps: list[ScalpPosition]
    pending_signals: list[TradeSignal]
    total_trades_today: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    current_exposure_pct: float               # Total exposure as % of equity
    max_drawdown_today: float
    kill_switch_active: bool
    last_signal_time: datetime | None
    last_trade_time: datetime | None
    active_broker: str
    data_feed_status: str                     # "connected", "delayed", "disconnected"
    errors: list[str]                         # Recent errors

class BotController:
    """Control interface for the trading bot."""

    def pause(self) -> None:
        """Pause signal processing (keep monitoring existing positions)."""
        ...

    def resume(self) -> None:
        """Resume signal processing."""
        ...

    def kill(self, close_day_trades: bool = True) -> None:
        """Emergency stop: halt all trading, optionally close day trade positions."""
        ...

    def get_state(self) -> BotState:
        """Get current bot state snapshot."""
        ...

    def update_config(self, config_updates: dict) -> None:
        """Hot-update configuration without restart."""
        ...
```

### `src/bot_dashboard/metrics.py` (~150 lines)
Performance metrics calculator.

```python
class PerformanceMetrics:
    """Compute trading performance metrics."""

    def daily_metrics(self, trades: list[TradeRecord]) -> DailyMetrics: ...
    def weekly_metrics(self, trades: list[TradeRecord]) -> WeeklyMetrics: ...
    def cumulative_pnl(self, trades: list[TradeRecord]) -> pd.Series: ...
    def win_rate_by_ticker(self, trades: list[TradeRecord]) -> dict[str, float]: ...
    def win_rate_by_conviction(self, trades: list[TradeRecord]) -> dict[str, float]: ...
    def avg_hold_time(self, trades: list[TradeRecord]) -> timedelta: ...
    def profit_factor(self, trades: list[TradeRecord]) -> float: ...
    def sharpe_ratio(self, daily_returns: pd.Series) -> float: ...
    def max_drawdown(self, equity_curve: pd.Series) -> float: ...
    def expectancy(self, trades: list[TradeRecord]) -> float: ...

@dataclass
class DailyMetrics:
    date: date
    total_trades: int
    winners: int
    losers: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    profit_factor: float
    avg_winner: float
    avg_loser: float
    largest_winner: float
    largest_loser: float
    avg_hold_time: timedelta
    stocks_traded: int
    options_scalped: int
    etfs_scalped: int
```

### `src/bot_dashboard/charts.py` (~300 lines)
EMA cloud chart rendering for the dashboard.

```python
class CloudChartRenderer:
    """Render interactive EMA cloud charts using Plotly."""

    def render_cloud_chart(self, df: pd.DataFrame, ticker: str, timeframe: str,
                           signals: list[TradeSignal] = None) -> go.Figure:
        """Create a candlestick chart with EMA cloud overlays.

        Features:
        - Candlestick price data
        - 4 shaded EMA cloud layers (fast, pullback, trend, macro)
        - Signal markers (entry arrows, exit markers)
        - Volume bars
        - Current position levels (entry, stop, target) as horizontal lines
        """
        ...

    def render_equity_curve(self, daily_pnl: list[DailyPnLRecord]) -> go.Figure: ...
    def render_pnl_heatmap(self, trades: list[TradeRecord]) -> go.Figure: ...
    def render_exposure_gauge(self, exposure_pct: float) -> go.Figure: ...
    def render_signal_timeline(self, signals: list[TradeSignal]) -> go.Figure: ...
```

---

## Dashboard Page
`app/pages/bot_control.py` (~600 lines) — added to nav_config.py under "Trading & Execution"

### Tab 1: Command Center
The primary monitoring view.

```
┌──────────────────────────────────────────────────────────────────┐
│  Status: 🟢 LIVE    Uptime: 4h 23m    Broker: Alpaca (Paper)    │
│  Mode: [⚡Options] [📈 Lev. ETF] [🔀 Both]     Instrument: BOTH │
│  [⏸ Pause] [▶ Resume] [🛑 Kill Switch]                          │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ Day P&L  │ Win Rate │ Trades   │ Exposure │ Max Drawdown        │
│ +$1,247  │ 68%      │ 12/7W/5L │ 32%      │ -1.8%               │
│ +2.4%    │          │          │          │                     │
├──────────┴──────────┴──────────┴──────────┴─────────────────────┤
│  [Intraday P&L Chart — line chart updated every 30 seconds]      │
├──────────────────────────────────────────────────────────────────┤
│  Active Positions (5)                                            │
│  NVDA  LONG  150 shares  +$234 (+1.2%)  Stop: $128.50  Cloud: ✅│
│  TSLA  LONG  80 shares   -$45  (-0.3%)  Stop: $245.00  Cloud: ✅│
│  SPY   CALL  3 contracts +$180 (+22%)   Target: 30%    0DTE  OPT│
│  TQQQ  LONG  200 shares  +$156 (+1.8%)  Stop: $71.20   3x   ETF│
│  SOXS  LONG  150 shares  -$48  (-0.5%)  Stop: $4.85    3x   ETF│
├──────────────────────────────────────────────────────────────────┤
│  Recent Signals                                                  │
│  14:23  AAPL  CLOUD_CROSS_BULLISH  Conv: 82  → EXECUTED         │
│  14:15  MSFT  CLOUD_BOUNCE_LONG    Conv: 67  → EXECUTED (half)  │
│  14:08  AMZN  CLOUD_FLIP_BEARISH   Conv: 45  → LOGGED ONLY     │
│  13:55  META  MTF_CONFLUENCE       Conv: 91  → EXECUTED         │
└──────────────────────────────────────────────────────────────────┘
```

### Tab 2: Positions
Detailed position view with management controls.

- Full position table (ticker, direction, shares/contracts, entry, current, P&L, stop, target, time held)
- Per-position EMA cloud mini-chart (shows current cloud state relative to entry)
- Manual override buttons: [Close Position] [Adjust Stop] [Add to Position]
- Position grouping: Day Trades vs Swing Trades vs Options Scalps vs ETF Scalps

### Tab 3: Signals
Live signal feed and history.

- Real-time signal stream with conviction scores and color coding
- Signal heatmap: ticker × timeframe grid showing signal strength
- Filter controls: by conviction, direction, signal type, timeframe
- Signal-to-execution attribution: which signals led to trades and their outcomes

### Tab 4: Cloud Charts
Interactive EMA cloud charting.

- Ticker selector + timeframe tabs (1m, 5m, 10m, 1h, Daily)
- Full EMA cloud chart with all 4 layers shaded
- Signal markers overlaid on chart (arrows for entries/exits)
- Multi-ticker comparison view (2×2 grid)
- Current scan universe displayed as a signal strength table

### Tab 5: Performance
Analytics and reporting.

- Cumulative P&L curve (daily, weekly, monthly views)
- Win rate breakdown: by ticker, by signal type, by conviction level, by time of day
- Profit factor, Sharpe ratio, expectancy, max drawdown
- Calendar heatmap (daily P&L colored green/red)
- Comparison vs buy-and-hold SPY
- Options vs Leveraged ETFs vs Stocks P&L split (by instrument type)

### Tab 6: Configuration
Live configuration management.

- **Instrument Mode selector**: Options / Leveraged ETF / Both (radio buttons with explanation)
  - Shows active ETF universe when Leveraged ETF or Both is selected
  - Shows options settings (delta, IV, strike) when Options or Both is selected
- Risk parameters (editable with validation)
- EMA cloud settings (periods, timeframes)
- Scan universe (add/remove tickers, filter criteria)
- Leveraged ETF settings (preferred leverage, sector mapping, hold limits)
- Broker settings (primary/fallback, paper/live toggle)
- Kill switch parameters
- Schedule (market hours, pre-market scanning, FOMC avoidance)
- **Paper ↔ Live toggle** with confirmation dialog

---

## Data Models (ORM)

```python
class BotSessionRecord(Base):
    __tablename__ = "bot_sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), unique=True, index=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime)
    status = Column(String(20), nullable=False)           # live, paused, killed, paper
    starting_equity = Column(Float, nullable=False)
    ending_equity = Column(Float)
    total_signals = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    config_json = Column(Text)                            # Snapshot of config at session start
    errors_json = Column(Text)
    created_at = Column(DateTime, default=func.now())

class BotEventRecord(Base):
    __tablename__ = "bot_events"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), index=True)
    event_type = Column(String(50), nullable=False)       # signal, trade, error, kill, config_change
    severity = Column(String(10), nullable=False)         # info, warning, error, critical
    message = Column(Text, nullable=False)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=func.now(), index=True)
```

---

## Notification System

The dashboard integrates with `src/alerting/` to send real-time notifications:

| Event | Channel | Priority |
|-------|---------|----------|
| Trade executed | Dashboard + Log | Info |
| Stop loss triggered | Dashboard + Push | Warning |
| Kill switch activated | Dashboard + Push + Sound | Critical |
| Daily loss limit approaching (80%) | Dashboard + Push | Warning |
| Broker disconnection | Dashboard + Push | Critical |
| High-conviction signal (≥90) | Dashboard | Info |
| New daily high P&L | Dashboard | Info |
| Consecutive losses (3+) | Dashboard + Push | Warning |

---

## Configuration

```python
@dataclass
class DashboardConfig:
    refresh_interval_seconds: int = 5         # Dashboard auto-refresh rate
    pnl_chart_lookback_days: int = 30         # Performance chart history
    max_signals_displayed: int = 50           # Signal feed limit
    max_events_displayed: int = 100           # Event log limit
    enable_sound_alerts: bool = True          # Browser sound on critical events
    paper_mode: bool = True                   # Start in paper mode (safety)
    require_confirmation_for_live: bool = True # Double-confirm live mode switch
```

---

## Integration Points

| System | Integration |
|--------|-------------|
| **EMA Signal Engine** (PRD-134) | Reads signal feed for display and attribution |
| **Trade Executor** (PRD-135) | Reads positions, P&L, controls pause/resume/kill |
| **Options Scalper** (PRD-136) | Reads scalp positions, Greeks exposure |
| **Alert System** | `src/alerting/` — push notifications for critical events |
| **Existing Dashboards** | Shares CSS from `app/styles.py`, nav from `app/nav_config.py` |

---

## Alembic Migration
`alembic/versions/137_bot_dashboard.py`
- Creates `bot_sessions` table
- Creates `bot_events` table
- Indexes on `(session_id)`, `(created_at)`, `(event_type)`

---

## Tests
`tests/test_bot_dashboard.py` (~250 lines)

| Test Class | Tests |
|-----------|-------|
| `TestBotState` | State snapshot, status transitions, metric calculations |
| `TestBotController` | Pause/resume/kill lifecycle, config hot-update |
| `TestPerformanceMetrics` | Win rate, profit factor, Sharpe, drawdown, expectancy |
| `TestCloudChartRenderer` | Chart generation with signals, equity curve, heatmap |
| `TestBotEventLog` | Event recording, filtering, session tracking |

---

## Nav Config Updates
Add to `app/nav_config.py` under "Trading & Execution":

```python
st.Page("pages/ema_signals.py", title="EMA Signals", icon=":material/ssid_chart:"),
st.Page("pages/trade_executor.py", title="Trade Executor", icon=":material/bolt:"),
st.Page("pages/options_scalper.py", title="Options Scalper", icon=":material/flash_on:"),
st.Page("pages/bot_control.py", title="Bot Control", icon=":material/smart_toy:"),
```

---

## Startup Sequence

```
1. streamlit run app/streamlit_app.py
2. Navigate to "Bot Control" page
3. Select execution mode: Paper (default) or Live
4. Select instrument mode: Options / Leveraged ETF / Both
5. Configure risk parameters (or use defaults)
6. Click [▶ Start Bot]
7. Bot begins:
   a. UniverseScanner builds daily scan list
   b. DataFeed subscribes to real-time bars
   c. EMACloudEngine computes clouds every tick
   d. SignalDetector emits signals
   e. InstrumentRouter routes signals based on selected mode
   f. TradeExecutor processes stock signals → places orders
   g. OptionsScalper handles 0DTE/1DTE signals (if Options/Both mode)
   h. ETFScalper handles leveraged ETF signals (if Leveraged ETF/Both mode)
   i. ExitMonitor watches all positions (stocks, options, ETFs)
   j. Dashboard refreshes every 5 seconds
8. Kill Switch available at all times
9. Instrument mode can be changed on-the-fly (new signals route to new mode; existing positions managed to completion)
```
