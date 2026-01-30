"""Machine Learning Prediction Engine.

A comprehensive ML system for stock prediction including:
- Cross-sectional stock ranking (LightGBM)
- Market regime classification (GMM + Random Forest)
- Earnings surprise prediction (XGBoost/GBM)
- Factor timing (multi-output LightGBM)
- Walk-forward validation pipeline
- Hyperparameter optimization
- Score blending (rules + ML hybrid)
- Model monitoring and degradation detection
- SHAP-based explainability
"""

# Configuration
from src.ml.config import (
    MLConfig,
    DEFAULT_ML_CONFIG,
    FeatureConfig,
    RankingModelConfig,
    RegimeModelConfig,
    EarningsModelConfig,
    FactorTimingConfig,
    WalkForwardConfig,
    MonitoringConfig,
    HybridScoringConfig,
)

# Feature Engineering
from src.ml.features import FeatureEngineer

# Models
from src.ml.models.base import BaseModel, ModelMetadata
from src.ml.models.ranking import StockRankingModel
from src.ml.models.regime import RegimeClassifier, RegimePrediction
from src.ml.models.earnings import EarningsPredictionModel, EarningsPrediction
from src.ml.models.factor_timing import FactorTimingModel

# Training
from src.ml.training.walk_forward import WalkForwardValidator, Split
from src.ml.training.hyperopt import HyperparameterOptimizer
from src.ml.training.pipeline import TrainingPipeline, TrainingResult

# Serving
from src.ml.serving.predictor import MLPredictor
from src.ml.serving.hybrid_scorer import HybridScorer

# Monitoring
from src.ml.monitoring.tracker import ModelPerformanceTracker, ModelHealthStatus
from src.ml.monitoring.degradation import DegradationDetector, DriftReport

# Explainability
from src.ml.explainability.explainer import ModelExplainer, Explanation

__all__ = [
    # Config
    "MLConfig",
    "DEFAULT_ML_CONFIG",
    "FeatureConfig",
    "RankingModelConfig",
    "RegimeModelConfig",
    "EarningsModelConfig",
    "FactorTimingConfig",
    "WalkForwardConfig",
    "MonitoringConfig",
    "HybridScoringConfig",
    # Features
    "FeatureEngineer",
    # Models
    "BaseModel",
    "ModelMetadata",
    "StockRankingModel",
    "RegimeClassifier",
    "RegimePrediction",
    "EarningsPredictionModel",
    "EarningsPrediction",
    "FactorTimingModel",
    # Training
    "WalkForwardValidator",
    "Split",
    "HyperparameterOptimizer",
    "TrainingPipeline",
    "TrainingResult",
    # Serving
    "MLPredictor",
    "HybridScorer",
    # Monitoring
    "ModelPerformanceTracker",
    "ModelHealthStatus",
    "DegradationDetector",
    "DriftReport",
    # Explainability
    "ModelExplainer",
    "Explanation",
]
