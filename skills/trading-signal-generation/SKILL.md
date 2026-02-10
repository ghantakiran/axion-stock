---
name: trading-signal-generation
description: Generate trading signals from EMA clouds, multi-source fusion, regime-aware parameters, and the multi-strategy framework. Covers the full pipeline from raw OHLCV data through conviction scoring, signal fusion across 7 sources, adaptive weight feedback, and pluggable strategies (VWAP, ORB, RSI Divergence). Use when building or debugging signal generation, fusion weights, or strategy registration.
metadata:
  author: axion-platform
  version: "1.0"
---

# Trading Signal Generation

## When to use this skill

Use this skill when you need to:
- Generate EMA cloud trading signals from OHLCV price data
- Fuse signals from multiple sources (EMA, social, factor, ML, sentiment, technical, fundamental) into a consensus recommendation
- Implement or register new trading strategies using the BotStrategy protocol
- Adjust signal fusion weights based on rolling source performance
- Debug signal detection, conviction scoring, or fusion pipeline issues
- Understand the 10 EMA signal types and their detection logic

## Step-by-step instructions

### 1. Generate EMA Cloud Signals

The signal generation pipeline starts with raw OHLCV data and produces `TradeSignal` objects:

```
OHLCV DataFrame -> EMACloudCalculator.compute_clouds() -> SignalDetector.detect() -> ConvictionScorer.score() -> TradeSignal
```

**Source files:**
- `src/ema_signals/clouds.py` -- EMA cloud computation (5 layers incl. 72/89 long-term)
- `src/ema_signals/detector.py` -- Signal detection (12 types incl. candlestick patterns)
- `src/ema_signals/conviction.py` -- Conviction scoring 0-100 (7 factors incl. slope)
- `src/ema_signals/mtf.py` -- Multi-timeframe confluence engine
- `src/ema_signals/scanner.py` -- Universe scanner for batch detection

### 2. Fuse Multiple Signal Sources

After generating EMA signals, fuse them with other sources:

```
RawSignal[] -> SignalFusion.fuse() -> FusedSignal -> TradeRecommender.recommend() -> Recommendation
```

**Source files:**
- `src/signal_fusion/collector.py` -- Signal collection and normalization
- `src/signal_fusion/fusion.py` -- Weighted fusion engine with time decay
- `src/signal_fusion/recommender.py` -- Action classification and position sizing
- `src/signal_fusion/agent.py` -- Autonomous fusion agent loop

### 3. Register and Run Multi-Strategy Analysis

Use the strategy registry to run multiple strategies and collect signals:

```
StrategyRegistry.register(strategy) -> registry.analyze_all(ticker, OHLCV) -> [(name, TradeSignal)]
```

**Source files:**
- `src/strategies/base.py` -- BotStrategy protocol
- `src/strategies/registry.py` -- Central strategy registry
- `src/strategies/vwap_strategy.py` -- VWAP mean-reversion
- `src/strategies/orb_strategy.py` -- Opening range breakout
- `src/strategies/rsi_divergence.py` -- RSI divergence detection
- `src/strategies/pullback_strategy.py` -- Ripster pullback-to-cloud entry
- `src/strategies/trend_day_strategy.py` -- ORB + cloud alignment trend day
- `src/strategies/session_scalp_strategy.py` -- Session-aware intraday routing

### 4. TradingView Scanner Signals

Use the TV Scanner for live market screening as an additional signal source:

```
TVScreener.scan(preset) -> ScreenerResult[] -> SignalBridge.to_raw_signals() -> RawSignal[]
```

**Source files:**
- `src/tv_scanner/screener.py` -- TradingView screener (6 asset classes, 14 presets)
- `src/tv_scanner/presets.py` -- Momentum, value, volume, growth, crypto presets
- `src/tv_scanner/bridge.py` -- Cross-module bridge to signal/EMA systems
- `src/tv_scanner/streaming.py` -- Continuous scan streaming mode

### 5. Signal Persistence and Audit Trail

Record every signal through the pipeline for full traceability:

```
SignalRecord -> FusionRecord -> RiskDecisionRecord -> ExecutionRecord
```

**Source files:**
- `src/signal_persistence/store.py` -- Thread-safe signal store
- `src/signal_persistence/models.py` -- SignalRecord, FusionRecord, RiskDecisionRecord, ExecutionRecord
- `src/signal_persistence/query.py` -- Query builder for signal audit trail

### 6. Close the Feedback Loop

Track signal source performance and adapt fusion weights:

```
PerformanceTracker.record_outcome() -> WeightAdjuster.compute_weights() -> FusionConfig.source_weights
```

