---
name: ml-model-development
description: >
  Build and serve ML models for stock prediction on the Axion platform.
  Covers the factor engine (6 categories, regime-adaptive weights),
  the factors library (value, momentum, quality, growth, volatility,
  technical), and the full ML pipeline (feature engineering, LightGBM
  stock ranking, regime classification, earnings prediction, factor
  timing, walk-forward validation, hybrid scoring, monitoring, and
  SHAP explainability).
metadata:
  author: Axion Platform Team
  version: 1.0.0
---

# ML Model Development on the Axion Platform

## When to use this skill

Use this skill when you need to:

- Compute multi-factor scores (value, momentum, quality, growth, volatility, technical) across a stock universe.
- Detect market regimes (bull, bear, sideways, crisis) and adapt factor weights accordingly.
- Engineer ML-ready features with cross-sectional ranking, sector-relative normalization, and lag/rolling statistics.
- Train stock ranking models (LightGBM), regime classifiers (GMM + Random Forest), earnings predictors (XGBoost), or factor timing models.
- Run walk-forward validation, hyperparameter optimization, or full training pipelines.
- Serve predictions in production with caching, fallback, and hybrid rule/ML score blending.
- Monitor model health, detect feature drift (PSI), and explain predictions with SHAP.

## Step-by-step instructions

### 1. Factor computation with the Factor Engine

The `FactorEngineV2` computes 6 factor categories with regime-adaptive weighting.

```python
from src.factor_engine import FactorEngineV2
import pandas as pd

# Initialize engine
engine = FactorEngineV2(
    use_adaptive_weights=True,    # regime-based weight adaptation
    use_sector_relative=True,     # sector-relative scoring adjustment
    use_momentum_overlay=True,    # tilt toward recently-performing factors
)

# Prepare inputs
# prices: DataFrame[dates x tickers] of adjusted close prices
# fundamentals: DataFrame[tickers x fields] (pe_ratio, roe, revenue_growth, etc.)
# sp500_prices: Series of S&P 500 closing prices (for regime detection)

scores = engine.compute_all_scores(
    prices=prices_df,
    fundamentals=fundamentals_df,
    sp500_prices=sp500_series,
    as_of_date=date(2026, 2, 7),
)
# scores columns: value, momentum, quality, growth, volatility, technical, composite, regime

# Access the detected regime
regime = engine.last_regime       # MarketRegime enum (BULL, BEAR, SIDEWAYS, CRISIS)
weights = engine.last_weights     # dict like {"value": 0.20, "momentum": 0.25, ...}

# Detailed breakdown for a single ticker
breakdown = engine.get_factor_breakdown("AAPL", prices_df, fundamentals_df)
# breakdown["category_scores"], breakdown["sub_factors"], breakdown["regime"]

# v1-compatible output (4 factors only: value, momentum, quality, growth)
v1_scores = engine.compute_v1_compatible_scores(prices_df, fundamentals_df)
```

### 2. Individual factor categories

The `src/factors` package provides 6 calculator classes. Use `create_default_registry()` or individual calculators directly.

```python
from src.factors import FactorRegistry, ValueFactors
from src.factors.registry import create_default_registry

registry = create_default_registry()
all_factors = registry.list_factors()       # dict[category -> [factor_names]]
total = registry.total_factor_count()       # 40+ factors across 6 categories
value_scores = registry.compute_category("value", prices_df, fundamentals_df)
all_scores = registry.compute_all(prices_df, fundamentals_df)  # dict[str, DataFrame]
```

**Factor categories:** `ValueFactors` (earnings_yield, fcf_yield, book_to_market, ev_ebitda, dividend_yield, forward_pe), `MomentumFactors` (ret_12m_1m, ret_6m_1m, ret_3m, high_52w_proximity, earnings_momentum, revenue_momentum), `QualityFactors` (roe, roa, roic, gross_profit_assets, accruals, debt_equity, interest_coverage), `GrowthFactors` (revenue_growth, eps_growth, fcf_growth, growth_acceleration, rnd_intensity), `VolatilityFactors` (realized_vol, idiosyncratic_vol, beta, downside_beta, max_drawdown), `TechnicalFactors` (rsi, macd, volume_trend, price_vs_sma, bollinger_bands).

