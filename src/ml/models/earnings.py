"""Earnings Surprise Prediction Model.

XGBoost classifier that predicts probability of earnings
beat/miss for individual stocks.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import EarningsModelConfig

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score, accuracy_score
    SKLEARN_AVAILABLE = True
except (ImportError, ValueError):
    SKLEARN_AVAILABLE = False
from src.ml.models.base import BaseModel

# Try to import XGBoost, fall back to sklearn
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EarningsPrediction:
    """Earnings prediction result."""

    symbol: str = ""
    beat_probability: float = 0.5
    expected_surprise_pct: float = 0.0
    predicted_move_pct: float = 0.0
    confidence: str = "low"  # low, medium, high
    top_positive_factors: list[tuple[str, float]] = field(default_factory=list)
    top_negative_factors: list[tuple[str, float]] = field(default_factory=list)


class EarningsPredictionModel(BaseModel):
    """Earnings surprise prediction model.

    Predicts probability of earnings beat using historical patterns,
    estimate revisions, price momentum, and sector context.

    Example:
        model = EarningsPredictionModel()
        model.train(X_train, y_train)
        prediction = model.predict_single("AAPL", features)
    """

    def __init__(self, config: Optional[EarningsModelConfig] = None):
        super().__init__(model_name="earnings_prediction")
        self.config = config or EarningsModelConfig()

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        **kwargs,
    ) -> dict:
        """Train earnings prediction model.

        Args:
            X: Feature matrix with earnings-related features.
            y: Binary target (1=beat, 0=miss).
            X_val: Validation features.
            y_val: Validation labels.

        Returns:
            Dict of training metrics.
        """
        if XGBOOST_AVAILABLE:
            self.model = xgb.XGBClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                min_child_weight=self.config.min_child_weight,
                subsample=self.config.subsample,
                colsample_bytree=self.config.colsample_bytree,
                random_state=42,
                eval_metric="logloss",
                use_label_encoder=False,
            )
            eval_set = [(X_val, y_val)] if X_val is not None else None
            self.model.fit(
                X, y,
                eval_set=eval_set,
                verbose=False,
            )
        else:
            self.model = GradientBoostingClassifier(
                n_estimators=min(self.config.n_estimators, 200),
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                min_samples_leaf=self.config.min_child_weight,
                subsample=self.config.subsample,
                random_state=42,
            )
            self.model.fit(X, y)

        self._is_fitted = True

        # Metrics
        train_probs = self.model.predict_proba(X)[:, 1]
        train_preds = (train_probs >= 0.5).astype(int)

        metrics = {
            "accuracy": float(accuracy_score(y, train_preds)),
            "auc_roc": float(roc_auc_score(y, train_probs)) if len(y.unique()) > 1 else 0,
            "beat_accuracy": float((train_preds[y == 1] == 1).mean()) if (y == 1).sum() > 0 else 0,
            "miss_accuracy": float((train_preds[y == 0] == 0).mean()) if (y == 0).sum() > 0 else 0,
        }

        if X_val is not None and y_val is not None:
            val_probs = self.model.predict_proba(X_val)[:, 1]
            val_preds = (val_probs >= 0.5).astype(int)
            metrics["val_accuracy"] = float(accuracy_score(y_val, val_preds))
            if len(y_val.unique()) > 1:
                metrics["val_auc_roc"] = float(roc_auc_score(y_val, val_probs))

        self._update_metadata(X, metrics)
        logger.info(f"Earnings model trained: {metrics}")

        return metrics

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predict earnings beat probability.

        Args:
            X: Feature matrix.

        Returns:
            DataFrame with beat_probability and predicted_beat columns.
        """
        if not self._is_fitted:
            raise ValueError("Model not trained.")

        probs = self.model.predict_proba(X)

        result = pd.DataFrame(index=X.index)
        result["beat_probability"] = probs[:, 1]
        result["miss_probability"] = probs[:, 0]
        result["predicted_beat"] = (probs[:, 1] >= 0.5).astype(int)

        # Confidence level
        result["confidence"] = pd.cut(
            result["beat_probability"].apply(lambda p: abs(p - 0.5)),
            bins=[-0.01, 0.1, 0.2, 0.5],
            labels=["low", "medium", "high"],
        )

        return result

    def predict_single(
        self,
        symbol: str,
        features: pd.Series,
    ) -> EarningsPrediction:
        """Predict earnings for a single stock.

        Args:
            symbol: Stock symbol.
            features: Feature values for this stock.

        Returns:
            EarningsPrediction with detailed results.
        """
        X = pd.DataFrame([features])
        predictions = self.predict(X)
        row = predictions.iloc[0]

        # Get feature importance for this prediction
        importance = self.get_feature_importance()
        feature_contrib = features * importance.reindex(features.index, fill_value=0)

        top_pos = feature_contrib.nlargest(3)
        top_neg = feature_contrib.nsmallest(3)

        return EarningsPrediction(
            symbol=symbol,
            beat_probability=float(row["beat_probability"]),
            confidence=str(row["confidence"]),
            top_positive_factors=list(zip(top_pos.index, top_pos.values)),
            top_negative_factors=list(zip(top_neg.index, top_neg.values)),
        )

    def get_feature_importance(self) -> pd.Series:
        """Get feature importance."""
        if not self._is_fitted:
            return pd.Series(dtype=float)

        importances = self.model.feature_importances_
        feature_names = self.metadata.feature_names or [f"f{i}" for i in range(len(importances))]

        return pd.Series(importances, index=feature_names[:len(importances)]).sort_values(ascending=False)


def create_earnings_features(
    earnings_history: pd.DataFrame,
    price_data: pd.DataFrame,
    estimates: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Create earnings-specific features.

    Args:
        earnings_history: Historical earnings with actual vs estimate.
        price_data: Price history around earnings dates.
        estimates: Analyst estimate revisions.

    Returns:
        DataFrame with earnings features.
    """
    features = pd.DataFrame()

    if earnings_history.empty:
        return features

    # Historical beat/miss pattern
    if "surprise_pct" in earnings_history.columns:
        for q in range(1, 9):
            col = f"beat_lag_q{q}"
            if len(earnings_history) >= q:
                features[col] = [int(earnings_history["surprise_pct"].iloc[-q] > 0)]

        # Beat rate
        features["beat_rate_4q"] = [
            (earnings_history["surprise_pct"].tail(4) > 0).mean()
        ]
        features["beat_rate_8q"] = [
            (earnings_history["surprise_pct"].tail(8) > 0).mean()
        ]

        # Average surprise magnitude
        features["avg_surprise_4q"] = [
            earnings_history["surprise_pct"].tail(4).mean()
        ]

    # Estimate revision momentum
    if estimates is not None and not estimates.empty:
        if "eps_estimate" in estimates.columns:
            features["estimate_revision_30d"] = [
                estimates["eps_estimate"].pct_change(30).iloc[-1]
                if len(estimates) > 30 else 0
            ]
            features["estimate_dispersion"] = [
                estimates["eps_estimate"].std() / estimates["eps_estimate"].mean()
                if estimates["eps_estimate"].mean() != 0 else 0
            ]

    return features
