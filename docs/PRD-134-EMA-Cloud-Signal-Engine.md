# PRD-134: EMA Cloud Signal Engine

## Overview
Core signal generation engine implementing the Ripster EMA Cloud methodology. Computes EMA cloud layers across multiple timeframes, detects crossovers, trend confirmations, and momentum shifts. Produces structured trade signals consumed by the Trade Executor (PRD-135) and Options Scalper (PRD-136).

## Background
The Ripster EMA Cloud system uses shaded areas between EMA pairs as dynamic support/resistance zones. When price crosses above a cloud, it signals bullish momentum; below signals bearish. Multiple cloud layers (fast, pullback, trend, macro) at different timeframes create a conviction hierarchy from scalp to swing.

## Module
`src/ema_signals/` — EMA Cloud Signal Engine

---

## Architecture

### EMA Cloud Layers

| Cloud | EMA Pair | Role | Color |
|-------|----------|------|-------|
| **Fast** | 5 / 12 | Fluid trendline for day trades; primary entry/exit trigger | Cyan/Blue |
| **Pullback** | 8 / 9 | Pullback support/resistance levels | Yellow |
| **Trend** | 20 / 21 | Intermediate trend confirmation | Purple |
| **Macro** | 34 / 50 | Major trend bias; risk boundary for stops | Red/Green |

### Timeframe Matrix

| Timeframe | Use Case | Signal Type |
|-----------|----------|-------------|
| **1 min** | Options scalping (0DTE/1DTE) | Micro signals |
| **5 min** | Fast day trade confirmation | Confirmation layer |
| **10 min** | Primary day trading | Core signals |
| **1 hour** | Swing entry/exit | Swing signals |
| **Daily** | Macro trend bias | Trend filter |

### Signal Types

```python
class SignalType(str, Enum):
    CLOUD_CROSS_BULLISH = "cloud_cross_bullish"    # Price crosses above cloud
    CLOUD_CROSS_BEARISH = "cloud_cross_bearish"    # Price crosses below cloud
    CLOUD_FLIP_BULLISH = "cloud_flip_bullish"      # Fast EMA crosses above slow EMA (cloud turns green)
    CLOUD_FLIP_BEARISH = "cloud_flip_bearish"      # Fast EMA crosses below slow EMA (cloud turns red)
    CLOUD_BOUNCE_LONG = "cloud_bounce_long"        # Price tests cloud from above and bounces
    CLOUD_BOUNCE_SHORT = "cloud_bounce_short"      # Price tests cloud from below and rejects
    TREND_ALIGNED_LONG = "trend_aligned_long"      # All clouds aligned bullish
    TREND_ALIGNED_SHORT = "trend_aligned_short"    # All clouds aligned bearish
    MOMENTUM_EXHAUSTION = "momentum_exhaustion"    # 3+ candles closing outside cloud (exit signal)
    MTF_CONFLUENCE = "mtf_confluence"              # Multiple timeframes agree
```

### Conviction Scoring (0–100)

Each signal receives a conviction score based on:

| Factor | Weight | Criteria |
|--------|--------|----------|
| Cloud alignment | 25% | How many cloud layers agree (fast + pullback + trend + macro) |
| MTF confluence | 25% | How many timeframes confirm the same direction |
| Volume confirmation | 15% | Current volume vs 20-period average (>1.5x = confirmed) |
| Cloud thickness | 10% | Wider cloud = stronger support/resistance |
| Candle quality | 10% | Full-body candles closing through cloud > wicks/dojis |
| Axion factor score | 15% | Integration with existing multi-factor model (value + momentum + quality + growth) |

**Conviction thresholds:**
- **High (75–100)**: All clouds aligned, MTF confirmed, volume surge → auto-execute
- **Medium (50–74)**: Most clouds agree, partial MTF → auto-execute with reduced size
- **Low (25–49)**: Mixed signals → log only, no execution
- **No signal (<25)**: Noise → discard

---

## Source Files

### `src/ema_signals/__init__.py`
Exports: `EMACloudEngine`, `SignalType`, `TradeSignal`, `ConvictionScore`, `CloudState`

### `src/ema_signals/clouds.py` (~250 lines)
EMA cloud computation engine.

