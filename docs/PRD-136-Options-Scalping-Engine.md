# PRD-136: Options & Leveraged ETF Scalping Engine

## Overview
Specialized scalping engine using EMA cloud signals on 1-minute charts. Supports two modes: **Options scalping** (0DTE/1DTE with Greeks-aware sizing) and **Leveraged ETF scalping** (3x ETFs for equivalent directional exposure without options complexity). The user selects their preferred instrument via the dashboard's Instrument Mode toggle (PRD-135). Operates as an extension of the Trade Executor (PRD-135) with instrument-specific logic.

## Module
`src/options_scalper/` — Options & Leveraged ETF Scalping Engine

---

## Architecture

### Scalping Pipeline (Dual-Path)

```
                              ┌─── OPTIONS MODE ───────────────────────────────────────┐
                              │ Strike Selector → Greeks Gate → Options Sizer → Order  │
                              │ (0DTE/1DTE calls/puts, delta targeting, IV filter)      │
                              └─────────────────────────────────────────────────────────┘
1-Min EMA Signal ──→ Mode Router ─┤
                              ┌─── LEVERAGED ETF MODE ─────────────────────────────────┐
                              │ ETF Picker → Liquidity Check → ETF Sizer → Order       │
                              │ (TQQQ/SQQQ, SPXL/SPXS, sector 3x ETFs)                │
                              └─────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                                  Fill → Exit Monitor
                                  - 20-30% profit target (options) / 1-3% target (ETFs)
                                  - 50% max loss (options) / 2% max loss (ETFs)
                                  - Momentum exhaustion
                                  - Time decay cutoff (options only)
                                  - Cloud flip
```

### Supported Instruments

**Options Mode:**

| Instrument | Strategy | Timeframe |
|-----------|----------|-----------|
| SPY 0DTE/1DTE Calls/Puts | Directional scalps | 1-min / 5-min |
| QQQ 0DTE/1DTE Calls/Puts | Directional scalps | 1-min / 5-min |
| High-Beta Stock Options (NVDA, TSLA, etc.) | 1-5 DTE directional | 1-min / 5-min |
| SPX 0DTE (IBKR only) | Index options scalps | 1-min |

**Leveraged ETF Mode:**

| Instrument | Bull / Bear | Leverage | Use Case |
|-----------|-------------|----------|----------|
| TQQQ / SQQQ | NASDAQ-100 | 3x | Primary scalp vehicle for QQQ signals |
| SPXL / SPXS | S&P 500 | 3x | Primary scalp vehicle for SPY signals |
| SOXL / SOXS | Semiconductors | 3x | Sector scalps (NVDA, AMD, etc.) |
| FNGU / FNGD | FANG+ | 3x | Mega-cap tech signals |
| TECL / TECS | Technology | 3x | Broad tech sector signals |
| TNA / TZA | Russell 2000 | 3x | Small-cap signals |
| LABU / LABD | Biotech | 3x | Biotech sector signals |
| FAS / FAZ | Financials | 3x | Financial sector signals |
| NUGT / DUST | Gold Miners | 2x | Gold/commodity signals |
| BOIL / KOLD | Natural Gas | 2x | Energy/commodity signals |
| UCO / SCO | Crude Oil | 2x | Oil signals |
| UVXY / SVXY | VIX | 1.5x | Volatility signals |

**ETF Scalp Advantages vs Options:**
- No theta decay (can hold intraday without time penalty)
- No strike selection needed (just buy/sell shares)
- Simpler fills (stock orders vs options chain)
- No minimum contract size (fractional shares possible on Alpaca)
- Available to accounts without options approval

**ETF Scalp Disadvantages vs Options:**
- Lower leverage ceiling (3x vs potentially 10-50x with deep OTM options)
- Daily rebalancing decay on multi-day holds
- Can't define exact risk/reward like options spreads

### Scalping Rules (Ripster-Derived)

**Entry Rules:**
1. Fast cloud (5/12) flips direction on 1-min chart
2. Macro cloud (34/50) on 10-min confirms the same bias (trend filter)
3. Volume bar > 1.5x 20-period average on the trigger candle
4. Enter half position on signal, add second half if first candle tests cloud and bounces

