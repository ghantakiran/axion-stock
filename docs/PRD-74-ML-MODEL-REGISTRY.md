# PRD-74: ML Model Registry & Versioning

## Overview
Machine learning model registry with versioning, training pipeline, walk-forward validation, hyperparameter optimization, model monitoring, degradation detection, feature drift tracking, and model explainability.

## Components

### 1. Model Base (`src/ml/models/base.py`)
- **BaseModel** — Abstract base class with train(), predict(), get_feature_importance(), save(), load()
- **ModelMetadata** — model_name, model_version, trained_at, train periods, n_samples, features, hyperparameters, metrics, status

### 2. Model Implementations (`src/ml/models/`)
- **StockRankingModel** (`ranking.py`) — Ensemble stock ranking with quintile prediction
- **RegimeClassifier** (`regime.py`) — Market regime classification (bull, bear, sideways, crisis)
- **EarningsPredictionModel** (`earnings.py`) — Earnings beat probability prediction
- **FactorTimingModel** (`factor_timing.py`) — Dynamic factor weight optimization

### 3. Training Pipeline (`src/ml/training/`)
- **TrainingPipeline** (`pipeline.py`) — End-to-end training with TrainingResult
- **WalkForwardValidator** (`walk_forward.py`) — Walk-forward cross-validation with expanding/rolling windows, no future leakage
- **HyperparameterOptimizer** (`hyperopt.py`) — Hyperparameter search and optimization

### 4. Feature Engineering (`src/ml/features/`)
- **FeatureEngineer** — Feature creation, ranking, interaction features, feature name tracking

### 5. Model Serving (`src/ml/serving/`)
- **MLPredictor** (`predictor.py`) — Real-time model inference
- **HybridScorer** (`hybrid_scorer.py`) — Hybrid ML + rules-based scoring with fallback, deactivation/reactivation

### 6. Model Monitoring (`src/ml/monitoring/`)
- **ModelPerformanceTracker** (`tracker.py`) — Rolling IC, prediction vs actuals recording, health status assessment
- **ModelHealthStatus** — status (healthy, warning, degraded, stale), IC, rolling IC, trend, retraining flag
- **DegradationDetector** (`degradation.py`) — Feature drift detection (PSI scores), IC trend analysis

### 7. Model Explainability (`src/ml/explainability/`)
- **ModelExplainer** (`explainer.py`) — Feature importance explanations with natural language summaries

## Database Tables
- `ml_models` — Model registry with name, version, type, status, hyperparameters, metrics, model_path (migration 007)
  - Unique constraint on (model_name, model_version)
  - Status: trained, production, deprecated
  - Types: ranking, regime, earnings, factor_timing
- `ml_predictions` — Prediction history with symbol, scores, quintiles, actuals, explanations (migration 007)
- `ml_training_runs` — Training log with run_id, status, duration, samples, metrics, walk-forward results (migration 007)
- `ml_feature_drift` — Drift detection results with PSI scores, drifted features, severity (migration 007)
- `ml_performance_metrics` — Rolling performance with IC, quintile returns, long-short spread, model status (migration 007)

## Dashboard
Streamlit dashboard (`app/pages/ml_models.py`) with:
- Model status and health overview
- Stock ranking predictions
- Regime classification display
- Feature importance visualization
- Model performance monitoring

## Test Coverage
32 tests in `tests/test_ml.py` covering ML config, feature engineering (creation/ranking/interactions), model training and prediction (ranking/regime/earnings/factor timing), walk-forward validation (splits/leakage/expanding), hybrid scoring (ML+rules/fallback/deactivation), performance tracking (IC/health), degradation detection (drift/IC trend), model explainability, and end-to-end workflow.
