# PRD-177: Multi-Strategy Bot

## Overview

Introduces a pluggable strategy system for the trading bot. Defines a `BotStrategy` protocol, provides 3 built-in strategies (VWAP, Opening Range Breakout, RSI Divergence), and a `StrategyRegistry` for runtime registration, enabling, and disabling of strategies.

## Architecture

- **Module**: `src/strategies/`
- **Source files**: `__init__.py`, `base.py`, `vwap_strategy.py`, `orb_strategy.py`, `rsi_divergence.py`, `registry.py`
- **Dependencies**: FusionBridge (PRD-173), BotOrchestrator (PRD-170)

### Strategy Flow

```
Market Data (OHLCV)
  --> StrategyRegistry.analyze_all(ticker, ohlcv)
    --> VWAPStrategy.analyze()     --> Signal | None
    --> ORBStrategy.analyze()      --> Signal | None
    --> RSIDivergenceStrategy.analyze() --> Signal | None
  --> FusionBridge.fuse_signals(signals)
  --> BotOrchestrator.process_signal(fused)
```

## Key Components

### BotStrategy Protocol (`src/strategies/base.py`)

```python
@runtime_checkable
class BotStrategy(Protocol):
    @property
    def name(self) -> str:
        """Unique strategy identifier."""
        ...

    def analyze(
        self, ticker: str, opens: list[float], highs: list[float],
        lows: list[float], closes: list[float], volumes: list[float],
    ) -> "Signal | None":
        """Analyze OHLCV data and return a Signal or None."""
        ...
```

### VWAPStrategy (`src/strategies/vwap_strategy.py`)

Volume-Weighted Average Price mean-reversion strategy.
- Computes VWAP: `sum(typical_price * volume) / sum(volume)`
- **Long**: Price below VWAP by `entry_threshold` (default 0.5%) with rising volume
- **Short**: Price above VWAP by `entry_threshold` with rising volume
- Conviction based on distance from VWAP and volume confirmation (0-100)

### ORBStrategy (`src/strategies/orb_strategy.py`)

Opening Range Breakout strategy for intraday momentum.
- Defines range from first `range_minutes` (default 15) of trading
- **Long**: Price breaks above range high with volume > `volume_multiplier` x average
- **Short**: Price breaks below range low with volume confirmation
- Stop at opposite side of range; TP at `risk_reward_ratio` (default 2.0) x range width

### RSIDivergenceStrategy (`src/strategies/rsi_divergence.py`)

Detects price/RSI divergence for reversal signals.
- **Bullish divergence**: Price lower low + RSI higher low (RSI < 30)
- **Bearish divergence**: Price higher high + RSI lower high (RSI > 70)
- Configurable `period` (default 14), `lookback_bars` (default 5)

### StrategyRegistry (`src/strategies/registry.py`)

| Method | Description |
|--------|-------------|
| `register(strategy)` | Add a strategy (validates BotStrategy protocol) |
| `unregister(name)` | Remove a strategy by name |
| `enable(name)` | Enable a registered strategy |
| `disable(name)` | Disable without removing (preserves config) |
| `analyze_all(ticker, ohlcv)` | Run all enabled strategies, collect signals |
| `list_strategies()` | Returns registered strategies with enabled/disabled status |

## API / Interface

```python
registry = StrategyRegistry()
registry.register(VWAPStrategy(entry_threshold=0.005))
registry.register(ORBStrategy(range_minutes=15))
registry.register(RSIDivergenceStrategy(period=14))

signals = registry.analyze_all("AAPL", opens, highs, lows, closes, volumes)
# [Signal(ticker="AAPL", strategy_name="vwap", direction="long", conviction=72)]

registry.disable("orb")
registry.enable("orb")
```

## Database Schema

### strategy_registry

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| strategy_name | VARCHAR(50) | Unique strategy name |
| strategy_class | VARCHAR(100) | Python class path |
| config_json | Text | Strategy configuration parameters |
| enabled | Boolean | Whether strategy is active |
| registered_at | DateTime | When strategy was registered |
| updated_at | DateTime | Last config or status change |

### strategy_signals

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| signal_id | VARCHAR(50) | Unique signal identifier |
| strategy_name | VARCHAR(50) | Strategy that generated the signal |
| ticker | VARCHAR(20) | Symbol analyzed |
| direction | VARCHAR(10) | long or short |
| conviction | Float | Conviction score (0-100) |
| entry_price | Float | Suggested entry price |
| stop_loss | Float | Stop loss price |
| take_profit | Float | Take profit price |
| metadata_json | Text | Strategy-specific details |
| created_at | DateTime | Signal generation timestamp |

**ORM Models:** `StrategyRegistryRecord`, `StrategySignalRecord` in `src/db/models.py`

## Migration

- **Revision**: 177
- **Down revision**: 176
- **Chain**: `...175 -> 176 -> 177`
- **File**: `alembic/versions/177_multi_strategy.py`
- Creates `strategy_registry` and `strategy_signals` tables
- Indexes on `strategy_name`, `ticker`, `direction`, and `created_at`

## Dashboard

4-tab Streamlit page at `app/pages/multi_strategy.py`:

| Tab | Contents |
|-----|----------|
| Strategy Registry | Registered strategies with enable/disable toggles, config viewer |
| Live Signals | Real-time signal feed from all active strategies |
| Strategy Comparison | Side-by-side performance: win rate, P&L, signal frequency |
| Strategy Builder | Form for registering custom strategies with parameters |

## Testing

~55 tests in `tests/test_multi_strategy.py`:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestBotStrategyProtocol` | ~6 | Protocol compliance, type checking |
| `TestVWAPStrategy` | ~12 | VWAP calculation, long/short signals, thresholds |
| `TestORBStrategy` | ~10 | Range detection, breakout signals, volume filter |
| `TestRSIDivergenceStrategy` | ~10 | RSI computation, divergence detection |
| `TestStrategyRegistry` | ~12 | Register, unregister, enable, disable, analyze_all |
| `TestRegistryEdgeCases` | ~5 | Empty registry, all disabled, duplicate names |

## Dependencies

| Module | Usage |
|--------|-------|
| PRD-173 FusionBridge | Fuses signals from multiple strategies |
| PRD-170 BotOrchestrator | Processes fused signals through pipeline |
| PRD-175 BotPerformanceTracker | Per-strategy performance attribution |
| PRD-134 EMA Signals | Existing strategy (can be wrapped as BotStrategy) |
