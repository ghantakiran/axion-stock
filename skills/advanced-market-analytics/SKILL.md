---
name: advanced-market-analytics
description: >
  Advanced market analytics across six Axion platform modules: insider trading (transaction tracking,
  cluster detection, signal generation), correlation (matrix computation, regime detection,
  diversification scoring), microstructure (spread analysis, tick metrics, price impact), order flow
  (imbalance, block detection, buy/sell pressure), dark pool (volume tracking, block detection,
  liquidity estimation), and pairs trading (cointegration, spread z-scores, pair selection).
metadata:
  author: Axion Platform Team
  version: 1.0.0
---

# Advanced Market Analytics Skill

## When to use this skill

Use this skill when you need to:

- Track insider transactions, detect cluster buying patterns, and generate insider signals
- Compute cross-asset correlation matrices with Pearson, Spearman, or Kendall methods
- Detect correlation regime shifts (low, normal, high, crisis)
- Score portfolio diversification quality using diversification ratio and effective number of bets
- Analyze bid-ask spreads (quoted, effective, realized) with adverse selection decomposition
- Compute tick-level metrics including VWAP, TWAP, and Kyle's lambda
- Measure order book imbalance and buy/sell pressure with cumulative delta
- Detect institutional block trades in dark pool data
- Track dark pool volume share and short volume ratios
- Test cointegration between asset pairs with Engle-Granger methodology
- Compute spread z-scores, half-life of mean reversion, and Hurst exponents
- Screen and rank pairs for statistical arbitrage trading

## Step-by-step instructions

### 1. Insider Trading Analysis

The `src/insider/` module tracks insider transactions, detects cluster buying,
generates signals, and manages alerts.

```python
from src.insider import (
    TransactionTracker, InsiderTransaction, InsiderType, TransactionType,
    ClusterDetector, InsiderCluster,
    SignalGenerator, InsiderSignal, SignalStrength,
    AlertManager, InsiderAlert,
    generate_sample_transactions,
)
from datetime import date, timedelta

# Track insider transactions
tracker = TransactionTracker()
tracker.add_transaction(InsiderTransaction(
    symbol="AAPL",
    company_name="Apple Inc.",
    insider_name="Tim Cook",
    insider_title="CEO",
    insider_type=InsiderType.CEO,
    transaction_type=TransactionType.BUY,
    transaction_date=date.today() - timedelta(days=5),
    shares=50000,
    price=185.0,
    value=9_250_000,
))

# Query transactions
buys = tracker.get_recent_buys(days=30, min_value=100_000)
ceo_buys = tracker.get_ceo_transactions(days=90, buys_only=True)
large = tracker.get_large_transactions(min_value=500_000, days=30)
symbol_txns = tracker.get_by_symbol("AAPL", days=90)
insider_txns = tracker.get_by_insider("Tim Cook", days=365)

# Summaries
summary = tracker.get_summary("AAPL", days=90)
# InsiderSummary with buy_count, sell_count, net_value, unique_insiders, ...
market = tracker.get_market_summary(days=30)
top_bought = tracker.get_top_bought(days=30, limit=10)
top_sold = tracker.get_top_sold(days=30, limit=10)

# Detect cluster buying (multiple insiders buying same stock)
detector = ClusterDetector(tracker)
clusters = detector.detect_clusters(days=90, min_insiders=2, min_value=100_000)
# InsiderCluster with insider_count, total_value, cluster_score, signal_strength

strongest = detector.get_strongest_clusters(limit=10)
aapl_cluster = detector.get_cluster_for_symbol("AAPL")

# Generate trading signals from insider activity
generator = SignalGenerator(tracker, detector)
signals = generator.generate_signals(days=30)
# InsiderSignal with signal_type (cluster_buy, large_buy, ceo_buy),
# signal_strength, insiders_involved, total_value

strong_signals = generator.get_signals(min_strength=SignalStrength.STRONG)

# Alert management
alert_mgr = AlertManager(generator)
alert_mgr.add_alert(InsiderAlert(
    name="Large CEO Buys",
    min_value=500_000,
    insider_types=[InsiderType.CEO],
))
notifications = alert_mgr.check_alerts(signals)
```

### 2. Correlation Analysis

The `src/correlation/` module computes correlation matrices, rolling correlations,
regime detection, and portfolio diversification scoring.

