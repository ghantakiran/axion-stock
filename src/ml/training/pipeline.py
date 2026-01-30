"""ML Training Pipeline.

Orchestrates the full training workflow:
1. Feature engineering
2. Walk-forward validation
3. Model training
4. Hyperparameter optimization
5. Model evaluation and storage
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import MLConfig
from src.ml.features import FeatureEngineer
from src.ml.models.base import BaseModel, ModelMetadata
from src.ml.models.ranking import StockRankingModel
from src.ml.models.regime import RegimeClassifier
from src.ml.models.earnings import EarningsPredictionModel
from src.ml.models.factor_timing import FactorTimingModel
from src.ml.training.walk_forward import WalkForwardValidator

logger = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    """Result of a training run."""

    model_name: str = ""
    version: str = ""
    trained_at: str = ""
    metrics: dict = field(default_factory=dict)
    walk_forward_metrics: dict = field(default_factory=dict)
    model_path: str = ""
    status: str = "completed"  # completed, failed
    error: str = ""


class TrainingPipeline:
    """Orchestrates ML model training.

    Manages the full lifecycle of training, validating, and
    storing ML models.

    Example:
        pipeline = TrainingPipeline()

        # Train ranking model
        result = pipeline.train_ranking_model(
            raw_data=stock_data,
            returns_data=returns,
        )

        # Train all models
        results = pipeline.train_all(
            raw_data=stock_data,
            returns_data=returns,
            market_data=market_data,
        )
    """

    def __init__(self, config: Optional[MLConfig] = None):
        self.config = config or MLConfig()
        self.feature_engineer = FeatureEngineer(config=self.config.features)
        self.walk_forward = WalkForwardValidator(config=self.config.walk_forward)

        # Current models
        self.ranking_model: Optional[StockRankingModel] = None
        self.regime_model: Optional[RegimeClassifier] = None
        self.earnings_model: Optional[EarningsPredictionModel] = None
        self.factor_timing_model: Optional[FactorTimingModel] = None

    def train_ranking_model(
        self,
        raw_data: pd.DataFrame,
        returns_data: pd.DataFrame,
        macro_data: Optional[pd.DataFrame] = None,
        run_walk_forward: bool = True,
    ) -> TrainingResult:
        """Train the stock ranking model.

        Args:
            raw_data: Raw stock data (multi-index date/symbol).
            returns_data: Daily returns DataFrame.
            macro_data: Macro indicators.
            run_walk_forward: Whether to run walk-forward validation.

        Returns:
            TrainingResult with metrics and model path.
        """
        result = TrainingResult(model_name="stock_ranking")
        result.version = datetime.now().strftime("%Y%m%d_%H%M")
        result.trained_at = datetime.now().isoformat()

        try:
            # Feature engineering
            logger.info("Creating features for ranking model...")
            features = self.feature_engineer.create_features(
                raw_data=raw_data,
                macro_data=macro_data,
            )

            if features.empty:
                result.status = "failed"
                result.error = "Feature engineering produced empty result"
                return result

            # Create targets
            dates = raw_data.index.get_level_values(0).unique() if isinstance(raw_data.index, pd.MultiIndex) else raw_data.index.unique()
            latest_date = dates.max()

            target = self.feature_engineer.create_target(
                returns_data=returns_data,
                target_date=latest_date.date() if hasattr(latest_date, 'date') else latest_date,
                forward_days=self.config.ranking.forward_days,
            )

            if target.empty:
                result.status = "failed"
                result.error = "Target creation produced empty result"
                return result

            # Align features and targets
            common = features.index.intersection(target.index)
            X = features.loc[common]
            y = target.loc[common]

            if len(X) < 100:
                result.status = "failed"
                result.error = f"Insufficient samples: {len(X)}"
                return result

            # Split into train/val
            split_idx = int(len(X) * 0.8)
            X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

            # Train model
            model = StockRankingModel(config=self.config.ranking)
            metrics = model.train(X_train, y_train, X_val=X_val, y_val=y_val)

            result.metrics = metrics
            self.ranking_model = model

            # Walk-forward validation
            if run_walk_forward and len(X) > 500:
                logger.info("Running walk-forward validation...")
                wf_results = self.walk_forward.run_walk_forward(model, X, y)
                result.walk_forward_metrics = self.walk_forward.aggregate_results(wf_results)

            # Save model
            model_path = os.path.join(
                self.config.model_dir, "ranking", result.version
            )
            model.save(model_path)
            result.model_path = model_path

            logger.info(f"Ranking model trained: {metrics}")

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.error(f"Ranking model training failed: {e}")

        return result

    def train_regime_model(
        self,
        market_data: pd.DataFrame,
        regime_labels: pd.Series,
    ) -> TrainingResult:
        """Train the regime classification model.

        Args:
            market_data: Market indicators DataFrame.
            regime_labels: Regime labels (bull/bear/sideways/crisis).

        Returns:
            TrainingResult.
        """
        result = TrainingResult(model_name="regime_classifier")
        result.version = datetime.now().strftime("%Y%m%d_%H%M")
        result.trained_at = datetime.now().isoformat()

        try:
            # Create regime features
            features = self.feature_engineer.create_regime_features(market_data)

            if features.empty:
                # Fallback: use market_data columns directly
                features = market_data.select_dtypes(include=[np.number]).dropna()

            if len(features) < 100:
                result.status = "failed"
                result.error = f"Insufficient data: {len(features)}"
                return result

            # Align with labels
            common = features.index.intersection(regime_labels.index)
            X = features.loc[common]
            y = regime_labels.loc[common]

            # Train
            model = RegimeClassifier(config=self.config.regime)
            metrics = model.train(X, y)

            result.metrics = metrics
            self.regime_model = model

            # Save
            model_path = os.path.join(
                self.config.model_dir, "regime", result.version
            )
            model.save(model_path)
            result.model_path = model_path

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.error(f"Regime model training failed: {e}")

        return result

    def train_earnings_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> TrainingResult:
        """Train the earnings prediction model.

        Args:
            X: Earnings-related features.
            y: Binary beat/miss labels.

        Returns:
            TrainingResult.
        """
        result = TrainingResult(model_name="earnings_prediction")
        result.version = datetime.now().strftime("%Y%m%d_%H%M")
        result.trained_at = datetime.now().isoformat()

        try:
            # Split
            split_idx = int(len(X) * 0.8)
            X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

            model = EarningsPredictionModel(config=self.config.earnings)
            metrics = model.train(X_train, y_train, X_val=X_val, y_val=y_val)

            result.metrics = metrics
            self.earnings_model = model

            # Save
            model_path = os.path.join(
                self.config.model_dir, "earnings", result.version
            )
            model.save(model_path)
            result.model_path = model_path

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.error(f"Earnings model training failed: {e}")

        return result

    def train_factor_timing_model(
        self,
        X: pd.DataFrame,
        factor_returns: pd.DataFrame,
    ) -> TrainingResult:
        """Train the factor timing model.

        Args:
            X: Macro/market features.
            factor_returns: Forward factor long-short returns.

        Returns:
            TrainingResult.
        """
        result = TrainingResult(model_name="factor_timing")
        result.version = datetime.now().strftime("%Y%m%d_%H%M")
        result.trained_at = datetime.now().isoformat()

        try:
            model = FactorTimingModel(config=self.config.factor_timing)
            metrics = model.train(X, factor_returns)

            result.metrics = metrics
            self.factor_timing_model = model

            # Save
            model_path = os.path.join(
                self.config.model_dir, "factor_timing", result.version
            )
            model.save(model_path)
            result.model_path = model_path

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.error(f"Factor timing model training failed: {e}")

        return result

    def train_all(
        self,
        raw_data: pd.DataFrame,
        returns_data: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
        regime_labels: Optional[pd.Series] = None,
        earnings_features: Optional[pd.DataFrame] = None,
        earnings_labels: Optional[pd.Series] = None,
        factor_returns: Optional[pd.DataFrame] = None,
    ) -> list[TrainingResult]:
        """Train all models.

        Args:
            raw_data: Raw stock data.
            returns_data: Daily returns.
            market_data: Market indicators.
            regime_labels: Regime labels.
            earnings_features: Earnings features.
            earnings_labels: Earnings beat/miss labels.
            factor_returns: Factor long-short returns.

        Returns:
            List of TrainingResult for each model.
        """
        results = []

        # 1. Ranking model
        logger.info("Training ranking model...")
        ranking_result = self.train_ranking_model(raw_data, returns_data)
        results.append(ranking_result)

        # 2. Regime model
        if market_data is not None and regime_labels is not None:
            logger.info("Training regime model...")
            regime_result = self.train_regime_model(market_data, regime_labels)
            results.append(regime_result)

        # 3. Earnings model
        if earnings_features is not None and earnings_labels is not None:
            logger.info("Training earnings model...")
            earnings_result = self.train_earnings_model(earnings_features, earnings_labels)
            results.append(earnings_result)

        # 4. Factor timing model
        if market_data is not None and factor_returns is not None:
            logger.info("Training factor timing model...")
            timing_result = self.train_factor_timing_model(market_data, factor_returns)
            results.append(timing_result)

        return results

    def load_models(self, model_dir: Optional[str] = None) -> dict[str, bool]:
        """Load latest models from disk.

        Args:
            model_dir: Directory containing model subdirectories.

        Returns:
            Dict of {model_name: loaded_successfully}.
        """
        model_dir = model_dir or self.config.model_dir
        status = {}

        for name, model_class, attr_name in [
            ("ranking", StockRankingModel, "ranking_model"),
            ("regime", RegimeClassifier, "regime_model"),
            ("earnings", EarningsPredictionModel, "earnings_model"),
            ("factor_timing", FactorTimingModel, "factor_timing_model"),
        ]:
            model_path = os.path.join(model_dir, name)
            if os.path.exists(model_path):
                # Find latest version
                versions = sorted(os.listdir(model_path))
                versions = [v for v in versions if not v.startswith(".")]
                if versions:
                    latest = os.path.join(model_path, versions[-1])
                    try:
                        model = model_class()
                        model.load(latest)
                        setattr(self, attr_name, model)
                        status[name] = True
                        logger.info(f"Loaded {name} model from {latest}")
                    except Exception as e:
                        status[name] = False
                        logger.error(f"Failed to load {name}: {e}")
                else:
                    status[name] = False
            else:
                status[name] = False

        return status
