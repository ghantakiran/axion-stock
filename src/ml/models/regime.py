"""Regime Classification Model.

Classifies market into Bull/Bear/Sideways/Crisis using an
ensemble of Hidden Markov Model and Random Forest.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import RegimeModelConfig

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except (ImportError, ValueError):
    SKLEARN_AVAILABLE = False
from src.ml.models.base import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class RegimePrediction:
    """Result of regime classification."""

    regime: str = "unknown"  # bull, bear, sideways, crisis
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    duration_days: int = 0  # Days in current regime


class RegimeClassifier(BaseModel):
    """Market regime classification model.

    Combines Gaussian Mixture Model (as HMM proxy) with
    Random Forest for regime classification.

    The GMM identifies latent market states from return/volatility
    patterns. The RF classifies using a broader feature set.

    Example:
        model = RegimeClassifier()
        model.train(X_train, y_train)
        regime = model.predict_regime(X_current)
    """

    def __init__(self, config: Optional[RegimeModelConfig] = None):
        super().__init__(model_name="regime_classifier")
        self.config = config or RegimeModelConfig()
        self.gmm = None
        self.rf_model = None
        self.scaler = StandardScaler()
        self._regime_map: dict[int, str] = {}
        self._current_regime: str = "unknown"
        self._regime_start_idx: int = 0

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        **kwargs,
    ) -> dict:
        """Train regime classification models.

        Args:
            X: Feature matrix with market indicators.
            y: Regime labels (bull, bear, sideways, crisis).

        Returns:
            Dict of training metrics.
        """
        # Scale features
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X),
            columns=X.columns,
            index=X.index,
        )

        # Train GMM for unsupervised regime detection
        self.gmm = GaussianMixture(
            n_components=self.config.n_components,
            covariance_type=self.config.covariance_type,
            n_init=3,
            max_iter=self.config.n_iter,
            random_state=42,
        )
        self.gmm.fit(X_scaled)

        # Map GMM clusters to regime labels
        gmm_labels = self.gmm.predict(X_scaled)
        self._map_clusters_to_regimes(gmm_labels, y)

        # Add GMM features for RF
        gmm_probs = self.gmm.predict_proba(X_scaled)
        X_enhanced = pd.concat([
            X_scaled.reset_index(drop=True),
            pd.DataFrame(gmm_probs, columns=[f"gmm_prob_{i}" for i in range(self.config.n_components)]),
        ], axis=1)

        # Train Random Forest
        self.rf_model = RandomForestClassifier(
            n_estimators=self.config.rf_n_estimators,
            max_depth=self.config.rf_max_depth,
            random_state=42,
            n_jobs=-1,
        )
        self.rf_model.fit(X_enhanced, y)

        self._is_fitted = True

        # Metrics
        rf_preds = self.rf_model.predict(X_enhanced)
        accuracy = (rf_preds == y).mean()

        # Per-regime accuracy
        regime_accuracy = {}
        for regime in self.config.regimes:
            mask = y == regime
            if mask.sum() > 0:
                regime_accuracy[f"{regime}_accuracy"] = float((rf_preds[mask] == regime).mean())

        metrics = {
            "accuracy": float(accuracy),
            **regime_accuracy,
            "n_regimes": len(y.unique()),
        }

        self._update_metadata(X, metrics)
        logger.info(f"Regime model trained: accuracy={accuracy:.3f}")

        return metrics

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predict regime for each row.

        Args:
            X: Feature matrix.

        Returns:
            DataFrame with regime, confidence, and probabilities.
        """
        if not self._is_fitted:
            raise ValueError("Model not trained.")

        X_scaled = pd.DataFrame(
            self.scaler.transform(X),
            columns=X.columns,
            index=X.index,
        )

        # GMM probabilities
        gmm_probs = self.gmm.predict_proba(X_scaled)
        X_enhanced = pd.concat([
            X_scaled.reset_index(drop=True),
            pd.DataFrame(gmm_probs, columns=[f"gmm_prob_{i}" for i in range(self.config.n_components)]),
        ], axis=1)

        # RF prediction
        rf_probs = self.rf_model.predict_proba(X_enhanced)
        rf_classes = self.rf_model.classes_

        result = pd.DataFrame(index=X.index)
        for i, cls in enumerate(rf_classes):
            result[f"prob_{cls}"] = rf_probs[:, i]

        result["regime"] = self.rf_model.predict(X_enhanced)
        result["confidence"] = rf_probs.max(axis=1)

        return result

    def predict_regime(self, X: pd.DataFrame) -> RegimePrediction:
        """Predict current market regime (single prediction).

        Args:
            X: Feature matrix (single row or latest row used).

        Returns:
            RegimePrediction with regime, confidence, and probabilities.
        """
        if X.empty:
            return RegimePrediction()

        predictions = self.predict(X)
        latest = predictions.iloc[-1]

        # Build probability dict
        probs = {}
        for regime in self.config.regimes:
            col = f"prob_{regime}"
            probs[regime] = float(latest[col]) if col in latest.index else 0.0

        predicted_regime = latest["regime"]
        confidence = float(latest["confidence"])

        # Track regime duration
        if predicted_regime != self._current_regime:
            self._current_regime = predicted_regime
            self._regime_start_idx = len(predictions) - 1

        duration = len(predictions) - self._regime_start_idx

        return RegimePrediction(
            regime=predicted_regime,
            confidence=confidence,
            probabilities=probs,
            duration_days=duration,
        )

    def get_feature_importance(self) -> pd.Series:
        """Get Random Forest feature importance."""
        if not self._is_fitted or self.rf_model is None:
            return pd.Series(dtype=float)

        feature_names = list(self.metadata.feature_names)
        # Add GMM probability features
        for i in range(self.config.n_components):
            feature_names.append(f"gmm_prob_{i}")

        importances = self.rf_model.feature_importances_
        return pd.Series(importances, index=feature_names[:len(importances)]).sort_values(ascending=False)

    def _map_clusters_to_regimes(
        self,
        gmm_labels: np.ndarray,
        true_labels: pd.Series,
    ) -> None:
        """Map GMM cluster indices to regime names."""
        self._regime_map = {}

        for cluster_id in range(self.config.n_components):
            mask = gmm_labels == cluster_id
            if mask.sum() > 0:
                most_common = true_labels[mask].mode()
                if len(most_common) > 0:
                    self._regime_map[cluster_id] = most_common.iloc[0]
                else:
                    self._regime_map[cluster_id] = "unknown"
