---
name: ripster-ema-trading
description: >
  Ripster EMA Cloud trading methodology for the Axion autonomous bot. Covers the
  5-layer EMA cloud system (5/12, 8/9, 20/21, 34/50, 72/89), signal detection
  (12 types including candlestick patterns), conviction scoring (7 factors),
  pullback-to-cloud entries, trend day detection, session-aware routing,
  multi-timeframe confluence, and 9 exit strategies. Use when configuring,
  debugging, or extending the EMA-based trading bot.
metadata:
  author: axion-platform
  version: "2.0"
---

# Ripster EMA Cloud Trading

## When to Use This Skill

- Configuring EMA cloud layers or modifying cloud periods
- Adding or debugging trade signal detection logic
- Tuning conviction scoring weights or adding new factors
- Implementing or modifying entry strategies (pullback, trend day, session scalp)
- Working with exit strategies (stop loss, trailing, breakeven, scale-out)
- Setting up multi-timeframe confluence analysis
- Debugging why a signal was generated or rejected
- Extending the BotStrategy protocol with new strategies

## The 5-Layer EMA Cloud System

Module: `src/ema_signals/clouds.py` — Core cloud engine computing 5 cloud layers.

| Cloud | Short EMA | Long EMA | Purpose |
|-------|-----------|----------|---------|
| Fast | 5 | 12 | Fluid trendline, day trade entries |
| Pullback | 8 | 9 | Pullback support/resistance |
| Trend | 20 | 21 | Intermediate trend confirmation |
| Macro | 34 | 50 | Major trend bias, risk boundary |
| Long-term | 72 | 89 | Institutional bias, major structure |

```python
from src.ema_signals.clouds import CloudConfig, CloudState, EMACloudCalculator

# Default 5-layer config
config = CloudConfig()  # fast=5/12, pullback=8/9, trend=20/21, macro=34/50, long_term=72/89
calc = EMACloudCalculator(config)

# Compute all clouds on OHLCV DataFrame
df = calc.compute_clouds(ohlcv_df)  # Adds ema_N columns + cloud_X_bull booleans

# Get current cloud states (latest bar)
states = calc.get_cloud_states(df)  # Returns 5 CloudState objects
for cs in states:
    print(f"{cs.cloud_name}: {'bull' if cs.is_bullish else 'bear'} "
          f"slope={cs.slope_direction} thickness={cs.thickness:.4f}")
```

**CloudState** fields: `cloud_name`, `short_ema`, `long_ema`, `is_bullish`, `thickness`, `price_above`, `price_inside`, `price_below`, `slope` (float), `slope_direction` ("rising"/"falling"/"flat").

**Cloud color rules**: When short EMA > long EMA → bullish (green). When short < long → bearish (red). Color transitions are key signals.

## Signal Detection

Module: `src/ema_signals/detector.py` — Detects 12 signal types from cloud states.

```python
from src.ema_signals.detector import SignalDetector, SignalType, TradeSignal

detector = SignalDetector()
signals = detector.detect(ohlcv_df, "AAPL", "5m")
for sig in signals:
    print(f"{sig.signal_type.value}: {sig.direction} conviction={sig.conviction}")
```

**12 Signal Types**:

| Signal | Direction | Trigger |
|--------|-----------|---------|
| `cloud_cross_bullish` | long | Price crosses above cloud |
| `cloud_cross_bearish` | short | Price crosses below cloud |
| `cloud_flip_bullish` | long | Short EMA crosses above long EMA |
| `cloud_flip_bearish` | short | Short EMA crosses below long EMA |
| `cloud_bounce_long` | long | Price tests cloud from above, bounces |
| `cloud_bounce_short` | short | Price tests cloud from below, bounces |
| `trend_aligned_long` | long | All 5 clouds bullish + price above all |
| `trend_aligned_short` | short | All 5 clouds bearish + price below all |
| `momentum_exhaustion` | exit | 3+ candles outside fast cloud |
| `mtf_confluence` | either | Multiple timeframes confirm |
| `candlestick_bullish` | long | Hammer/engulfing/pin bar at cloud |
| `candlestick_bearish` | short | Bearish engulfing/pin bar at cloud |