**Source files:**
- `src/signal_feedback/tracker.py` -- Rolling Sharpe per source
- `src/signal_feedback/adjuster.py` -- Adaptive weight adjustment
- `src/signal_feedback/weight_store.py` -- Weight history persistence

## Code examples

### Generate EMA Cloud Signals

```python
import pandas as pd
from src.ema_signals import (
    CloudConfig,
    EMACloudCalculator,
    SignalDetector,
    ConvictionScorer,
    TradeSignal,
    SignalType,
)

# Configure the 5 cloud layers (Ripster methodology)
config = CloudConfig(
    fast_short=5,    fast_long=12,     # Fast cloud
    pullback_short=8, pullback_long=9,  # Pullback cloud
    trend_short=20,  trend_long=21,     # Trend cloud
    macro_short=34,  macro_long=50,     # Macro cloud
    long_term_short=72, long_term_long=89,  # Long-term cloud
)

# Compute clouds from OHLCV DataFrame (needs 89+ bars for 5th layer)
calculator = EMACloudCalculator(config)
cloud_df = calculator.compute_clouds(ohlcv_df)
cloud_states = calculator.get_cloud_states(cloud_df)  # 5 CloudState objects
# Each CloudState has: is_bullish, thickness, slope, slope_direction

# Detect signals across all 5 cloud layers
detector = SignalDetector(config)
signals = detector.detect(ohlcv_df, ticker="AAPL", timeframe="5m")

# Score each signal's conviction (0-100)
scorer = ConvictionScorer()
for signal in signals:
    score = scorer.score(
        signal,
        volume_data={"current_volume": 12_000_000, "avg_volume": 8_000_000},
        factor_scores={"composite": 0.72},
    )
    signal.conviction = score.total
    print(f"{signal.signal_type.value}: conviction={score.total} ({score.level})")
    print(f"  Cloud alignment: {score.cloud_alignment}")
    print(f"  Volume confirmation: {score.volume_confirmation}")
```

### Fuse Signals from Multiple Sources

```python
from datetime import datetime, timezone
from src.signal_fusion import (
    SignalSource,
    RawSignal,
    FusionConfig,
    SignalFusion,
    TradeRecommender,
    RecommenderConfig,
    DEFAULT_SOURCE_WEIGHTS,
)

# Default source weights:
# EMA_CLOUD: 0.25, FACTOR: 0.20, SOCIAL: 0.15, ML_RANKING: 0.15,
# SENTIMENT: 0.10, TECHNICAL: 0.10, FUNDAMENTAL: 0.05

# Create raw signals from various sources
signals = [
    RawSignal(
        symbol="AAPL", source=SignalSource.EMA_CLOUD,
        direction="bullish", strength=85.0, confidence=0.82,
        timestamp=datetime.now(timezone.utc),
    ),
    RawSignal(
        symbol="AAPL", source=SignalSource.FACTOR,
        direction="bullish", strength=70.0, confidence=0.68,
        timestamp=datetime.now(timezone.utc),
    ),
    RawSignal(
        symbol="AAPL", source=SignalSource.SENTIMENT,
        direction="bearish", strength=55.0, confidence=0.45,
        timestamp=datetime.now(timezone.utc),
    ),
]

# Fuse into a consensus
fusion = SignalFusion(FusionConfig(min_sources=2, decay_minutes=60.0))
fused = fusion.fuse(signals)
print(f"Direction: {fused.direction}")          # bullish
print(f"Composite: {fused.composite_score:+.1f}")  # +42.3
print(f"Confidence: {fused.confidence:.2f}")     # 0.71
print(f"Agreement: {len(fused.agreeing_sources)}/{fused.source_count}")

# Convert to actionable recommendation
recommender = TradeRecommender(RecommenderConfig(
    min_confidence=0.5,
    max_positions=10,
    max_single_weight=0.15,
    risk_tolerance="moderate",
))
rec = recommender.recommend(fused)
if rec:
    print(f"Action: {rec.action}")              # BUY
    print(f"Size: {rec.position_size_pct:.1f}%") # 10.7%
    print(f"Stop: {rec.stop_loss_pct:.1f}%")     # 3.2%
    print(f"Target: {rec.take_profit_pct:.1f}%")  # 6.5%

# Batch: fuse and recommend for entire portfolio
batch_signals = {"AAPL": signals, "MSFT": msft_signals}
fused_batch = fusion.fuse_batch(batch_signals)
recs = recommender.recommend_portfolio(fused_batch)
```

### Register and Run Multiple Strategies