### 3. Feature engineering

The `FeatureEngineer` creates ML-ready features from raw stock data with strict look-ahead prevention.

```python
from src.ml import FeatureEngineer, FeatureConfig
from datetime import date

engineer = FeatureEngineer(config=FeatureConfig(
    max_features=100,
    collinearity_threshold=0.95,
    lag_periods=[5, 10, 21],
    rolling_windows=[5, 21, 63],
))

# Create cross-sectional features for ranking model
# raw_data: MultiIndex DataFrame (date, symbol) x factor columns
features = engineer.create_features(
    raw_data=stock_data_df,
    macro_data=macro_df,        # optional: macro indicators indexed by date
    target_date=date(2026, 1, 15),
)
# Features include: *_rank, *_sector_rank, *_x_* (interactions),
#                    *_lagNd, *_mean_Nd, *_std_Nd, month_of_year, quarter

# Create target: forward return quintile labels (1=worst, 5=best)
target = engineer.create_target(
    returns_data=daily_returns_df,  # columns are symbols
    target_date=date(2026, 1, 15),
    forward_days=21,                # 1-month forward
    num_quintiles=5,
)

# Get feature names from last call
feature_names = engineer.feature_names

# Create features for regime classification
regime_features = engineer.create_regime_features(
    market_data=market_data_df,  # columns: sp500_close, vix, yield_10y, etc.
    target_date=date(2026, 1, 15),
)
# Includes: sp500_return_20d/60d, sp500_volatility_20d, vix_level,
#           vix_term_structure, yield_curve_10y_2y, credit_spread_hy_ig,
#           advance_decline_10d, pct_above_200sma, put_call_ratio
```

### 4. Training models

#### Stock ranking model (LightGBM ensemble)

```python
from src.ml import StockRankingModel, RankingModelConfig

model = StockRankingModel(config=RankingModelConfig(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.05,
    n_ensemble=3,          # ensemble of 3 models with different seeds
    num_quintiles=5,
))

# Train with validation set for early stopping
metrics = model.train(X_train, y_train, X_val=X_val, y_val=y_val)
# metrics: accuracy, top_quintile_accuracy, bottom_quintile_accuracy,
#          information_coefficient, ic_pvalue

# Predict quintile probabilities and composite score
predictions = model.predict(X_test)
# DataFrame columns: prob_q1..prob_q5, predicted_quintile, score (0-1)

# Convenience: get continuous rank score only
rank_scores = model.predict_rank(X_test)  # Series, 0=worst to 1=best

# Feature importance (averaged across ensemble)
importance = model.get_feature_importance()  # Series sorted descending
```

#### Regime classifier (GMM + Random Forest)

```python
from src.ml import RegimeClassifier, RegimeModelConfig, RegimePrediction

model = RegimeClassifier(config=RegimeModelConfig(
    n_components=4,          # GMM components
    covariance_type="full",
    rf_n_estimators=200,
    rf_max_depth=8,
    regimes=["bull", "bear", "sideways", "crisis"],
))

# Train on market data with regime labels
metrics = model.train(X_market, regime_labels)
# metrics: accuracy, bull_accuracy, bear_accuracy, ...

# Predict regime for current market
regime = model.predict_regime(X_current)
# RegimePrediction: regime="bull", confidence=0.82,
#                   probabilities={"bull": 0.82, "bear": 0.05, ...},
#                   duration_days=45

# Batch predictions
batch = model.predict(X_all)
# DataFrame: prob_bull, prob_bear, ..., regime, confidence
```

#### Earnings prediction model

```python
from src.ml import EarningsPredictionModel, EarningsModelConfig

model = EarningsPredictionModel(config=EarningsModelConfig())
metrics = model.train(X_earnings, y_beat_miss)
prediction = model.predict_single("AAPL", earnings_features)
# EarningsPrediction: symbol, beat_probability, predicted_surprise, confidence
```

#### Factor timing model

```python
from src.ml import FactorTimingModel, FactorTimingConfig

model = FactorTimingModel(config=FactorTimingConfig(
    factors=["value", "momentum", "quality", "growth", "volatility", "technical"],
))
metrics = model.train(X_macro, factor_returns_df)
weights = model.get_factor_weights(X_current_macro)
# {"value": 0.22, "momentum": 0.18, "quality": 0.20, ...}
```

