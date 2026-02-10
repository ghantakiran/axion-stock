---
name: market-regime-detection
description: Detect market regimes (bull/bear/sideways/crisis) using HMM, clustering, rule-based, and ensemble methods. Classify regimes from price, VIX, and breadth data. Compute regime-aware portfolio allocations, dynamic trading thresholds, and adaptive strategy profiles. Use when building regime-conditional logic for trading, risk management, or allocation.
metadata:
  author: axion-platform
  version: "1.0"
---

# Market Regime Detection

## When to use this skill

Use this skill when you need to:
- Classify the current market environment as bull, bear, sideways, or crisis
- Combine multiple detection methods (HMM, clustering, rule-based) into an ensemble consensus
- Adjust portfolio allocations based on detected regime and confidence
- Set regime-adaptive entry/exit thresholds, stop-losses, and position sizing
- Adapt trading bot parameters (risk limits, signal filters) to the current regime
- Track regime transitions and persistence over time

## Step-by-step instructions

### 1. Rule-based regime detection

The simplest approach uses `RegimeDetector` from `src/regime/detector.py`. It classifies regimes from S&P 500 trend (200-SMA), VIX level, breadth ratio, momentum, and correlation spikes.

```python
import pandas as pd
from src.regime.detector import RegimeDetector, MarketRegime

detector = RegimeDetector()

# market_prices: DataFrame with at least 200 rows, "SPY" column
result = detector.classify(
    market_prices=market_prices,
    vix_data=vix_series,            # Optional pd.Series of VIX levels
    universe_prices=universe_df,    # Optional DataFrame for breadth calc
    as_of_date=None,                # Defaults to latest date in data
)

print(result.regime)       # MarketRegime.BULL / BEAR / SIDEWAYS / CRISIS
print(result.confidence)   # 0.0 - 1.0
print(result.features)     # RegimeFeatures dataclass
print(detector.get_regime_summary(result))
```

Classification priority: Crisis (VIX > 35 or correlation spike + drawdown), then Bull (>= 3 bull signals), then Bear (>= 3 bear signals), else Sideways.

### 2. HMM-based regime detection

`GaussianHMM` in `src/regime/hmm.py` fits a 4-state Hidden Markov Model on return/volatility features using EM. States are labeled by ascending mean return: crisis, bear, sideways, bull.

```python
from src.regime.hmm import GaussianHMM
from src.regime.config import HMMConfig

hmm = GaussianHMM(config=HMMConfig(
    n_regimes=4,
    n_iterations=100,
    convergence_tol=1e-4,
    min_observations=60,
    random_seed=42,
))

# Detect current regime from returns list
state = hmm.detect(
    returns=daily_returns_list,
    volatilities=daily_vol_list,  # Optional
)
print(state.regime)        # "bull", "bear", "sideways", "crisis"
print(state.confidence)    # 0.0 - 1.0
print(state.probabilities) # {"bull": 0.6, "bear": 0.1, ...}
print(state.duration)      # Days in current regime

# Full history with segments
history = hmm.detect_history(returns=daily_returns_list)
for seg in history.segments:
    print(f"{seg.regime}: idx {seg.start_idx}-{seg.end_idx}, "
          f"avg_ret={seg.avg_return}, vol={seg.volatility}")
```

### 3. Clustering-based regime detection

`ClusterRegimeClassifier` in `src/regime/clustering.py` uses K-Means or agglomerative clustering on rolling window features (mean return, volatility).

```python
from src.regime.clustering import ClusterRegimeClassifier
from src.regime.config import ClusterConfig, ClusterMethod

classifier = ClusterRegimeClassifier(config=ClusterConfig(
    method=ClusterMethod.KMEANS,   # or AGGLOMERATIVE
    n_clusters=4,
    window_size=21,
    min_observations=60,
))

state = classifier.classify(returns=daily_returns_list)
print(state.regime, state.confidence)

# Quality check
score = classifier.silhouette_score(returns=daily_returns_list)
print(f"Silhouette score: {score}")  # [-1, 1], higher = better separation
```

### 4. Ensemble consensus