**Exit Rules:**
1. **Profit target**: Take profit at 20-30% gain (don't hold for home runs)
2. **Stop loss**: Cut at 50% loss (hard stop, no exceptions)
3. **Momentum exhaustion**: 3+ consecutive candles close outside fast cloud, same color, no wick touch
4. **Time decay cutoff**: Close 0DTE positions by 2:00 PM ET (theta accelerates)
5. **Cloud flip**: Fast cloud flips against position → immediate exit
6. **No averaging up**: Never add to a losing options position (IV crush risk)

---

## Source Files

### `src/options_scalper/__init__.py`
Exports: `OptionsScalper`, `ETFScalper`, `StrikeSelector`, `GreeksGate`, `ScalpPosition`, `ETFScalpPosition`, `ScalpConfig`

### `src/options_scalper/scalper.py` (~300 lines)
Main scalping engine.

```python
@dataclass
class ScalpPosition:
    ticker: str
    option_symbol: str               # e.g., "SPY250208C00600000"
    option_type: Literal["call", "put"]
    strike: float
    expiry: date
    dte: int                         # Days to expiration
    direction: Literal["long_call", "long_put"]
    contracts: int
    entry_price: float               # Premium paid per contract
    current_price: float
    delta: float
    theta: float
    iv: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_time: datetime
    signal_id: str

class OptionsScalper:
    """0DTE/1DTE options scalping engine."""

    def __init__(self, config: ScalpConfig, executor_router: OrderRouter):
        self.config = config
        self.router = executor_router
        self.strike_selector = StrikeSelector(config)
        self.greeks_gate = GreeksGate(config)
        self.positions: list[ScalpPosition] = []

    async def process_signal(self, signal: TradeSignal) -> ScalpResult | None:
        """Convert EMA signal to options order.

        1. Determine call/put based on signal direction
        2. Select optimal strike (StrikeSelector)
        3. Validate Greeks (GreeksGate)
        4. Size position (max risk per scalp)
        5. Submit order
        """
        ...

    async def monitor_positions(self):
        """Continuously monitor scalp positions for exit triggers."""
        ...

    def _should_scalp(self, signal: TradeSignal) -> bool:
        """Pre-filter: only scalp if macro bias aligns and within trading hours."""
        ...
```

### `src/options_scalper/strike_selector.py` (~200 lines)
Optimal strike and expiry selection.

```python
class StrikeSelector:
    """Select the optimal strike price and expiry for a scalp trade.

    Selection criteria (priority order):
    1. Expiry: 0DTE first, 1DTE if 0DTE not available or after 2 PM
    2. Delta target: 0.30-0.50 for directional scalps (ATM to slightly OTM)
    3. Bid-ask spread: < 10% of option mid price (liquidity filter)
    4. Open interest: > 1,000 contracts (ensures liquidity for exit)
    5. Volume: > 500 contracts traded today
    """

    def select(self, ticker: str, direction: str, chain: OptionsChain) -> StrikeSelection:
        ...

    def _filter_by_delta(self, strikes: list, target_delta: float) -> list: ...
    def _filter_by_liquidity(self, strikes: list) -> list: ...
    def _score_strikes(self, strikes: list) -> list: ...

@dataclass
class StrikeSelection:
    strike: float
    expiry: date
    option_type: Literal["call", "put"]
    option_symbol: str
    delta: float
    gamma: float
    theta: float
    iv: float
    bid: float
    ask: float
    mid: float
    spread_pct: float              # (ask - bid) / mid
    open_interest: int
    volume: int
    score: float                   # Composite selection score
```

### `src/options_scalper/greeks_gate.py` (~150 lines)
Greeks-based validation.

```python
class GreeksGate:
    """Validate that option Greeks are favorable for a scalp trade."""

    def validate(self, selection: StrikeSelection, signal: TradeSignal) -> GreeksDecision:
        """
        Checks:
        1. IV rank < 80th percentile (avoid IV crush after entry)
           Exception: IV rank doesn't matter for 0DTE (theta dominates)
        2. Theta: daily theta burn < 5% of premium for 1DTE+
        3. Bid-ask spread < max_spread_pct
        4. Delta within target range (0.30-0.50)
        5. Gamma check: avoid extreme gamma (>0.15) unless 0DTE
        """
        ...

@dataclass
class GreeksDecision:
    approved: bool
    reason: str | None
    adjustments: dict | None       # e.g., "reduce size due to high IV"
```

### `src/options_scalper/sizing.py` (~100 lines)
Options-specific position sizing.

```python
class ScalpSizer:
    """Position sizing for options scalps.

    Rules:
    - Max risk per scalp: 2% of account equity (tighter than stocks)
    - Max premium at risk: entry_price * contracts * 100
    - Assume max loss = 50% of premium (hard stop)
    - So: max_contracts = (equity * 0.02) / (premium * 100 * 0.50)
    - Conviction adjustment:
      - High (75+): full contracts
      - Medium (50-74): half contracts (min 1)
    - Max 3 concurrent scalp positions
    """

    def calculate(self, premium: float, conviction: int, account_equity: float) -> int:
        ...
```

### `src/options_scalper/etf_scalper.py` (~250 lines)
Leveraged ETF scalping engine (alternative to options scalping).

```python
@dataclass
class ETFScalpPosition:
    ticker: str                          # e.g., "TQQQ"
    original_signal_ticker: str          # e.g., "QQQ"
    leverage: float                      # e.g., 3.0
    direction: Literal["long", "short"]  # long TQQQ = bullish, long SQQQ = bearish
    shares: int
    entry_price: float
    current_price: float
    stop_loss: float
    target_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_time: datetime
    signal_id: str

class ETFScalper:
    """Leveraged ETF scalping as an alternative to options scalping.

    Uses the same EMA cloud signals on 1-min charts but trades
    leveraged ETFs instead of options contracts.
    """

    def __init__(self, config: ScalpConfig, executor_router: OrderRouter):
        self.config = config
        self.router = executor_router
        self.etf_catalog = LEVERAGED_ETF_CATALOG
        self.positions: list[ETFScalpPosition] = []

    async def process_signal(self, signal: TradeSignal) -> ETFScalpResult | None:
        """Convert EMA signal to leveraged ETF order.

        1. Map signal ticker to leveraged ETF (e.g., QQQ bullish → TQQQ)
        2. Check ETF liquidity (volume, spread)
        3. Size position (leverage-adjusted)
        4. Submit order
        """
        ...

    async def monitor_positions(self):
        """Monitor ETF scalp positions with tighter stops (leverage amplifies moves)."""
        ...

    def _map_ticker_to_etf(self, ticker: str, direction: str) -> str | None:
        """Map a signal ticker to its corresponding leveraged ETF.

        Mapping priority:
        1. Direct index: SPY → SPXL/SPXS, QQQ → TQQQ/SQQQ
        2. Sector: NVDA/AMD → SOXL/SOXS, AAPL/MSFT → TECL/TECS
        3. Fallback: use TQQQ/SQQQ for any NASDAQ stock, SPXL/SPXS for any S&P stock
        """
        ...

class ETFScalpSizer:
    """Position sizing for leveraged ETF scalps.

    Key difference from options: risk is linear (not binary).
    - Max risk per scalp: 3% of equity (slightly more than options due to linear risk)
    - Stop loss: 2% of ETF price (leveraged, so ~6% underlying move for 3x)
    - Target: 1-3% of ETF price (leveraged, so ~3-9% underlying move for 3x)
    - Max 5 concurrent ETF scalps (more than options since risk is lower per trade)
    """

    def calculate(self, etf_price: float, leverage: float,
                  conviction: int, account_equity: float) -> int:
        ...
```

---

## Data Models (ORM)

```python
class OptionsScalpRecord(Base):
    __tablename__ = "options_scalps"

    id = Column(Integer, primary_key=True)
    signal_id = Column(String(50), index=True)
    ticker = Column(String(10), nullable=False, index=True)
    option_symbol = Column(String(30), nullable=False)
    option_type = Column(String(4), nullable=False)        # call, put
    strike = Column(Float, nullable=False)
    expiry = Column(Date, nullable=False)
    dte = Column(Integer, nullable=False)
    direction = Column(String(20), nullable=False)          # long_call, long_put
    contracts = Column(Integer, nullable=False)
    entry_premium = Column(Float, nullable=False)
    exit_premium = Column(Float)
    entry_delta = Column(Float)
    entry_theta = Column(Float)
    entry_iv = Column(Float)
    status = Column(String(20), default="open")            # open, closed, expired
    exit_reason = Column(String(50))
    pnl = Column(Float)
    pnl_pct = Column(Float)
    broker = Column(String(20))
    order_id = Column(String(100))
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=func.now())

class ETFScalpRecord(Base):
    __tablename__ = "etf_scalps"

    id = Column(Integer, primary_key=True)
    signal_id = Column(String(50), index=True)
    ticker = Column(String(10), nullable=False, index=True)   # e.g., "TQQQ"
    original_ticker = Column(String(10))                       # e.g., "QQQ"
    leverage = Column(Float, nullable=False)
    direction = Column(String(10), nullable=False)
    shares = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    stop_loss = Column(Float)
    target_price = Column(Float)
    status = Column(String(20), default="open")
    exit_reason = Column(String(50))
    pnl = Column(Float)
    pnl_pct = Column(Float)
    broker = Column(String(20))
    order_id = Column(String(100))
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=func.now())
```

---

## Configuration

```python
@dataclass
class ScalpConfig:
    # Instruments
    scalp_tickers: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT", "META", "AMZN"])
    allow_spx: bool = True                    # SPX 0DTE (IBKR only)

    # Strike selection
    target_delta_min: float = 0.30
    target_delta_max: float = 0.50
    max_spread_pct: float = 0.10              # 10% bid-ask spread max
    min_open_interest: int = 1000
    min_volume: int = 500

    # Risk (tighter than stock trades)
    max_risk_per_scalp: float = 0.02          # 2% of equity per scalp
    max_loss_pct: float = 0.50                # 50% of premium = stop loss
    profit_target_pct: float = 0.25           # 25% profit target
    max_concurrent_scalps: int = 3
    no_average_up: bool = True                # Never add to losing options

    # Greeks
    max_iv_rank: float = 0.80                 # 80th percentile IV rank
    max_theta_burn_pct: float = 0.05          # 5% daily theta burn
    max_gamma: float = 0.15                   # Extreme gamma filter

    # Timing
    scalp_start_time: str = "09:35"           # 5 min after open (avoid opening volatility)
    zero_dte_cutoff: str = "14:00"            # 2 PM ET for 0DTE (theta cliff)
    one_dte_cutoff: str = "15:30"             # 3:30 PM for 1DTE
    no_scalp_around_fomc: bool = True         # Skip scalps 30 min before/after FOMC

    # Execution
    entry_order_type: str = "limit"           # Always limit for options (spreads)
    limit_offset: float = 0.02                # $0.02 above mid for fills
    fill_timeout_seconds: int = 15            # Cancel unfilled orders after 15s

    # Conviction
    min_conviction_to_scalp: int = 50
    require_macro_alignment: bool = True      # 10-min macro cloud must agree

    # ── Leveraged ETF Scalp Settings ─────────────────
    etf_max_risk_per_scalp: float = 0.03      # 3% of equity per ETF scalp
    etf_stop_loss_pct: float = 0.02           # 2% of ETF price
    etf_profit_target_pct: float = 0.02       # 2% of ETF price (adjustable 1-3%)
    etf_max_concurrent_scalps: int = 5
    etf_min_daily_volume: float = 10_000_000  # $10M min avg daily volume
    etf_max_spread_pct: float = 0.05          # 0.05% bid-ask spread max
    etf_prefer_3x: bool = True                # Prefer 3x over 2x for scalps
    etf_sector_mapping_enabled: bool = True   # Map individual stocks to sector ETFs
```

---

## Integration Points

| System | Integration |
|--------|-------------|
| **EMA Signal Engine** (PRD-134) | Consumes 1-min signals routed to scalper |
| **Trade Executor** (PRD-135) | Shares `OrderRouter` and `RiskGate` for order submission |
| **Options Analytics** | `src/options/` — existing chain analysis, IV calculation |
| **Bot Dashboard** (PRD-137) | Live scalp positions, P&L, Greeks exposure |
| **Alpaca** | Options orders via Alpaca Options API |
| **IBKR** | SPX 0DTE + all options via ib_insync |

---

## Alembic Migration
`alembic/versions/136_options_scalper.py`
- Creates `options_scalps` table
- Creates `etf_scalps` table
- Indexes on `(ticker, status)`, `(signal_id)`, `(expiry)` for options
- Indexes on `(ticker, status)`, `(signal_id)` for ETFs

---

## Tests
`tests/test_options_scalper.py` (~300 lines)

| Test Class | Tests |
|-----------|-------|
| `TestStrikeSelector` | Delta filtering, liquidity filtering, strike scoring, 0DTE vs 1DTE preference |
| `TestGreeksGate` | IV rank check, theta burn, spread validation, gamma filter |
| `TestScalpSizer` | Risk-based sizing, conviction adjustment, min/max contracts |
| `TestOptionsScalper` | Full pipeline: signal → strike → greeks → size → order |
| `TestETFScalper` | Signal → ETF mapping → liquidity → size → order |
| `TestETFScalpSizer` | Leverage-adjusted sizing, stop/target calculation, max concurrent |
| `TestTickerToETFMapping` | Individual stock → sector ETF mapping, index fallback |
| `TestExitLogic` | Profit target, stop loss, exhaustion, time cutoff, cloud flip (both modes) |
| `TestTimingRules` | Market hours, 0DTE cutoff, FOMC avoidance |

---

## Dashboard Page
`app/pages/options_scalper.py` — added to nav_config.py under "Trading & Execution"

**Tabs:**
1. **Live Scalps** — Active options AND/OR ETF positions with real-time P&L (Greeks for options, leverage for ETFs)
2. **Strike Picker / ETF Picker** — Options chain view with delta heatmap OR leveraged ETF selector with liquidity indicators
3. **Scalp History** — Unified trade log with instrument_type column, entry/exit reasons, P&L, win rate, avg hold time
4. **Performance** — Cumulative P&L curve split by instrument type (Options vs ETF), win rate by ticker/time/conviction
5. **Mode Comparison** — Side-by-side backtest of same signals executed as options vs leveraged ETFs