### 5. Training pipeline, walk-forward, and hyperopt

```python
from src.ml import TrainingPipeline, MLConfig, TrainingResult
from src.ml import WalkForwardValidator, WalkForwardConfig, HyperparameterOptimizer

pipeline = TrainingPipeline(config=MLConfig(model_dir="models/"))

# Train a single model with walk-forward
result = pipeline.train_ranking_model(
    raw_data=stock_data_df, returns_data=daily_returns_df,
    macro_data=macro_df, run_walk_forward=True,
)
# TrainingResult: model_name, version, metrics, walk_forward_metrics, model_path, status

# Train all models at once
results = pipeline.train_all(
    raw_data=stock_data_df, returns_data=daily_returns_df,
    market_data=market_data_df, regime_labels=regime_series,
    earnings_features=earnings_df, earnings_labels=beat_miss_series,
    factor_returns=factor_ls_returns_df,
)

# Load saved models
status = pipeline.load_models(model_dir="models/")

# Walk-forward validation standalone
validator = WalkForwardValidator(config=WalkForwardConfig(
    n_splits=5, train_size=252*3, test_size=63, gap=21,
))
wf_results = validator.run_walk_forward(model, X, y)
aggregated = validator.aggregate_results(wf_results)

# Hyperparameter optimization
optimizer = HyperparameterOptimizer()
best_params = optimizer.optimize(
    model_class=StockRankingModel, X=X_train, y=y_train,
    X_val=X_val, y_val=y_val, n_trials=50,
)
```

### 6. Serving, hybrid scoring, monitoring, and explainability

```python
from src.ml import MLPredictor, HybridScorer, HybridScoringConfig
from src.ml import ModelPerformanceTracker, DegradationDetector, ModelExplainer

# --- Production predictor ---
predictor = MLPredictor()
predictor.set_models(ranking=pipeline.ranking_model, regime=pipeline.regime_model)
rankings = predictor.predict_rankings(raw_data=current_data, target_date=date.today())
regime = predictor.predict_regime(market_data)       # RegimePrediction
weights = predictor.get_factor_timing_weights(market_data)  # dict
status = predictor.get_model_status()                # per-model health dict

# --- Hybrid scoring (rules + ML blend) ---
scorer = HybridScorer(config=HybridScoringConfig(
    ml_weight=0.30, min_ic_for_ml=0.03, fallback_to_rules=True,
))
hybrid = scorer.compute_hybrid_scores(rule_scores=composites, ml_scores=ml_scores)
scorer.update_ml_performance(ic=0.045)  # auto-deactivates if IC < threshold

# --- Monitoring ---
tracker = ModelPerformanceTracker()
tracker.record_prediction(prediction_date, predicted_scores, actual_returns)
health = tracker.get_health_status("stock_ranking")
# ModelHealthStatus: status, current_ic, rolling_ic_3m, ic_trend, needs_retraining

detector = DegradationDetector()
drift = detector.check_feature_drift(reference_data=X_train, current_data=X_current)
# DriftReport: overall_drift, psi_scores, drifted_features

# --- Explainability (SHAP) ---
explainer = ModelExplainer()
explanation = explainer.explain(model=ranking_model, X=X_single, symbol="AAPL")
print(explanation.to_text())
# Shows top_positive_factors, top_negative_factors, feature_contributions
```

## Key classes and methods

