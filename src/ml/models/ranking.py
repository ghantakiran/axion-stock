"""Cross-Sectional Stock Ranking Model.

LightGBM-based model that predicts next-month relative performance
ranking of each stock into quintiles (1=worst to 5=best).

Uses ensemble of models with different random seeds for robustness.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import RankingModelConfig
from src.ml.models.base import BaseModel

# Try to import LightGBM, fall back to sklearn
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

try:
    from sklearn.ensemble import GradientBoostingClassifier
    SKLEARN_AVAILABLE = True
except (ImportError, ValueError):
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class StockRankingModel(BaseModel):
    """LightGBM stock ranking model.

    Predicts next-month return quintile (1-5) for each stock
    in the cross-section.

    Uses an ensemble of N models with different seeds and averages
    predictions for robustness.

    Example:
        model = StockRankingModel()
        metrics = model.train(X_train, y_train)
        predictions = model.predict(X_test)
    """

    def __init__(self, config: Optional[RankingModelConfig] = None):
        super().__init__(model_name="stock_ranking")
        self.config = config or RankingModelConfig()
        self.models: list = []  # Ensemble of models

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        **kwargs,
    ) -> dict:
        """Train ensemble of ranking models.

        Args:
            X: Feature matrix (n_samples x n_features).
            y: Target quintile labels (1-5).
            X_val: Validation features for early stopping.
            y_val: Validation labels.

        Returns:
            Dict of training metrics.
        """
        self.models = []

        # Adjust target to 0-indexed for model training
        y_adj = y - 1  # 0-4 instead of 1-5
        y_val_adj = y_val - 1 if y_val is not None else None

        params = self._get_params()

        for seed in range(self.config.n_ensemble):
            model = self._create_model(seed=seed, params=params)

            if LIGHTGBM_AVAILABLE:
                callbacks = []
                if X_val is not None:
                    callbacks.append(lgb.early_stopping(50, verbose=False))
                    callbacks.append(lgb.log_evaluation(period=0))

                model.fit(
                    X, y_adj,
                    eval_set=[(X_val, y_val_adj)] if X_val is not None else None,
                    callbacks=callbacks if callbacks else None,
                )
            else:
                model.fit(X, y_adj)

            self.models.append(model)

        self._is_fitted = True

        # Calculate metrics
        train_preds = self.predict(X)
        metrics = self._calculate_metrics(y, train_preds)

        if X_val is not None and y_val is not None:
            val_preds = self.predict(X_val)
            val_metrics = self._calculate_metrics(y_val, val_preds)
            metrics.update({f"val_{k}": v for k, v in val_metrics.items()})

        self._update_metadata(X, metrics, hyperparameters=params)
        logger.info(f"Ranking model trained: {metrics}")

        return metrics

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predict quintile probabilities and scores.

        Args:
            X: Feature matrix.

        Returns:
            DataFrame with columns: predicted_quintile, score, prob_q1..prob_q5.
        """
        if not self._is_fitted:
            raise ValueError("Model not trained. Call train() first.")

        all_probs = []

        for model in self.models:
            if LIGHTGBM_AVAILABLE:
                probs = model.predict_proba(X)
            else:
                probs = model.predict_proba(X)
            all_probs.append(probs)

        # Average probabilities across ensemble
        avg_probs = np.mean(all_probs, axis=0)

        # Create result DataFrame
        result = pd.DataFrame(index=X.index)

        for q in range(self.config.num_quintiles):
            result[f"prob_q{q+1}"] = avg_probs[:, q] if avg_probs.shape[1] > q else 0

        # Predicted quintile (1-indexed)
        result["predicted_quintile"] = avg_probs.argmax(axis=1) + 1

        # Continuous score: weighted average of quintile probabilities
        weights = np.arange(1, self.config.num_quintiles + 1)
        result["score"] = avg_probs @ weights / self.config.num_quintiles

        # Normalize score to 0-1 range
        score_min = result["score"].min()
        score_max = result["score"].max()
        if score_max > score_min:
            result["score"] = (result["score"] - score_min) / (score_max - score_min)

        return result

    def predict_rank(self, X: pd.DataFrame) -> pd.Series:
        """Predict continuous rank score (0-1).

        Convenience method for score blending.

        Args:
            X: Feature matrix.

        Returns:
            Series of rank scores (0=worst, 1=best).
        """
        predictions = self.predict(X)
        return predictions["score"]

    def get_feature_importance(self) -> pd.Series:
        """Get average feature importance across ensemble."""
        if not self._is_fitted:
            return pd.Series(dtype=float)

        importances = []
        for model in self.models:
            if LIGHTGBM_AVAILABLE:
                imp = model.feature_importances_
            else:
                imp = model.feature_importances_
            importances.append(imp)

        avg_importance = np.mean(importances, axis=0)

        # Use feature names from metadata or model
        feature_names = self.metadata.feature_names
        if not feature_names:
            feature_names = [f"f{i}" for i in range(len(avg_importance))]

        return pd.Series(avg_importance, index=feature_names).sort_values(ascending=False)

    def _create_model(self, seed: int, params: dict):
        """Create a single model instance."""
        if LIGHTGBM_AVAILABLE:
            return lgb.LGBMClassifier(
                n_estimators=params["n_estimators"],
                max_depth=params["max_depth"],
                learning_rate=params["learning_rate"],
                min_child_samples=params["min_child_samples"],
                subsample=params["subsample"],
                colsample_bytree=params["colsample_bytree"],
                reg_alpha=params["reg_alpha"],
                reg_lambda=params["reg_lambda"],
                num_leaves=params.get("num_leaves", 31),
                random_state=42 + seed,
                n_jobs=-1,
                verbose=-1,
            )
        else:
            # Fallback to sklearn GradientBoosting
            return GradientBoostingClassifier(
                n_estimators=min(params["n_estimators"], 200),
                max_depth=params["max_depth"],
                learning_rate=params["learning_rate"],
                min_samples_leaf=params["min_child_samples"],
                subsample=params["subsample"],
                random_state=42 + seed,
            )

    def _get_params(self) -> dict:
        """Get model parameters from config."""
        return {
            "n_estimators": self.config.n_estimators,
            "max_depth": self.config.max_depth,
            "learning_rate": self.config.learning_rate,
            "min_child_samples": self.config.min_child_samples,
            "subsample": self.config.subsample,
            "colsample_bytree": self.config.colsample_bytree,
            "reg_alpha": self.config.reg_alpha,
            "reg_lambda": self.config.reg_lambda,
            "num_leaves": self.config.num_leaves,
        }

    def _calculate_metrics(
        self,
        y_true: pd.Series,
        predictions: pd.DataFrame,
    ) -> dict:
        """Calculate ranking model metrics."""
        predicted = predictions["predicted_quintile"]
        scores = predictions["score"]

        # Accuracy
        accuracy = (predicted == y_true).mean()

        # Top/bottom quintile accuracy
        top_mask = y_true == self.config.num_quintiles
        bottom_mask = y_true == 1
        top_accuracy = (predicted[top_mask] == self.config.num_quintiles).mean() if top_mask.sum() > 0 else 0
        bottom_accuracy = (predicted[bottom_mask] == 1).mean() if bottom_mask.sum() > 0 else 0

        # Information Coefficient (rank correlation)
        from scipy.stats import spearmanr
        try:
            ic, ic_pval = spearmanr(y_true, scores)
        except Exception:
            ic, ic_pval = 0, 1

        return {
            "accuracy": float(accuracy),
            "top_quintile_accuracy": float(top_accuracy),
            "bottom_quintile_accuracy": float(bottom_accuracy),
            "information_coefficient": float(ic),
            "ic_pvalue": float(ic_pval),
        }
