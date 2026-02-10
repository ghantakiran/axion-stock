# PRD-178: Ripster EMA Cloud Trading Methodology Upgrade

## Overview

Upgrades the bot's Ripster EMA Cloud coverage from ~65% to ~95% of the full methodology. Adds a 5th cloud layer, slope analysis, candlestick boundary detection, three new entry strategies (pullback, trend day, session scalp), two new exit strategies (trail-to-breakeven, partial scale-out), and refined strategy routing through the existing StrategySelector and StrategyBridge infrastructure.

## Architecture

- **Modules modified**: `src/ema_signals/`, `src/strategies/`, `src/bot_pipeline/`, `src/strategy_selector/`
- **New source files**: `src/strategies/pullback_strategy.py`, `src/strategies/trend_day_strategy.py`, `src/strategies/session_scalp_strategy.py`
- **Dependencies**: EMA Signals (PRD-134), StrategySelector (PRD-165), StrategyBridge (PRD-173), BotOrchestrator (PRD-170), StrategyRegistry (PRD-177)

### Signal Flow

```
Market Data (OHLCV)
  --> EMACloudEngine (5 layers incl. 72/89)
    --> Cloud slope analysis (midpoint ROC)
    --> Candlestick boundary detection
  --> ConvictionScorer (7 factors)
  --> StrategySelector (ADX routing)
    --> PullbackToCloudStrategy | TrendDayStrategy | SessionScalpStrategy
  --> StrategyBridge (OHLCV passthrough)
  --> BotOrchestrator (partial close support)
```

## Core Cloud Engine Changes

### 5th Cloud Layer (`src/ema_signals/clouds.py`)

Adds the 72/89 EMA long-term trend cloud to the existing 4-layer stack:

| Cloud | Short EMA | Long EMA | Purpose |
|-------|-----------|----------|---------|
| 1 (Fast) | 8 | 9 | Immediate momentum |
| 2 | 5 | 12 | Short-term trend |
| 3 | 34 | 50 | Medium-term trend |
| 4 | 20 | 21 | Keltner-style |
| **5 (New)** | **72** | **89** | **Long-term trend bias** |

### Cloud Slope Analysis (`src/ema_signals/clouds.py`)

Computes midpoint rate of change over 5 bars for each cloud:
- `slope = (midpoint[0] - midpoint[-5]) / midpoint[-5]`
- **Rising**: slope > +0.001
- **Flat**: -0.001 <= slope <= +0.001
- **Falling**: slope < -0.001

Slope state feeds into conviction scoring and strategy routing. Rising slope on cloud 5 confirms long-term trend alignment.

### Candlestick Pattern Detection (`src/ema_signals/detector.py`)

Detects reversal patterns when price interacts with cloud boundaries:

| Pattern | Detection Rule |
|---------|---------------|
| Hammer | Small body (< 30% range), long lower wick (> 60% range), at cloud support |
| Engulfing | Current body fully contains prior body, opposite direction, at cloud edge |
| Pin bar | Wick > 2x body, rejection from cloud boundary |

Patterns within 0.2% of a cloud boundary generate `cloud_bounce` signal metadata.

### 7-Factor Conviction Scoring (`src/ema_signals/conviction.py`)

Updated scoring model (was 6 factors, 100 points total):

| Factor | Points | Description |
|--------|--------|-------------|
| Cloud alignment | 25 | All 5 clouds agree on direction |
| Cloud order | 20 | Fast above slow (bull) or below (bear) |
| Volume | 15 | Above 20-bar average |
| Momentum (RSI) | 15 | RSI confirmation of direction |
| **Cloud slope** | **5** | **Rising/falling slope on clouds 3-5** |
| Cloud thickness | 5 | Reduced from 10; wide clouds = strong trend |
| Multi-timeframe | 15 | Higher timeframe confirmation |

## New Entry Strategies

### PullbackToCloudStrategy (`src/strategies/pullback_strategy.py`)

Trend pullback to the fast cloud (8/9 EMA) with bounce confirmation.

- **Entry conditions**: (1) Cloud 5 slope rising (long) or falling (short), (2) price pulls back to cloud 1 boundary, (3) candlestick bounce pattern detected, (4) volume > 80% of 20-bar average
- **Stop**: Below cloud 2 (34/50) midpoint
- **Target**: 2:1 risk-reward ratio
- **Min conviction**: 60

### TrendDayStrategy (`src/strategies/trend_day_strategy.py`)

High-conviction trend day entries combining ORB breakout with full cloud alignment.

- **Entry conditions**: (1) ORB breakout within first 15 minutes, (2) all 5 clouds aligned in breakout direction, (3) volume > 1.5x 20-bar average, (4) ATR expansion > 1.2x 5-day ATR average, (5) conviction >= 80
- **Stop**: ORB opposite boundary
- **Target**: 3:1 risk-reward ratio (trail after 2R)
- **Min conviction**: 80

### SessionScalpStrategy (`src/strategies/session_scalp_strategy.py`)

Time-of-day session routing for intraday scalps.