```python
from src.strategies import (
    BotStrategy,
    StrategyRegistry,
    VWAPStrategy,
    ORBStrategy,
    RSIDivergenceStrategy,
)
from src.strategies.vwap_strategy import VWAPConfig
from src.strategies.orb_strategy import ORBConfig

# Create and configure strategies
vwap = VWAPStrategy(VWAPConfig(
    rsi_period=14,
    rsi_oversold=40.0,
    rsi_overbought=60.0,
    vwap_deviation_pct=0.5,
))
orb = ORBStrategy(ORBConfig(
    opening_range_bars=3,     # 3 x 5min = 15-minute range
    volume_multiplier=1.5,
    risk_reward=2.0,
))
rsi_div = RSIDivergenceStrategy()

# Import Ripster strategies
from src.strategies import PullbackToCloudStrategy, TrendDayStrategy, SessionScalpStrategy

# Register all strategies
registry = StrategyRegistry()
registry.register(vwap, description="VWAP mean-reversion", category="mean_reversion")
registry.register(orb, description="Opening range breakout", category="breakout")
registry.register(rsi_div, description="RSI divergence", category="divergence")
registry.register(PullbackToCloudStrategy(), description="Pullback to cloud", category="trend")
registry.register(TrendDayStrategy(), description="Trend day detection", category="trend")
registry.register(SessionScalpStrategy(), description="Session-aware scalping", category="scalping")

# Run all enabled strategies on a ticker
results = registry.analyze_all(
    ticker="AAPL",
    opens=open_prices,
    highs=high_prices,
    lows=low_prices,
    closes=close_prices,
    volumes=volume_data,
)
for strategy_name, signal in results:
    print(f"[{strategy_name}] {signal.direction} @ {signal.entry_price}")

# Enable/disable strategies dynamically
registry.disable("orb_breakout")
registry.enable("orb_breakout")
print(registry.list_strategies())
```

### Adaptive Signal Feedback Loop

```python
from src.signal_feedback import (
    PerformanceTracker,
    TrackerConfig,
    WeightAdjuster,
    AdjusterConfig,
)

# Track rolling performance per source
tracker = PerformanceTracker(TrackerConfig(
    rolling_window=100,
    min_trades_for_stats=10,
    risk_free_rate=0.05,
))

# Record trade outcomes
tracker.record_outcome("ema_cloud", pnl=150.0, conviction=82.0)
tracker.record_outcome("ema_cloud", pnl=-50.0, conviction=65.0)
tracker.record_outcome("social", pnl=80.0, conviction=70.0)
tracker.record_outcome("factor", pnl=-30.0, conviction=55.0)

# Get performance metrics
ema_perf = tracker.get_performance("ema_cloud")
print(f"EMA Sharpe: {ema_perf.sharpe_ratio:.2f}")
print(f"EMA Win Rate: {ema_perf.win_rate:.1%}")
print(f"EMA Profit Factor: {ema_perf.profit_factor:.2f}")

# Get ranked sources by Sharpe ratio
ranked = tracker.get_ranked_sources()
for perf in ranked:
    print(f"  {perf.source}: Sharpe={perf.sharpe_ratio:.2f}, PnL={perf.total_pnl:.2f}")

# Adjust fusion weights based on performance
adjuster = WeightAdjuster(
    config=AdjusterConfig(
        learning_rate=0.1,
        min_weight=0.02,
        max_weight=0.40,
        sharpe_target=1.5,
    ),
    tracker=tracker,
)
current_weights = {"ema_cloud": 0.25, "social": 0.15, "factor": 0.20}
update = adjuster.compute_weights(current_weights)
print(f"New weights: {update.new_weights}")
# Apply to fusion config:
# fusion_config.source_weights = update.new_weights
```

## Key classes and methods

### EMA Signal Engine (`src/ema_signals/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `EMACloudCalculator` | `compute_clouds(df)`, `get_cloud_states(df)`, `cloud_thickness(df, name)` | Compute 5-layer EMA clouds (incl. 72/89) |
| `SignalDetector` | `detect(df, ticker, timeframe)` | Detect 12 signal types (incl. candlestick patterns) |
| `ConvictionScorer` | `score(signal, volume_data, factor_scores)` | Score conviction 0-100 from 7 factors (incl. slope) |
| `MTFEngine` | `analyze(ticker, data_by_tf)` | Multi-timeframe confluence |
| `UniverseScanner` | `scan(tickers, data)` | Batch scan across ticker universe |

### Signal Fusion (`src/signal_fusion/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `SignalFusion` | `fuse(signals)`, `fuse_batch(by_symbol)` | Weighted fusion with time decay |
| `TradeRecommender` | `recommend(fused)`, `recommend_portfolio(fused_batch)`, `rank_opportunities(recs)` | Action classification, sizing |
| `FusionAgent` | `run_cycle()`, `start()`, `stop()` | Autonomous fusion loop |

