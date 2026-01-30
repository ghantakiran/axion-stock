"""Factor Timing Model.

Multi-output LightGBM model that predicts which factors will
outperform in the next month. Used for dynamic factor weight
adjustment.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import FactorTimingConfig

try:
    from sklearn.ensemble import GradientBoostingRegressor
    SKLEARN_AVAILABLE = True
except (ImportError, ValueError):
    SKLEARN_AVAILABLE = False
from src.ml.models.base import BaseModel

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

logger = logging.getLogger(__name__)


class FactorTimingModel(BaseModel):
    """Factor timing model for dynamic weight adjustment.

    Predicts next-month return of factor long-short portfolios
    to determine which factors will outperform.

    Example:
        model = FactorTimingModel()
        model.train(X_train, y_train_dict)
        timing_scores = model.predict(X_current)
    """

    def __init__(self, config: Optional[FactorTimingConfig] = None):
        super().__init__(model_name="factor_timing")
        self.config = config or FactorTimingConfig()
        self.factor_models: dict[str, object] = {}

    def train(
        self,
        X: pd.DataFrame,
        y: pd.DataFrame,
        **kwargs,
    ) -> dict:
        """Train factor timing models.

        Trains one model per factor to predict its next-month spread.

        Args:
            X: Feature matrix (macro/market features).
            y: DataFrame with columns for each factor's forward return.
               Column names should match config.factors.

        Returns:
            Dict of training metrics.
        """
        self.factor_models = {}
        all_metrics = {}

        for factor in self.config.factors:
            if factor not in y.columns:
                logger.warning(f"Factor '{factor}' not in target columns, skipping")
                continue

            factor_target = y[factor].dropna()
            X_aligned = X.loc[factor_target.index]

            if len(X_aligned) < 50:
                logger.warning(f"Insufficient data for factor '{factor}': {len(X_aligned)}")
                continue

            model = self._create_model()
            model.fit(X_aligned, factor_target)
            self.factor_models[factor] = model

            # Metrics
            preds = model.predict(X_aligned)
            from sklearn.metrics import mean_squared_error, r2_score
            mse = mean_squared_error(factor_target, preds)
            r2 = r2_score(factor_target, preds)

            # Directional accuracy
            direction_correct = ((preds > 0) == (factor_target > 0)).mean()

            all_metrics[f"{factor}_mse"] = float(mse)
            all_metrics[f"{factor}_r2"] = float(r2)
            all_metrics[f"{factor}_direction_accuracy"] = float(direction_correct)

        self._is_fitted = True

        self._update_metadata(X, all_metrics)
        logger.info(f"Factor timing models trained for: {list(self.factor_models.keys())}")

        return all_metrics

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predict factor returns for next period.

        Args:
            X: Feature matrix.

        Returns:
            DataFrame with predicted return for each factor.
        """
        if not self._is_fitted:
            raise ValueError("Model not trained.")

        result = pd.DataFrame(index=X.index)

        for factor, model in self.factor_models.items():
            result[f"{factor}_predicted"] = model.predict(X)

        # Determine recommended factor tilts
        if not result.empty:
            latest = result.iloc[-1]
            pred_cols = [c for c in result.columns if c.endswith("_predicted")]

            if pred_cols:
                # Rank predictions
                factor_ranks = latest[pred_cols].rank(ascending=False)
                for col in pred_cols:
                    factor = col.replace("_predicted", "")
                    result[f"{factor}_rank"] = factor_ranks[col]

        return result

    def get_factor_weights(self, X: pd.DataFrame) -> dict[str, float]:
        """Get recommended factor weight adjustments.

        Returns weights normalized to sum to 1, tilted toward
        factors predicted to outperform.

        Args:
            X: Feature matrix (single row for current prediction).

        Returns:
            Dict of factor weights.
        """
        if not self._is_fitted:
            # Equal weights fallback
            n = len(self.config.factors)
            return {f: 1.0 / n for f in self.config.factors}

        predictions = self.predict(X)
        if predictions.empty:
            n = len(self.config.factors)
            return {f: 1.0 / n for f in self.config.factors}

        latest = predictions.iloc[-1]

        # Convert predictions to weights using softmax
        pred_values = []
        factors = []
        for factor in self.config.factors:
            col = f"{factor}_predicted"
            if col in latest.index:
                pred_values.append(latest[col])
                factors.append(factor)

        if not pred_values:
            n = len(self.config.factors)
            return {f: 1.0 / n for f in self.config.factors}

        # Softmax with temperature to control conviction
        pred_array = np.array(pred_values)
        temperature = 1.0
        exp_preds = np.exp(pred_array / temperature)
        weights = exp_preds / exp_preds.sum()

        return dict(zip(factors, weights))

    def get_feature_importance(self) -> pd.Series:
        """Get average feature importance across factor models."""
        if not self._is_fitted:
            return pd.Series(dtype=float)

        all_importances = []
        for model in self.factor_models.values():
            all_importances.append(model.feature_importances_)

        if not all_importances:
            return pd.Series(dtype=float)

        avg = np.mean(all_importances, axis=0)
        feature_names = self.metadata.feature_names or [f"f{i}" for i in range(len(avg))]
        return pd.Series(avg, index=feature_names[:len(avg)]).sort_values(ascending=False)

    def _create_model(self):
        """Create a single factor model."""
        if LIGHTGBM_AVAILABLE:
            return lgb.LGBMRegressor(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                random_state=42,
                verbose=-1,
                n_jobs=-1,
            )
        else:
            return GradientBoostingRegressor(
                n_estimators=min(self.config.n_estimators, 200),
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                random_state=42,
            )