```python
from src.correlation import (
    CorrelationEngine, CorrelationMatrix, CorrelationPair,
    CorrelationMethod, RollingCorrelation,
    CorrelationRegimeDetector, CorrelationRegime, RegimeType,
    DiversificationAnalyzer, DiversificationScore, DiversificationLevel,
)
import pandas as pd
import numpy as np

# Build returns DataFrame
returns = pd.DataFrame({
    "AAPL": np.random.randn(252) * 0.02,
    "MSFT": np.random.randn(252) * 0.018,
    "GOOGL": np.random.randn(252) * 0.022,
    "JPM": np.random.randn(252) * 0.025,
})

# Compute correlation matrix
engine = CorrelationEngine()
matrix = engine.compute_matrix(returns, method=CorrelationMethod.PEARSON)
# CorrelationMatrix with symbols, values (NxN numpy array),
# avg_correlation, max_correlation, n_assets

# Get most and least correlated pairs
top_pairs = engine.get_top_pairs(matrix, n=5)
# List of CorrelationPair with symbol_a, symbol_b, correlation
bottom_pairs = engine.get_top_pairs(matrix, n=5, ascending=True)
highly_corr = engine.get_highly_correlated(matrix, threshold=0.70)

# Rolling correlation between two assets
rolling = engine.compute_rolling(returns, "AAPL", "MSFT", window=60)
# RollingCorrelation with dates, values, window

# Eigenvalue analysis for PCA / factor structure
eigenvalues = engine.compute_eigenvalues(matrix)

# Correlation regime detection
regime_detector = CorrelationRegimeDetector()
regime = regime_detector.detect(matrix)
# CorrelationRegime with regime (LOW/NORMAL/HIGH/CRISIS),
# avg_correlation, dispersion, regime_changed, days_in_regime

# Check for significant regime shifts
has_shift = regime_detector.has_significant_shift(current_matrix, prev_matrix)

# Portfolio diversification scoring
div_analyzer = DiversificationAnalyzer()
score = div_analyzer.score(
    matrix,
    weights={"AAPL": 0.30, "MSFT": 0.25, "GOOGL": 0.25, "JPM": 0.20},
    volatilities={"AAPL": 0.25, "MSFT": 0.22, "GOOGL": 0.28, "JPM": 0.30},
)
# DiversificationScore with diversification_ratio, effective_n_bets,
# avg_pair_correlation, max_pair, level (EXCELLENT/GOOD/FAIR/POOR),
# highly_correlated_pairs

# Compare portfolios
comparison = div_analyzer.compare_portfolios({
    "Growth": growth_score,
    "Value": value_score,
})
```

### 3. Market Microstructure Analysis

The `src/microstructure/` module analyzes bid-ask spreads, order book dynamics,
tick-level trade metrics, and price impact.

```python
from src.microstructure import (
    SpreadAnalyzer, SpreadMetrics, Trade,
    OrderBookAnalyzer, TickAnalyzer, TickMetrics,
    ImpactEstimator, ImpactEstimate,
)
import numpy as np

trades = [Trade(price=185.10, size=100, timestamp=1000.0, side=1),
          Trade(price=185.05, size=200, timestamp=1001.0, side=-1)]
bids = np.array([185.00, 184.98])
asks = np.array([185.15, 185.10])

# Spread analysis with Lee-Ready trade classification
metrics = SpreadAnalyzer().analyze(trades, bids, asks, symbol="AAPL")
# SpreadMetrics: quoted_spread_bps, effective_spread_bps,
# realized_spread_bps, adverse_selection_bps, roll_spread

# Tick-level: VWAP, TWAP, Kyle's lambda, size distribution
tick_metrics = TickAnalyzer().analyze(trades, (bids+asks)/2, symbol="AAPL")
# TickMetrics: vwap, twap, tick_to_trade_ratio, kyle_lambda

# Price impact estimation
impact = ImpactEstimator().estimate(
    order_size=10000, adv=1_000_000, volatility=0.25,
    spread_bps=5.0, symbol="AAPL",
)
```

### 4. Order Flow Analysis

The `src/orderflow/` module measures order book imbalance, detects block trades,
and computes buy/sell pressure with cumulative delta.