**Candlestick patterns** only fire when the pattern occurs within `BOUNCE_THRESHOLD` (0.2%) of a cloud level. Detected patterns: hammer, inverted hammer, bullish engulfing, bearish engulfing, bullish pin bar, bearish pin bar.

## Conviction Scoring

Module: `src/ema_signals/conviction.py` — 7-factor scoring system (0-100).

```python
from src.ema_signals.conviction import ConvictionScorer, ConvictionScore

scorer = ConvictionScorer()
score = scorer.score(signal, volume_data={"current_volume": 5e6, "avg_volume": 2e6})
print(f"Total: {score.total}/100 ({score.level})")
```

| Factor | Weight | Description |
|--------|--------|-------------|
| Cloud alignment | 25 | How many clouds agree with direction |
| MTF confluence | 25 | How many timeframes confirm |
| Volume | 15 | Current vs average volume ratio |
| Cloud thickness | 5 | Wider cloud = stronger support |
| Cloud slope | 5 | Aligned slopes boost conviction |
| Candle quality | 10 | Full-body candles score higher |
| Factor score | 15 | Integration with multi-factor model |

Levels: `high` (>=75), `medium` (>=50), `low` (>=25), `none` (<25).

## Entry Strategies

### Pullback-to-Cloud (`src/strategies/pullback_strategy.py`)

Core Ripster entry: trade WITH the trend, enter on pullbacks to cloud support.

```python
from src.strategies import PullbackToCloudStrategy
strategy = PullbackToCloudStrategy()
signal = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
```

Logic: Confirm uptrend (price above macro cloud for 10+ bars) → detect pullback to fast cloud → confirm bounce (close back above) → volume check → signal with stop at macro cloud.

### Trend Day (`src/strategies/trend_day_strategy.py`)

"Market reaches new high/low by 10:00-10:30 AM → it's a trend day."

```python
from src.strategies import TrendDayStrategy
strategy = TrendDayStrategy()
signal = strategy.analyze("SPY", opens, highs, lows, closes, volumes)
```

Logic: Opening range (first 30 min) → breakout within 60 min → cloud alignment + volume surge → ATR expansion > 1.2x → high conviction (80+) signal.

### Session Scalp (`src/strategies/session_scalp_strategy.py`)

Time-of-day routing for different market sessions:

| Session | Time (ET) | Setup | Conviction |
|---------|-----------|-------|------------|
| Open Bell | 9:30-10:30 | ORB + cloud alignment | +10 boost |
| Midday | 10:30-14:00 | Pullback-only, tighter stops | -10 penalty |
| Power Hour | 14:00-16:00 | Momentum continuation + volume | +5 boost |

```python
from src.strategies import SessionScalpStrategy
strategy = SessionScalpStrategy()
signal = strategy.analyze("NVDA", opens, highs, lows, closes, volumes)
```

## Exit Management

Module: `src/trade_executor/exit_monitor.py` — 9 priority-ordered exit strategies.

```python
from src.trade_executor.exit_monitor import ExitMonitor
monitor = ExitMonitor()
exit_sig = monitor.check_all(position, current_price, cloud_states, bars)
if exit_sig:
    print(f"Exit: {exit_sig.exit_type} (priority {exit_sig.priority})")
```

| Priority | Exit Type | Trigger |
|----------|-----------|---------|
| 1 | stop_loss | Price hits stop loss |
| 2 | exhaustion | 3+ candles outside fast cloud |
| 3 | cloud_flip | Fast cloud (5/12) flips against position |
| 4 | target | 2:1 reward-to-risk reached |
| 5 | time_stop | Day trade held >120 min with no progress |
| 6 | eod | Day trade past 3:55 PM ET |
| 7 | trailing | Swing trade: price below pullback cloud |
| 8 | trail_to_breakeven | 1R profit reached → stop moves to breakeven+0.1% |
| 9 | scale_out | 1R profit → sell 50% (partial close) |