| Session | Time (ET) | Behavior |
|---------|-----------|----------|
| Open bell | 9:30-10:00 | ORB + cloud alignment, aggressive sizing |
| Midday | 11:30-14:00 | Mean-reversion to VWAP, reduced sizing |
| Power hour | 15:00-16:00 | Trend continuation, momentum follow-through |

Falls back to no signal outside defined sessions. Uses cloud 1 slope for intra-session direction bias.

## New Exit Strategies

### Trail-to-Breakeven (priority 8)

Added to `src/trade_executor/exit_monitor.py`:
- Triggers at 1R profit (unrealized P&L >= 1x initial risk)
- Moves stop to entry price + 0.1% buffer
- Prevents winners from becoming losers

### Partial Scale-Out (priority 9)

Added to `src/trade_executor/exit_monitor.py`:
- Triggers at 1R profit
- Sells 50% of position at market
- Remaining 50% trails with existing exit strategies

### Orchestrator Partial Close Support

`BotOrchestrator.close_position()` in `src/bot_pipeline/orchestrator.py` accepts optional `partial_qty` parameter. When set, submits a reduce-only order for the specified quantity instead of closing the full position.

## Strategy Integration

### StrategySelector Refined Routing (`src/strategy_selector/selector.py`)

Updated decision tree:

```
ADX >= 25 (trending)?
  --> Cloud 5 slope aligned?
    --> Conviction >= 80 + ORB breakout? --> TrendDayStrategy
    --> Pullback to cloud 1?            --> PullbackToCloudStrategy
    --> Default                         --> EMACloudStrategy (existing)
  --> No alignment                      --> EMACloudStrategy (existing)
ADX < 25 (ranging)?
  --> SessionScalpStrategy (if in session window)
  --> MeanReversionStrategy (existing fallback)
```

### StrategyBridge OHLCV Passthrough (`src/bot_pipeline/strategy_bridge.py`)

StrategyBridge updated to pass full OHLCV arrays to strategy `analyze()` methods. Previously only passed `closes`. Now passes `opens`, `highs`, `lows`, `closes`, `volumes` as required by the `BotStrategy` protocol.

### /strategies API Endpoints (`src/api/routes/trading.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/strategies` | GET | List all registered strategies with status |
| `/strategies/{name}/enable` | POST | Enable a strategy |
| `/strategies/{name}/disable` | POST | Disable a strategy |

## Testing

93 new tests in `tests/test_ripster_strategies.py`:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestFifthCloudLayer` | ~10 | 72/89 EMA computation, cloud state |
| `TestCloudSlope` | ~8 | ROC calculation, rising/flat/falling thresholds |
| `TestCandlestickDetection` | ~12 | Hammer, engulfing, pin bar at boundaries |
| `TestConvictionScoring` | ~10 | 7-factor scoring, slope contribution |
| `TestPullbackStrategy` | ~12 | Entry conditions, stop/target, conviction gate |
| `TestTrendDayStrategy` | ~10 | ORB + cloud + volume + ATR, high conviction |
| `TestSessionScalpStrategy` | ~10 | Session routing, time windows, fallback |
| `TestTrailToBreakeven` | ~6 | 1R trigger, stop movement, buffer |
| `TestPartialScaleOut` | ~5 | 50% close, remaining trail |
| `TestOrchestratorPartialClose` | ~4 | partial_qty parameter, reduce-only |
| `TestStrategyRouting` | ~6 | Selector decision tree, fallback paths |

## Files Modified (8)

| File | Changes |
|------|---------|
| `src/ema_signals/clouds.py` | 5th cloud layer (72/89), slope analysis |
| `src/ema_signals/detector.py` | Candlestick pattern detection at cloud boundaries |
| `src/ema_signals/conviction.py` | 7-factor scoring (slope added, thickness reduced) |
| `src/trade_executor/exit_monitor.py` | Trail-to-breakeven (p8), partial scale-out (p9) |
| `src/bot_pipeline/orchestrator.py` | `partial_qty` parameter on `close_position()` |
| `src/bot_pipeline/strategy_bridge.py` | OHLCV passthrough to strategy `analyze()` |
| `src/strategy_selector/selector.py` | Refined routing for Ripster strategies |
| `src/api/routes/trading.py` | `/strategies` list/enable/disable endpoints |

## Files Created (5)

| File | Description |
|------|-------------|
| `src/strategies/pullback_strategy.py` | PullbackToCloudStrategy implementation |
| `src/strategies/trend_day_strategy.py` | TrendDayStrategy implementation |
| `src/strategies/session_scalp_strategy.py` | SessionScalpStrategy implementation |
| `tests/test_ripster_strategies.py` | 93 tests for all new components |
| `skills/ripster-ema-trading/SKILL.md` | Agent skill for Ripster EMA methodology |

## Dependencies

| Module | Usage |
|--------|-------|
| PRD-134 EMA Signals | Core cloud engine being extended |
| PRD-165 StrategySelector | Routing logic refined for new strategies |
| PRD-170 BotOrchestrator | Partial close support added |
| PRD-173 StrategyBridge | OHLCV passthrough to strategies |
| PRD-177 StrategyRegistry | Registration of 3 new strategies |
| PRD-175 BotPerformanceTracker | Per-strategy performance attribution |