`RegimeEnsemble` in `src/regime/ensemble.py` combines results from all three methods via weighted voting.

```python
from src.regime.ensemble import RegimeEnsemble, MethodResult

ensemble = RegimeEnsemble(
    method_weights={"hmm": 0.40, "clustering": 0.30, "rule_based": 0.30},
    min_methods=2,
)

# From individual RegimeState objects
result = ensemble.combine_from_states({
    "hmm": hmm_state,
    "clustering": cluster_state,
    "rule_based": rule_state,
})
print(result.consensus_regime)       # "bull"
print(result.consensus_confidence)   # 0.75
print(result.agreement_ratio)        # 1.0 if all agree
print(result.is_unanimous)           # True/False

# Compare divergence
comparison = ensemble.compare_methods(method_results)
print(comparison.divergent_methods)  # ["clustering"] if it disagrees
print(comparison.confidence_spread)  # Max - min confidence across methods

# Convert to RegimeState for downstream use
state = ensemble.weighted_regime_state(method_results)
```

### 5. Regime-aware allocation

`RegimeAllocator` in `src/regime/allocation.py` provides per-regime target weights and probability-blended allocations.

```python
from src.regime.allocation import RegimeAllocator
from src.regime.config import AllocationConfig

allocator = RegimeAllocator(config=AllocationConfig(
    blend_with_probabilities=True,
    max_single_asset_weight=0.40,
    min_single_asset_weight=0.0,
    transition_smoothing=0.3,
))

alloc = allocator.allocate(
    regime="bull",
    confidence=0.8,
    regime_probabilities={"bull": 0.7, "sideways": 0.2, "bear": 0.1},
)
print(alloc.weights)          # {"equity": 0.70, "bonds": 0.15, ...}
print(alloc.blended_weights)  # Probability-weighted blend
print(alloc.expected_return)  # 0.15 for bull
print(alloc.expected_risk)    # 0.12 for bull

# Recommend allocation shifts
shifts = allocator.recommend_shift(
    current_weights={"equity": 0.60, "bonds": 0.25, "cash": 0.15},
    new_regime="bear",
)
# {"equity": -0.30, "bonds": 0.15, "cash": 0.05}
```

Default regime targets:
| Regime   | Equity | Bonds | Commodities | Cash |
|----------|--------|-------|-------------|------|
| Bull     | 70%    | 15%   | 10%         | 5%   |
| Bear     | 30%    | 40%   | 10%         | 20%  |
| Sideways | 50%    | 30%   | 10%         | 10%  |
| Crisis   | 15%    | 30%   | 5%          | 50%  |

### 6. Dynamic trading thresholds

`DynamicThresholdManager` in `src/regime/threshold_manager.py` adjusts entry/exit thresholds, stops, and position sizing per regime.

```python
from src.regime.threshold_manager import DynamicThresholdManager

mgr = DynamicThresholdManager(base_position_size=1.0)

# Get thresholds for current regime
ts = mgr.get_thresholds("crisis")
print(ts.entry_threshold)      # 0.8 (high bar to enter in crisis)
print(ts.stop_loss_pct)        # 0.02 (tight stops)
print(ts.position_size_scalar) # 0.3 (small positions)

# Evaluate a signal against regime thresholds
decision = mgr.evaluate_signal(
    signal_name="EMA_CROSS",
    signal_score=0.7,
    signal_confidence=0.85,
    regime="bear",
    current_position=False,
)
print(decision.action)        # "enter", "exit", or "hold"
print(decision.position_size) # Scaled position size
print(decision.stop_loss)     # Stop-loss percentage

# Blend thresholds using regime probabilities
blended = mgr.interpolate_thresholds(
    {"bull": 0.3, "sideways": 0.5, "bear": 0.2}
)
print(blended.entry_threshold)  # Weighted average across regimes
```

### 7. Regime-adaptive strategy profiles

`RegimeAdapter` in `src/regime_adaptive/adapter.py` mutates bot executor config based on regime. `ProfileRegistry` holds 4 built-in profiles.

