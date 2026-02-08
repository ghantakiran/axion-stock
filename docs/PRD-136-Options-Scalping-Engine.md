# PRD-136: Options Scalping Engine

## Overview
Specialized 0DTE/1DTE options scalping engine using EMA cloud signals on 1-minute charts. Handles the unique requirements of fast options trading: Greeks-aware position sizing, rapid entry/exit, time decay management, and IV-adjusted strike selection. Operates as an extension of the Trade Executor (PRD-135) with options-specific logic.

## Module
`src/options_scalper/` — Options Scalping Engine

---

## Architecture

### Scalping Pipeline

```
1-Min EMA Signal ──→ Strike Selector ──→ Greeks Gate ──→ Position Sizer ──→ Order Router
     │                     │                  │                                    │
     ▼                     ▼                  ▼                                    ▼
 [Conviction ≥ 50]   Select optimal     Validate:                         Broker API
 [Macro bias OK]     strike/expiry      - IV rank                        (Alpaca/IBKR)
 [Volume > avg]      based on:          - Theta burn rate                      │
                     - Delta target      - Bid-ask spread                       ▼
                     - Bid-ask spread    - Open interest              Fill → Exit Monitor
                     - OI/volume                                      - 20-30% profit target
                                                                      - 50% max loss
                                                                      - Momentum exhaustion
                                                                      - Time decay cutoff
```

### Supported Instruments

| Instrument | Strategy | Timeframe |
|-----------|----------|-----------|
| SPY 0DTE/1DTE Calls/Puts | Directional scalps | 1-min / 5-min |
| QQQ 0DTE/1DTE Calls/Puts | Directional scalps | 1-min / 5-min |
| High-Beta Stock Options (NVDA, TSLA, etc.) | 1-5 DTE directional | 1-min / 5-min |
| SPX 0DTE (IBKR only) | Index options scalps | 1-min |

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
Exports: `OptionsScalper`, `StrikeSelector`, `GreeksGate`, `ScalpPosition`, `ScalpConfig`

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
- Indexes on `(ticker, status)`, `(signal_id)`, `(expiry)`

---

## Tests
`tests/test_options_scalper.py` (~300 lines)

| Test Class | Tests |
|-----------|-------|
| `TestStrikeSelector` | Delta filtering, liquidity filtering, strike scoring, 0DTE vs 1DTE preference |
| `TestGreeksGate` | IV rank check, theta burn, spread validation, gamma filter |
| `TestScalpSizer` | Risk-based sizing, conviction adjustment, min/max contracts |
| `TestOptionsScalper` | Full pipeline: signal → strike → greeks → size → order |
| `TestExitLogic` | Profit target, stop loss, exhaustion, time cutoff, cloud flip |
| `TestTimingRules` | Market hours, 0DTE cutoff, FOMC avoidance |

---

## Dashboard Page
`app/pages/options_scalper.py` — added to nav_config.py under "Trading & Execution"

**Tabs:**
1. **Live Scalps** — Active options positions with real-time Greeks, P&L, time-to-expiry countdown
2. **Strike Picker** — Interactive chain view showing selected strikes, delta heatmap
3. **Scalp History** — Trade log with entry/exit reasons, P&L, win rate, avg hold time
4. **Performance** — Cumulative P&L curve, win rate by ticker/time/conviction, best/worst scalps