### Multi-Strategy (`src/strategies/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `BotStrategy` (Protocol) | `analyze(ticker, O, H, L, C, V)`, `name` property | Strategy interface |
| `StrategyRegistry` | `register()`, `analyze_all()`, `enable()`, `disable()`, `list_strategies()` | Dynamic strategy management |
| `VWAPStrategy` | `analyze()`, `_compute_vwap()`, `_compute_rsi()` | VWAP mean-reversion |
| `ORBStrategy` | `analyze()` | Opening range breakout |
| `RSIDivergenceStrategy` | `analyze()` | RSI divergence detection |
| `PullbackToCloudStrategy` | `analyze()` | Ripster pullback-to-cloud entry |
| `TrendDayStrategy` | `analyze()` | ORB + cloud + volume trend day |
| `SessionScalpStrategy` | `analyze()` | Session-aware intraday routing |

### Feedback Loop (`src/signal_feedback/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `PerformanceTracker` | `record_outcome()`, `get_performance()`, `get_ranked_sources()` | Rolling metrics per source |
| `WeightAdjuster` | `compute_weights()`, `get_recommended_weights()` | Sharpe-proportional allocation |

## Common patterns

### The 10 EMA Signal Types

| Signal Type | Direction | Trigger |
|---|---|---|
| `CLOUD_CROSS_BULLISH` | long | Price crosses above cloud |
| `CLOUD_CROSS_BEARISH` | short | Price crosses below cloud |
| `CLOUD_FLIP_BULLISH` | long | Fast EMA crosses above slow EMA |
| `CLOUD_FLIP_BEARISH` | short | Fast EMA crosses below slow EMA |
| `CLOUD_BOUNCE_LONG` | long | Price tests cloud from above, bounces up |
| `CLOUD_BOUNCE_SHORT` | short | Price tests cloud from below, bounces down |
| `TREND_ALIGNED_LONG` | long | All 4 clouds bullish, price above all |
| `TREND_ALIGNED_SHORT` | short | All 4 clouds bearish, price below all |
| `MOMENTUM_EXHAUSTION` | reversal | 3+ candles outside fast cloud |
| `MTF_CONFLUENCE` | context | Multiple timeframes agree on direction |
| `CANDLESTICK_BULLISH` | long | Hammer/engulfing/pin bar at cloud boundary |
| `CANDLESTICK_BEARISH` | short | Bearish engulfing/pin bar at cloud boundary |

### Default Signal Source Weights

```python
DEFAULT_SOURCE_WEIGHTS = {
    SignalSource.EMA_CLOUD:    0.25,
    SignalSource.FACTOR:       0.20,
    SignalSource.SOCIAL:       0.15,
    SignalSource.ML_RANKING:   0.15,
    SignalSource.SENTIMENT:    0.10,
    SignalSource.TECHNICAL:    0.10,
    SignalSource.FUNDAMENTAL:  0.05,
}
```

### Conviction Scoring Weights (7 factors, total = 100)

| Factor | Weight | Source |
|---|---|---|
| Cloud alignment | 25 | Number of 5 clouds agreeing with direction |
| MTF confluence | 25 | Number of timeframes confirming |
| Volume | 15 | Current vs. average volume ratio |
| Factor score | 15 | Axion composite factor score |
| Candle quality | 10 | Full-body vs. wicks/dojis |
| Cloud slope | 5 | Aligned rising/falling slopes on clouds 3-5 |
| Cloud thickness | 5 | Wider cloud = stronger support |

### Recommendation Action Thresholds

| Composite Score | Action |
|---|---|
| >= +50 | STRONG_BUY |
| >= +20 | BUY |
| -20 to +20 | HOLD |
| <= -20 | SELL |
| <= -50 | STRONG_SELL |

### Minimum Data Requirements

- `EMACloudCalculator` needs 89+ bars (long_term_long period)
- `SignalDetector.detect()` needs `max_period + 2` bars minimum
- Cloud bounce detection needs at least 4 bars
- Momentum exhaustion needs `EXHAUSTION_CANDLES + 1` (4) bars
- `VWAPStrategy` needs `rsi_period + 1` (15) bars
- `ORBStrategy` needs `opening_range_bars + 2` (5) bars

## See Also
- **backtesting-strategies** — Validate signals historically with BacktestEngine and BotBacktestRunner
- **risk-assessment** — Pre-trade risk checks (VaR, correlation guard) before signal execution
- **order-execution** — Signal-to-order pipeline that consumes generated signals
- **sentiment-analysis** — Sentiment scores as an additional signal source for fusion
