"""Model Explainability using SHAP and feature importance.

Provides per-prediction explanations showing which features
drove the model's decision.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.models.base import BaseModel

# Try to import SHAP, fall back to feature importance
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class Explanation:
    """Explanation for a single prediction."""

    symbol: str = ""
    prediction: float = 0.0
    predicted_quintile: int = 0

    # Top contributing features
    top_positive_factors: list[tuple[str, float]] = field(default_factory=list)
    top_negative_factors: list[tuple[str, float]] = field(default_factory=list)

    # Full feature contributions
    feature_contributions: dict[str, float] = field(default_factory=dict)

    # Base value (expected prediction without any features)
    base_value: float = 0.0

    def to_text(self) -> str:
        """Format explanation as readable text."""
        lines = [
            f"Prediction for {self.symbol}: Quintile {self.predicted_quintile} (score: {self.prediction:.2f})",
            "",
            "Top positive factors:",
        ]

        for name, value in self.top_positive_factors[:5]:
            lines.append(f"  + {name}: {value:+.4f}")

        lines.append("\nTop negative factors:")
        for name, value in self.top_negative_factors[:5]:
            lines.append(f"  - {name}: {value:+.4f}")

        return "\n".join(lines)


class ModelExplainer:
    """Explain individual model predictions.

    Uses SHAP values when available, otherwise falls back to
    feature importance-weighted contributions.

    Example:
        explainer = ModelExplainer(model)
        explanation = explainer.explain(symbol="AAPL", features=features)
        print(explanation.to_text())
    """

    def __init__(self, model: BaseModel):
        self.model = model
        self._shap_explainer = None
        self._feature_importance: Optional[pd.Series] = None

    def explain(
        self,
        symbol: str,
        features: pd.Series,
        n_top: int = 5,
    ) -> Explanation:
        """Explain a prediction for a single stock.

        Args:
            symbol: Stock symbol.
            features: Feature values for this stock.
            n_top: Number of top factors to return.

        Returns:
            Explanation with feature contributions.
        """
        if not self.model.is_fitted:
            return Explanation(symbol=symbol)

        X = pd.DataFrame([features])

        # Get prediction
        predictions = self.model.predict(X)
        pred_score = float(predictions["score"].iloc[0]) if "score" in predictions.columns else 0
        pred_quintile = int(predictions["predicted_quintile"].iloc[0]) if "predicted_quintile" in predictions.columns else 0

        # Calculate contributions
        if SHAP_AVAILABLE:
            contributions = self._shap_explain(X)
        else:
            contributions = self._importance_explain(features)

        # Sort by contribution
        sorted_contribs = sorted(contributions.items(), key=lambda x: x[1])
        positive = [(k, v) for k, v in sorted_contribs if v > 0]
        negative = [(k, v) for k, v in sorted_contribs if v < 0]

        return Explanation(
            symbol=symbol,
            prediction=pred_score,
            predicted_quintile=pred_quintile,
            top_positive_factors=positive[-n_top:][::-1],
            top_negative_factors=negative[:n_top],
            feature_contributions=contributions,
        )

    def explain_batch(
        self,
        X: pd.DataFrame,
        n_top: int = 5,
    ) -> dict[str, Explanation]:
        """Explain predictions for multiple stocks.

        Args:
            X: Feature matrix indexed by symbol.
            n_top: Number of top factors per stock.

        Returns:
            Dict of {symbol: Explanation}.
        """
        results = {}
        for symbol in X.index:
            results[symbol] = self.explain(symbol, X.loc[symbol], n_top)
        return results

    def get_global_importance(self) -> pd.Series:
        """Get global feature importance.

        Returns:
            Series of feature importance scores.
        """
        return self.model.get_feature_importance()

    def _shap_explain(self, X: pd.DataFrame) -> dict[str, float]:
        """SHAP-based explanation."""
        try:
            if self._shap_explainer is None:
                # Create SHAP explainer
                if hasattr(self.model, "models") and self.model.models:
                    # For ensemble, use first model
                    self._shap_explainer = shap.TreeExplainer(self.model.models[0])
                elif self.model.model is not None:
                    self._shap_explainer = shap.TreeExplainer(self.model.model)
                else:
                    return self._importance_explain(X.iloc[0])

            shap_values = self._shap_explainer.shap_values(X)

            # For multi-class, use the highest quintile SHAP values
            if isinstance(shap_values, list):
                # Average across classes weighted by prediction
                shap_arr = np.mean(shap_values, axis=0)
            else:
                shap_arr = shap_values

            if shap_arr.ndim > 1:
                shap_arr = shap_arr[0]

            return dict(zip(X.columns, shap_arr))

        except Exception as e:
            logger.warning(f"SHAP explanation failed: {e}, falling back to importance")
            return self._importance_explain(X.iloc[0])

    def _importance_explain(self, features: pd.Series) -> dict[str, float]:
        """Feature importance-based explanation (fallback).

        Approximates contributions as: importance * (feature - median).
        """
        importance = self.model.get_feature_importance()

        if importance.empty:
            return {}

        contributions = {}
        for feat_name in features.index:
            if feat_name in importance.index:
                imp = importance[feat_name]
                # Contribution proportional to importance and deviation from neutral
                deviation = features[feat_name] - 0.5  # 0.5 is neutral for ranked features
                contributions[feat_name] = float(imp * deviation)

        return contributions