```python
from src.orderflow import (
    ImbalanceAnalyzer, OrderBookSnapshot, ImbalanceType, FlowSignal,
    BlockDetector, PressureAnalyzer, FlowPressure, PressureDirection,
)
import pandas as pd

# Order book imbalance
imbalance = ImbalanceAnalyzer()
snapshot = imbalance.compute_imbalance(bid_volume=50000, ask_volume=30000, symbol="AAPL")
# OrderBookSnapshot with imbalance_ratio, imbalance_type, signal

# Rolling imbalance over a series
rolling = imbalance.rolling_imbalance(bid_series, ask_series, symbol="AAPL")

# Buy/sell pressure with cumulative delta
pressure = PressureAnalyzer()
flow = pressure.compute_pressure(buy_volume=100000, sell_volume=60000, symbol="AAPL")
# FlowPressure with net_flow, pressure_ratio, direction, cumulative_delta

# Pressure over a time series
flows = pressure.compute_series(buy_volumes, sell_volumes, symbol="AAPL")
cumulative = pressure.get_cumulative_delta()
smoothed = pressure.smoothed_ratio(buy_volumes, sell_volumes)
```

### 5. Dark Pool Analytics

The `src/darkpool/` module tracks dark pool volume, analyzes prints,
detects institutional blocks, and estimates hidden liquidity.

```python
from src.darkpool import (
    VolumeTracker, DarkPoolVolume, VolumeSummary,
    PrintAnalyzer, DarkPrint,
    BlockDetector as DarkBlockDetector, DarkBlock, BlockDirection,
    LiquidityEstimator, DarkLiquidity,
)

# Track dark pool vs lit volume
tracker = VolumeTracker()
tracker.add_records([
    DarkPoolVolume(symbol="AAPL", dark_volume=2_000_000,
                   lit_volume=8_000_000, total_volume=10_000_000,
                   short_volume=500_000),
])
summary = tracker.summarize("AAPL")
# VolumeSummary with avg_dark_share, dark_share_trend, avg_short_ratio, is_elevated

# Block detection from dark prints (direction inferred from NBBO)
detector = DarkBlockDetector()
blocks = detector.detect(prints, adv=1_000_000, symbol="AAPL")
# DarkBlock with size, notional, direction (BUY/SELL/UNKNOWN), adv_ratio, cluster_id
block_summary = detector.summarize_blocks(blocks)
```

### 6. Pairs Trading

The `src/pairs/` module implements statistical pairs trading with cointegration testing,
spread analysis, and pair selection.

```python
from src.pairs import (
    CointegrationTester, CointegrationResult, PairStatus,
    SpreadAnalyzer as PairsSpreadAnalyzer, SpreadAnalysis, PairSignal, PairSignalType,
    PairSelector, PairScore,
)
import pandas as pd
import numpy as np

# Test cointegration between two assets
tester = CointegrationTester()
prices_a = pd.Series(np.cumsum(np.random.randn(252)) + 100)
prices_b = pd.Series(np.cumsum(np.random.randn(252)) + 100)

result = tester.test_pair(prices_a, prices_b, asset_a="AAPL", asset_b="MSFT")
# CointegrationResult with test_statistic, pvalue, hedge_ratio, intercept,
# correlation, status (COINTEGRATED/WEAK/NOT_COINTEGRATED)

# Test all pairs in a universe
prices = pd.DataFrame({"AAPL": prices_a, "MSFT": prices_b, "GOOGL": prices_c})
all_results = tester.test_universe(prices)

# Spread analysis with z-score, half-life, and Hurst exponent
spread_analyzer = PairsSpreadAnalyzer()
analysis = spread_analyzer.analyze(
    prices_a, prices_b,
    hedge_ratio=result.hedge_ratio,
    intercept=result.intercept,
    asset_a="AAPL",
    asset_b="MSFT",
)
# SpreadAnalysis with current_spread, spread_mean, spread_std,
# zscore, half_life, hurst_exponent, signal

# Compute raw spread series and rolling z-score
spread_series = spread_analyzer.compute_spread(prices_a, prices_b, result.hedge_ratio)
zscore_series = spread_analyzer.compute_zscore_series(spread_series)

# Half-life and Hurst independently
half_life = spread_analyzer.compute_half_life(spread_series.values)
hurst = spread_analyzer.compute_hurst(spread_series.values)

# Generate trading signals
signal = spread_analyzer.generate_signal(
    zscore=-2.1,
    hedge_ratio=result.hedge_ratio,
    asset_a="AAPL",
    asset_b="MSFT",
)
# PairSignal with signal (LONG_SPREAD/SHORT_SPREAD/EXIT/NO_SIGNAL),
# zscore, confidence

# Screen and rank entire universe for tradable pairs
selector = PairSelector()
ranked_pairs = selector.screen_universe(prices)
# List of PairScore sorted by total_score, each with
# cointegration_score, half_life_score, correlation_score, hurst_score, rank

# Score individual pair
pair_score = selector.score_pair(coint_result, spread_analysis)
```