**Trail-to-breakeven**: Once position reaches 1:1 R:R profit, stop automatically moves to entry + 0.1% buffer. One-shot — only fires once per position.

**Partial scale-out**: At 1R, signal to sell half the position. Orchestrator handles the partial close (reduces shares, keeps position open with trailing stop on remainder).

## Multi-Timeframe Confluence

Module: `src/ema_signals/mtf.py` — Cross-timeframe signal confirmation.

```python
from src.ema_signals.mtf import MTFEngine
engine = MTFEngine()
mtf_signal = engine.analyze("AAPL", {"5m": df_5m, "1h": df_1h, "1d": df_1d})
```

Default timeframes: 1m, 5m, 10m, 1h, 1d. More confirming timeframes = higher MTF confluence score (up to 25 conviction points).

## Strategy Registration

Module: `src/strategies/` — BotStrategy protocol + StrategyRegistry.

```python
from src.strategies import (
    BotStrategy, StrategyRegistry,
    VWAPStrategy, ORBStrategy, RSIDivergenceStrategy,
    PullbackToCloudStrategy, TrendDayStrategy, SessionScalpStrategy,
)

registry = StrategyRegistry()
registry.register(PullbackToCloudStrategy())
registry.register(TrendDayStrategy())
signals = registry.analyze_all("AAPL", opens, highs, lows, closes, volumes)
```

The `StrategySelector` (`src/strategy_selector/`) uses ADX to route between EMA Cloud (trending) and mean-reversion (ranging) strategies. New strategies integrate via `StrategyBridge` in the bot pipeline.

## Bot Pipeline Integration

The 9-stage orchestrator (`src/bot_pipeline/orchestrator.py`) processes signals through:

1. Kill switch check → 2. Signal guard (freshness + dedup) → 3. Signal recording
4. Risk assessment → 5. Instrument routing → 6. Position sizing
7. Order submission (with retry) → 8. Fill validation → 9. Position creation

Exit monitoring runs continuously via the lifecycle manager, checking all 9 exit conditions on every price update.

## Key Configuration

```python
from src.ema_signals.clouds import EMASignalConfig

config = EMASignalConfig()
config.cloud_config.fast_short = 5      # Fast cloud periods
config.cloud_config.long_term_long = 89 # Long-term cloud
config.min_conviction_to_execute = 50   # Min score to trade
config.high_conviction_threshold = 75   # High-conviction threshold
config.active_timeframes = ["1m", "5m", "10m", "1h", "1d"]
```

## Common Patterns

### Debugging Signal Generation
```python
# Check why a signal was or wasn't generated
detector = SignalDetector(config.cloud_config)
cloud_df = detector.calculator.compute_clouds(df)
states = detector.calculator.get_cloud_states(cloud_df)
for cs in states:
    print(f"{cs.cloud_name}: bull={cs.is_bullish} above={cs.price_above} "
          f"slope={cs.slope_direction}")
```

### Extending with New Strategies
```python
# Implement BotStrategy protocol
class MyStrategy:
    @property
    def name(self) -> str:
        return "my_strategy"

    def analyze(self, ticker, opens, highs, lows, closes, volumes):
        # Your logic here
        return TradeSignal(...) or None

# Register
registry.register(MyStrategy())
```

## See Also

- **trading-signal-generation** — Signal pipeline and fusion
- **qullamaggie-momentum** — Qullamaggie breakout/EP/parabolic short strategies (complementary momentum setups)
- **backtesting-strategies** — Strategy backtesting and walk-forward
- **risk-assessment** — Risk management and position sizing
- **order-execution** — Order routing and broker integration