```python
from src.regime_adaptive.adapter import RegimeAdapter, AdapterConfig
from src.regime_adaptive.profiles import ProfileRegistry, StrategyProfile

# Get profiles
registry = ProfileRegistry()
profile = registry.get_profile("bull")
print(profile.max_risk_per_trade)       # 0.06
print(profile.preferred_signal_types)   # ["CLOUD_CROSS_BULLISH", ...]
print(profile.position_size_multiplier) # 1.2

# Adapt executor config
adapter = RegimeAdapter(
    config=AdapterConfig(smooth_transitions=True, transition_speed=0.5),
    registry=registry,
)

adaptation = adapter.adapt(
    executor_config={"max_risk_per_trade": 0.05, "max_concurrent_positions": 10},
    regime="crisis",
    confidence=0.85,
)
print(adaptation.adapted_config)  # Parameters tightened for crisis
print(adaptation.changes)         # List of {"field", "old_value", "new_value", "reason"}

# Filter signals by regime
filtered = adapter.filter_signals(
    signals=[{"signal_type": "CLOUD_CROSS_BULLISH", "score": 0.8}],
    regime="bear",
    confidence=0.9,
)
# CLOUD_CROSS_BULLISH is in bear's avoid list -> filtered out
```

## Key classes and methods

| Class | File | Key Methods |
|-------|------|-------------|
| `RegimeDetector` | `src/regime/detector.py` | `classify()`, `get_regime_summary()` |
| `GaussianHMM` | `src/regime/hmm.py` | `fit()`, `predict()`, `predict_proba()`, `detect()`, `detect_history()` |
| `ClusterRegimeClassifier` | `src/regime/clustering.py` | `fit()`, `classify()`, `classify_history()`, `silhouette_score()` |
| `RegimeEnsemble` | `src/regime/ensemble.py` | `combine()`, `combine_from_states()`, `compare_methods()`, `weighted_regime_state()` |
| `RegimeAllocator` | `src/regime/allocation.py` | `allocate()`, `recommend_shift()`, `regime_signal()` |
| `DynamicThresholdManager` | `src/regime/threshold_manager.py` | `get_thresholds()`, `evaluate_signal()`, `interpolate_thresholds()`, `compare_thresholds()` |
| `RegimeAdapter` | `src/regime_adaptive/adapter.py` | `adapt()`, `filter_signals()`, `reset()` |
| `ProfileRegistry` | `src/regime_adaptive/profiles.py` | `get_profile()`, `get_blended_profile()`, `register_custom()`, `get_all_profiles()` |

## Common patterns

### Full pipeline: detect, allocate, adapt

```python
# 1. Detect with ensemble
hmm_state = hmm.detect(returns)
cluster_state = classifier.classify(returns)
rule_state = ...  # from RegimeDetector

ensemble_result = ensemble.combine_from_states({
    "hmm": hmm_state, "clustering": cluster_state, "rule_based": rule_state,
})

regime = ensemble_result.consensus_regime
confidence = ensemble_result.consensus_confidence
probs = ensemble_result.consensus_probabilities

# 2. Allocate
allocation = allocator.allocate(regime, confidence, probs)

# 3. Set thresholds
thresholds = threshold_mgr.interpolate_thresholds(probs)

# 4. Adapt bot config
adaptation = adapter.adapt(executor_config, regime, confidence)
```

### Regime data models

- `RegimeState`: regime (str), confidence (float), probabilities (dict), duration (int), method (str)
- `RegimeSegment`: regime, start_idx, end_idx, avg_return, volatility
- `RegimeHistory`: regimes (list), probabilities (list), segments (list)
- `RegimeAllocation`: weights, blended_weights, expected_return, expected_risk
- `ThresholdSet`: entry_threshold, exit_threshold, stop_loss_pct, take_profit_pct, min_confidence, position_size_scalar
- `StrategyProfile`: risk limits, execution params, preferred/avoid signal types, sizing multiplier

### Confidence-based blending

When confidence is below 0.7, `ProfileRegistry.get_blended_profile()` interpolates between the detected-regime profile and the neutral sideways baseline. Numeric fields use weighted average; boolean fields use the more conservative value. This prevents abrupt parameter jumps on low-confidence detections.