## Key classes and methods

### Insider Module (`src/insider/`)

| Class | Method | Description |
|---|---|---|
| `TransactionTracker` | `add_transaction(txn)` | Record insider transaction |
| `TransactionTracker` | `get_by_symbol(symbol, days)` | Transactions per symbol |
| `TransactionTracker` | `get_recent_buys(days, min_value)` | Recent buy transactions |
| `TransactionTracker` | `get_ceo_transactions(days, buys_only)` | CEO transaction filter |
| `TransactionTracker` | `get_large_transactions(min_value, days)` | Large value filter |
| `TransactionTracker` | `get_summary(symbol, days)` | InsiderSummary for symbol |
| `TransactionTracker` | `get_market_summary(days)` | Market-wide insider stats |
| `TransactionTracker` | `get_top_bought(days, limit)` | Top bought by value |
| `ClusterDetector` | `detect_clusters(days, min_insiders, min_value)` | Detect cluster buys |
| `ClusterDetector` | `get_strongest_clusters(limit)` | Top clusters by score |
| `SignalGenerator` | `generate_signals(days)` | Generate all insider signals |
| `SignalGenerator` | `get_signals(signal_type, min_strength)` | Filter signals |
| `AlertManager` | `add_alert(alert)` | Register alert rule |
| `AlertManager` | `check_alerts(signals)` | Check signals against alerts |

### Correlation Module (`src/correlation/`)

| Class | Method | Description |
|---|---|---|
| `CorrelationEngine` | `compute_matrix(returns, method)` | NxN correlation matrix |
| `CorrelationEngine` | `get_top_pairs(matrix, n, ascending)` | Most/least correlated pairs |
| `CorrelationEngine` | `get_highly_correlated(matrix, threshold)` | Pairs above threshold |
| `CorrelationEngine` | `compute_rolling(returns, symbol_a, symbol_b, window)` | Rolling correlation |
| `CorrelationEngine` | `compute_eigenvalues(matrix)` | Eigenvalue decomposition |
| `CorrelationRegimeDetector` | `detect(matrix)` | Classify correlation regime |
| `CorrelationRegimeDetector` | `has_significant_shift(current, previous)` | Detect regime change |
| `DiversificationAnalyzer` | `score(matrix, weights, volatilities)` | Diversification score |
| `DiversificationAnalyzer` | `compare_portfolios(scores)` | Multi-portfolio comparison |

### Microstructure Module (`src/microstructure/`)

| Class | Method | Description |
|---|---|---|
| `SpreadAnalyzer` | `analyze(trades, bids, asks, symbol)` | Full spread decomposition |
| `SpreadAnalyzer` | `roll_estimator(prices)` | Roll's implied spread |
| `TickAnalyzer` | `analyze(trades, midpoints, symbol)` | Tick metrics (VWAP, lambda) |
| `OrderBookAnalyzer` | `analyze(levels, symbol)` | Order book depth metrics |
| `ImpactEstimator` | `estimate(order_size, adv, volatility, ...)` | Price impact estimate |

### Order Flow Module (`src/orderflow/`)

| Class | Method | Description |
|---|---|---|
| `ImbalanceAnalyzer` | `compute_imbalance(bid_vol, ask_vol, symbol)` | Single-period imbalance |
| `ImbalanceAnalyzer` | `rolling_imbalance(bid_series, ask_series)` | Rolling imbalance series |
| `BlockDetector` | `detect(trades, adv)` | Detect block trades |
| `PressureAnalyzer` | `compute_pressure(buy_vol, sell_vol)` | Single-period pressure |
| `PressureAnalyzer` | `compute_series(buy_vols, sell_vols)` | Pressure time series |
| `PressureAnalyzer` | `smoothed_ratio(buy_vols, sell_vols)` | Smoothed ratio series |
| `PressureAnalyzer` | `get_cumulative_delta()` | Running cumulative delta |

### Dark Pool Module (`src/darkpool/`)

