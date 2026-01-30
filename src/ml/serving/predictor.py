"""ML Model Predictor.

Production serving layer that provides predictions from
trained models with caching and fallback handling.
"""

import logging
from datetime import datetime, date
from typing import Optional

import pandas as pd

from src.ml.config import MLConfig
from src.ml.features import FeatureEngineer
from src.ml.models.ranking import StockRankingModel
from src.ml.models.regime import RegimeClassifier, RegimePrediction
from src.ml.models.earnings import EarningsPredictionModel, EarningsPrediction
from src.ml.models.factor_timing import FactorTimingModel

logger = logging.getLogger(__name__)


class MLPredictor:
    """Production ML prediction service.

    Provides a unified interface for getting predictions from
    all ML models with caching and graceful degradation.

    Example:
        predictor = MLPredictor()
        predictor.load_models()

        # Stock rankings
        rankings = predictor.predict_rankings(raw_data)

        # Current regime
        regime = predictor.predict_regime(market_data)

        # Factor weights
        weights = predictor.get_factor_timing_weights(market_data)
    """

    def __init__(self, config: Optional[MLConfig] = None):
        self.config = config or MLConfig()
        self.feature_engineer = FeatureEngineer(config=self.config.features)

        # Models
        self.ranking_model: Optional[StockRankingModel] = None
        self.regime_model: Optional[RegimeClassifier] = None
        self.earnings_model: Optional[EarningsPredictionModel] = None
        self.factor_timing_model: Optional[FactorTimingModel] = None

        # Cache
        self._prediction_cache: dict = {}
        self._cache_date: Optional[date] = None

    def set_models(
        self,
        ranking: Optional[StockRankingModel] = None,
        regime: Optional[RegimeClassifier] = None,
        earnings: Optional[EarningsPredictionModel] = None,
        factor_timing: Optional[FactorTimingModel] = None,
    ) -> None:
        """Set trained models for serving."""
        if ranking:
            self.ranking_model = ranking
        if regime:
            self.regime_model = regime
        if earnings:
            self.earnings_model = earnings
        if factor_timing:
            self.factor_timing_model = factor_timing

    def predict_rankings(
        self,
        raw_data: pd.DataFrame,
        macro_data: Optional[pd.DataFrame] = None,
        target_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Predict stock rankings.

        Args:
            raw_data: Current stock data.
            macro_data: Macro indicators.
            target_date: Prediction date.

        Returns:
            DataFrame with score, predicted_quintile, probabilities.
        """
        if self.ranking_model is None or not self.ranking_model.is_fitted:
            logger.warning("Ranking model not available")
            return pd.DataFrame()

        features = self.feature_engineer.create_features(
            raw_data=raw_data,
            macro_data=macro_data,
            target_date=target_date,
        )

        if features.empty:
            return pd.DataFrame()

        # Ensure features match training features
        trained_features = self.ranking_model.metadata.feature_names
        if trained_features:
            missing = set(trained_features) - set(features.columns)
            for col in missing:
                features[col] = 0.5  # Neutral value
            features = features[trained_features]

        return self.ranking_model.predict(features)

    def predict_regime(
        self,
        market_data: pd.DataFrame,
        target_date: Optional[date] = None,
    ) -> RegimePrediction:
        """Predict current market regime.

        Args:
            market_data: Market indicator DataFrame.
            target_date: Prediction date.

        Returns:
            RegimePrediction with regime and confidence.
        """
        if self.regime_model is None or not self.regime_model.is_fitted:
            logger.warning("Regime model not available")
            return RegimePrediction()

        features = self.feature_engineer.create_regime_features(
            market_data=market_data,
            target_date=target_date,
        )

        if features.empty:
            return RegimePrediction()

        # Align features
        trained_features = self.regime_model.metadata.feature_names
        if trained_features:
            for col in trained_features:
                if col not in features.columns:
                    features[col] = 0
            features = features[[c for c in trained_features if c in features.columns]]

        return self.regime_model.predict_regime(features)

    def predict_earnings(
        self,
        symbol: str,
        features: pd.Series,
    ) -> EarningsPrediction:
        """Predict earnings surprise for a stock.

        Args:
            symbol: Stock symbol.
            features: Earnings-related features.

        Returns:
            EarningsPrediction with beat probability.
        """
        if self.earnings_model is None or not self.earnings_model.is_fitted:
            return EarningsPrediction(symbol=symbol)

        return self.earnings_model.predict_single(symbol, features)

    def get_factor_timing_weights(
        self,
        market_data: pd.DataFrame,
    ) -> dict[str, float]:
        """Get recommended factor weights from timing model.

        Args:
            market_data: Market indicators.

        Returns:
            Dict of factor weights.
        """
        if self.factor_timing_model is None or not self.factor_timing_model.is_fitted:
            # Equal weight fallback
            factors = self.config.factor_timing.factors
            return {f: 1.0 / len(factors) for f in factors}

        features = market_data.select_dtypes(include=["number"]).iloc[[-1]]
        return self.factor_timing_model.get_factor_weights(features)

    def get_model_status(self) -> dict:
        """Get status of all models."""
        status = {}

        for name, model in [
            ("ranking", self.ranking_model),
            ("regime", self.regime_model),
            ("earnings", self.earnings_model),
            ("factor_timing", self.factor_timing_model),
        ]:
            if model is not None and model.is_fitted:
                status[name] = {
                    "status": "active",
                    "trained_at": model.metadata.trained_at,
                    "metrics": model.metadata.metrics,
                    "n_features": model.metadata.n_features,
                }
            else:
                status[name] = {"status": "unavailable"}

        return status