```python
@dataclass
class CloudConfig:
    fast_short: int = 5
    fast_long: int = 12
    pullback_short: int = 8
    pullback_long: int = 9
    trend_short: int = 20
    trend_long: int = 21
    macro_short: int = 34
    macro_long: int = 50

@dataclass
class CloudState:
    """State of a single EMA cloud at a point in time."""
    cloud_name: str              # "fast", "pullback", "trend", "macro"
    short_ema: float
    long_ema: float
    is_bullish: bool             # short > long
    thickness: float             # abs(short - long) as % of price
    price_above: bool            # current price above both EMAs
    price_inside: bool           # price between the two EMAs
    price_below: bool            # price below both EMAs

class EMACloudCalculator:
    """Compute EMA clouds from OHLCV data."""

    def __init__(self, config: CloudConfig = CloudConfig()):
        self.config = config

    def compute_clouds(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add EMA cloud columns to a DataFrame with OHLCV data.

        Adds columns: ema_5, ema_12, ema_8, ema_9, ema_20, ema_21, ema_34, ema_50,
        cloud_fast_bull, cloud_pullback_bull, cloud_trend_bull, cloud_macro_bull
        """
        ...

    def get_cloud_states(self, df: pd.DataFrame) -> list[CloudState]:
        """Return current CloudState for all 4 layers."""
        ...
```

### `src/ema_signals/detector.py` (~300 lines)
Signal detection logic.

```python
@dataclass
class TradeSignal:
    signal_type: SignalType
    direction: Literal["long", "short"]
    ticker: str
    timeframe: str                # "1m", "5m", "10m", "1h", "1d"
    conviction: int               # 0–100
    entry_price: float
    stop_loss: float              # Below macro cloud for longs, above for shorts
    target_price: float | None    # Optional profit target
    cloud_states: list[CloudState]
    timestamp: datetime
    metadata: dict                # Volume ratio, candle pattern, factor scores, etc.

class SignalDetector:
    """Detect trade signals from EMA cloud states."""

    def detect(self, df: pd.DataFrame, ticker: str, timeframe: str) -> list[TradeSignal]:
        """Scan latest bars for entry/exit signals."""
        ...

    def _detect_cloud_cross(self, df, cloud_name) -> TradeSignal | None: ...
    def _detect_cloud_flip(self, df, cloud_name) -> TradeSignal | None: ...
    def _detect_cloud_bounce(self, df, cloud_name) -> TradeSignal | None: ...
    def _detect_momentum_exhaustion(self, df) -> TradeSignal | None: ...
    def _detect_trend_alignment(self, df) -> TradeSignal | None: ...
```

### `src/ema_signals/mtf.py` (~200 lines)
Multi-timeframe confluence engine.

```python
class MTFEngine:
    """Aggregate signals across timeframes for confluence scoring."""

    TIMEFRAMES = ["1m", "5m", "10m", "1h", "1d"]

    def compute_confluence(self, signals_by_tf: dict[str, list[TradeSignal]]) -> list[TradeSignal]:
        """Merge signals across timeframes, boost conviction when aligned."""
        ...

    def get_macro_bias(self, daily_clouds: list[CloudState]) -> Literal["bullish", "bearish", "neutral"]:
        """Determine overall market bias from daily macro cloud."""
        ...
```

### `src/ema_signals/conviction.py` (~150 lines)
Conviction scoring system.

```python
@dataclass
class ConvictionScore:
    total: int                     # 0–100
    cloud_alignment: float         # 0–25
    mtf_confluence: float          # 0–25
    volume_confirmation: float     # 0–15
    cloud_thickness: float         # 0–10
    candle_quality: float          # 0–10
    factor_score: float            # 0–15
    breakdown: dict                # Detailed scoring breakdown

class ConvictionScorer:
    """Score signal conviction using multi-factor criteria."""

    def score(self, signal: TradeSignal, volume_data: dict, factor_scores: dict | None) -> ConvictionScore:
        ...
```

### `src/ema_signals/scanner.py` (~250 lines)
Dynamic universe scanner.

```python
class UniverseScanner:
    """Scan a dynamic universe of tickers for EMA cloud signals.

    Builds the daily scan list using:
    1. Axion factor scores (top momentum + quality stocks)
    2. Unusual volume filter (>2x 20-day avg)
    3. Minimum liquidity threshold ($5M avg daily volume)
    4. Earnings/event exclusion (skip tickers with earnings in next 2 days)
    """

    def build_scan_list(self) -> list[str]:
        """Return today's tickers to scan (~30-80 tickers)."""
        ...

    def scan_all(self, tickers: list[str]) -> list[TradeSignal]:
        """Run EMA cloud detection across all tickers and timeframes."""
        ...

    def rank_by_conviction(self, signals: list[TradeSignal]) -> list[TradeSignal]:
        """Sort signals by conviction score, return top N."""
        ...
```