| Module | Class | Key Methods |
|--------|-------|-------------|
| `src.factor_engine` | `FactorEngineV2` | `compute_all_scores()`, `compute_v1_compatible_scores()`, `get_factor_breakdown()` |
| `src.factors` | `FactorRegistry` | `register()`, `compute_category()`, `compute_all()`, `list_factors()`, `get_default_weights()`, `total_factor_count()` |
| `src.factors` | `FactorCalculator` (ABC) | `compute()`, `percentile_rank()`, `winsorize()`, `zscore()`, `combine_subfactors()` |
| `src.factors` | `ValueFactors` / `MomentumFactors` / `QualityFactors` / `GrowthFactors` / `VolatilityFactors` / `TechnicalFactors` | `compute()` |
| `src.ml` | `FeatureEngineer` | `create_features()`, `create_target()`, `create_regime_features()` |
| `src.ml` | `StockRankingModel` | `train()`, `predict()`, `predict_rank()`, `get_feature_importance()` |
| `src.ml` | `RegimeClassifier` | `train()`, `predict()`, `predict_regime()`, `get_feature_importance()` |
| `src.ml` | `EarningsPredictionModel` | `train()`, `predict_single()` |
| `src.ml` | `FactorTimingModel` | `train()`, `get_factor_weights()` |
| `src.ml` | `TrainingPipeline` | `train_ranking_model()`, `train_regime_model()`, `train_earnings_model()`, `train_factor_timing_model()`, `train_all()`, `load_models()` |
| `src.ml` | `WalkForwardValidator` | `run_walk_forward()`, `aggregate_results()` |
| `src.ml` | `HyperparameterOptimizer` | `optimize()` |
| `src.ml` | `MLPredictor` | `set_models()`, `predict_rankings()`, `predict_regime()`, `predict_earnings()`, `get_factor_timing_weights()`, `get_model_status()` |
| `src.ml` | `HybridScorer` | `compute_hybrid_scores()`, `compute_hybrid_score_single()`, `update_ml_performance()` |
| `src.ml` | `ModelPerformanceTracker` | `record_prediction()`, `get_health_status()` |
| `src.ml` | `DegradationDetector` | `check_feature_drift()` |
| `src.ml` | `ModelExplainer` | `explain()` |

## Common patterns

### Data flow: factors to ML to scoring

The typical end-to-end pipeline connects all three modules:

```
prices/fundamentals
      |
      v
  FactorEngineV2 -----> composite scores (rule-based)
      |                          |
      v                          v
  FeatureEngineer         HybridScorer <---- ML ranking scores
      |                          |
      v                          v
  StockRankingModel       Final blended scores
```

### Percentile ranking convention

All factor scores and ML scores are normalized to the 0-1 range where:
- **0.0** = worst in the cross-section
- **0.5** = median
- **1.0** = best in the cross-section

The `FactorCalculator.percentile_rank()` method handles direction (ascending for positive factors like ROE, descending for negative factors like P/E).

### Config hierarchy

`MLConfig` is the top-level config containing sub-configs: `FeatureConfig`, `RankingModelConfig`, `RegimeModelConfig`, `EarningsModelConfig`, `FactorTimingConfig`, `WalkForwardConfig`, `MonitoringConfig`, `HybridScoringConfig`. All have sensible defaults; customize by passing sub-configs: `MLConfig(ranking=RankingModelConfig(n_estimators=1000))`.

### Model lifecycle

All ML models extend `BaseModel` with: `is_fitted` (bool), `metadata` (ModelMetadata with trained_at, metrics, feature_names), `save(path)`, `load(path)`.

### Regime-aware factor weighting

The `AdaptiveWeightManager` shifts factor weights by regime: bull emphasizes momentum/growth, bear favors quality/volatility, crisis maximizes quality. Weights are further adjusted by an optional momentum overlay.

### Look-ahead bias prevention

`FeatureEngineer.create_features()` strictly filters data by `target_date`. `WalkForwardValidator` enforces a `gap` period between training and test sets.

### LightGBM fallback

`StockRankingModel` prefers `lightgbm.LGBMClassifier`, falling back to `sklearn.GradientBoostingClassifier`. `RegimeClassifier` uses sklearn throughout. SHAP falls back to feature importance when the `shap` package is unavailable.

### Integration with factor engine

The ML pipeline builds on top of the factor engine output:

```python
# 1. Compute raw factor scores
engine = FactorEngineV2()
scores = engine.compute_all_scores(prices, fundamentals)

# 2. Use factor scores as ML features
features = engineer.create_features(raw_data=scores)

# 3. Train ranking model on those features
model = StockRankingModel()
model.train(features, target)

# 4. Blend rule-based composite with ML predictions
hybrid = scorer.compute_hybrid_scores(
    rule_scores=scores["composite"],
    ml_scores=model.predict_rank(features),
)
```