| Class | Method | Description |
|---|---|---|
| `VolumeTracker` | `add_records(records)` | Add dark pool volume records |
| `VolumeTracker` | `summarize(symbol)` | VolumeSummary with dark share |
| `PrintAnalyzer` | `analyze(prints, symbol)` | Analyze dark prints |
| `BlockDetector` | `detect(prints, adv, symbol)` | Detect dark blocks |
| `BlockDetector` | `summarize_blocks(blocks)` | Block statistics summary |
| `LiquidityEstimator` | `estimate(dark_vol, lit_vol, symbol)` | Hidden liquidity |

### Pairs Trading Module (`src/pairs/`)

| Class | Method | Description |
|---|---|---|
| `CointegrationTester` | `test_pair(prices_a, prices_b, ...)` | Engle-Granger test |
| `CointegrationTester` | `test_universe(prices)` | Test all pairs in DataFrame |
| `SpreadAnalyzer` | `analyze(prices_a, prices_b, hedge_ratio, ...)` | Full spread analysis |
| `SpreadAnalyzer` | `compute_spread(prices_a, prices_b, hedge_ratio)` | Raw spread series |
| `SpreadAnalyzer` | `compute_zscore_series(spread)` | Rolling z-score series |
| `SpreadAnalyzer` | `compute_half_life(spread)` | Ornstein-Uhlenbeck half-life |
| `SpreadAnalyzer` | `compute_hurst(spread)` | Hurst exponent (R/S method) |
| `SpreadAnalyzer` | `generate_signal(zscore, hedge_ratio, ...)` | Trading signal from z-score |
| `PairSelector` | `screen_universe(prices)` | Screen and rank all pairs |
| `PairSelector` | `score_pair(coint, spread)` | Score individual pair |

## Common patterns

### Enums and configuration

Each module uses Python enums for classification and dataclass configs with defaults:

```python
# Enums for type-safe classification
from src.insider.config import InsiderType, TransactionType, SignalStrength
from src.correlation.config import CorrelationMethod, RegimeType, DiversificationLevel
from src.microstructure.config import TradeClassification, SpreadType, ImpactModel
from src.orderflow.config import FlowSignal, ImbalanceType, PressureDirection
from src.darkpool.config import PrintType, BlockDirection, LiquidityLevel
from src.pairs.config import PairSignalType, SpreadMethod, HedgeMethod, PairStatus

# All analyzers accept optional config, falling back to module defaults
from src.correlation.config import CorrelationConfig
engine = CorrelationEngine(config=CorrelationConfig(method=CorrelationMethod.SPEARMAN))
engine = CorrelationEngine()  # uses DEFAULT_CORRELATION_CONFIG
```

### Cross-module workflow: insider signals filtered by correlation

```python
from src.insider import TransactionTracker, ClusterDetector
from src.correlation import CorrelationEngine
import pandas as pd

tracker = TransactionTracker()
# ... add transactions ...
clusters = ClusterDetector(tracker).detect_clusters(days=30)
symbols = [c.symbol for c in clusters]

# Filter out highly correlated cluster signals to avoid overlap
returns = pd.DataFrame(...)  # returns for cluster symbols
matrix = CorrelationEngine().compute_matrix(returns)
high_corr = {(p.symbol_a, p.symbol_b)
             for p in CorrelationEngine().get_highly_correlated(matrix, threshold=0.80)}
```

### Cross-module workflow: pairs pipeline with correlation pre-filter

```python
from src.pairs import PairSelector, PairSignalType, SpreadAnalyzer
from src.correlation import CorrelationEngine

engine = CorrelationEngine()
matrix = engine.compute_matrix(returns)
candidates = engine.get_highly_correlated(matrix, threshold=0.60)

selector = PairSelector()
ranked = selector.screen_universe(prices)
# Each PairScore has cointegration_score, half_life_score, hurst_score, rank
```

### Cross-module workflow: microstructure + order flow combined view

```python
from src.microstructure import SpreadAnalyzer, TickAnalyzer, Trade
from src.orderflow import PressureAnalyzer

metrics = SpreadAnalyzer().analyze(trades, bids, asks, "AAPL")
tick_metrics = TickAnalyzer().analyze(trades, midpoints, "AAPL")
flow = PressureAnalyzer().compute_pressure(
    tick_metrics.buy_volume, tick_metrics.sell_volume, "AAPL")
# Combine: spread bps, Kyle's lambda, flow direction, cumulative delta
```