### `src/ema_signals/data_feed.py` (~200 lines)
Market data acquisition for real-time and historical bars.

```python
class DataFeed:
    """Fetch OHLCV bars from Polygon/Yahoo Finance/Alpaca.

    Supports:
    - Historical bars for backtesting and initial cloud computation
    - Real-time/streaming bars for live signal detection
    - WebSocket subscription for 1-min bars
    """

    def get_bars(self, ticker: str, timeframe: str, lookback: int = 200) -> pd.DataFrame: ...
    def subscribe_realtime(self, tickers: list[str], callback: Callable) -> None: ...
    def unsubscribe(self, tickers: list[str]) -> None: ...
```

---

## Data Models (ORM)

```python
class EMASignalRecord(Base):
    __tablename__ = "ema_signals"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), nullable=False, index=True)
    signal_type = Column(String(50), nullable=False)
    direction = Column(String(10), nullable=False)        # "long" or "short"
    timeframe = Column(String(10), nullable=False)
    conviction = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float)
    target_price = Column(Float)
    cloud_states_json = Column(Text)                      # JSON serialized cloud states
    metadata_json = Column(Text)                          # JSON serialized metadata
    created_at = Column(DateTime, default=func.now(), index=True)
    executed = Column(Boolean, default=False)              # Picked up by executor?
    execution_id = Column(String(50))                     # Link to trade execution
```

---

## Integration Points

| System | Integration |
|--------|-------------|
| **Axion Factor Scores** | `src/services/scoring.py` — factor scores boost/penalize conviction |
| **Data Sources** | Polygon (real-time), Yahoo Finance (historical fallback), Alpaca (streaming) |
| **Trade Executor** (PRD-135) | Signals pushed to executor queue when conviction ≥ 50 |
| **Options Scalper** (PRD-136) | 1-min signals routed to options scalper module |
| **Bot Dashboard** (PRD-137) | Live signal feed displayed on monitoring dashboard |
| **Alert System** | `src/alerting/` — high-conviction signals fire alerts |

---

## Configuration

```python
@dataclass
class EMASignalConfig:
    # Cloud parameters
    cloud_config: CloudConfig = field(default_factory=CloudConfig)

    # Scanning
    scan_interval_seconds: int = 30           # How often to scan for new signals
    max_tickers_per_scan: int = 80            # Max tickers in daily universe
    min_daily_volume: float = 5_000_000       # $5M min avg daily volume
    unusual_volume_threshold: float = 2.0     # 2x 20-day avg = unusual
    earnings_exclusion_days: int = 2          # Skip tickers with earnings in N days

    # Conviction
    min_conviction_to_signal: int = 25        # Below this = discard
    min_conviction_to_execute: int = 50       # Below this = log only
    high_conviction_threshold: int = 75       # Full position size

    # Timeframes to scan
    active_timeframes: list[str] = field(default_factory=lambda: ["1m", "5m", "10m", "1h", "1d"])

    # Market hours
    pre_market_scan: bool = True              # Scan pre-market (4am–9:30am ET)
    after_hours_scan: bool = False            # Scan after hours

    # Data source priority
    data_source: str = "polygon"              # "polygon", "alpaca", "yahoo"
```

---

## Alembic Migration
`alembic/versions/134_ema_signals.py`
- Creates `ema_signals` table
- Indexes on `(ticker, created_at)` and `(conviction, executed)`

---

## Tests
`tests/test_ema_signals.py` (~300 lines)

| Test Class | Tests |
|-----------|-------|
| `TestEMACloudCalculator` | Compute EMAs, verify cloud states, handle edge cases (insufficient data) |
| `TestSignalDetector` | Detect each signal type (cross, flip, bounce, exhaustion, alignment) |
| `TestConvictionScorer` | Score breakdown, threshold boundaries, factor score integration |
| `TestMTFEngine` | Single-TF vs multi-TF confluence, macro bias determination |
| `TestUniverseScanner` | Scan list building, filtering, ranking |
| `TestDataFeed` | Bar fetching, WebSocket subscription mock |

---

## Dashboard Page
`app/pages/ema_signals.py` — added to nav_config.py under "Trading & Execution"

**Tabs:**
1. **Live Signals** — Real-time signal feed with conviction bars, cloud visualization
2. **Scanner** — Current scan universe, filter controls, signal heatmap
3. **Cloud Charts** — Interactive EMA cloud chart for any ticker/timeframe (Plotly)
4. **Signal History** — Historical signal log with P&L attribution (post-execution)
