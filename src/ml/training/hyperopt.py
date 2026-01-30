"""Hyperparameter Optimization.

Bayesian optimization of model hyperparameters using walk-forward
validation to prevent overfitting.
"""

import logging
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from src.ml.config import RankingModelConfig

# Try to import Optuna, fall back to grid search
try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default search space for LightGBM ranking model
DEFAULT_SEARCH_SPACE = {
    "n_estimators": {"type": "int", "low": 200, "high": 1000, "step": 100},
    "max_depth": {"type": "int", "low": 4, "high": 8},
    "learning_rate": {"type": "float", "low": 0.01, "high": 0.1, "log": True},
    "min_child_samples": {"type": "int", "low": 20, "high": 100, "step": 10},
    "subsample": {"type": "float", "low": 0.7, "high": 0.9},
    "colsample_bytree": {"type": "float", "low": 0.7, "high": 0.9},
    "reg_alpha": {"type": "float", "low": 0.001, "high": 1.0, "log": True},
    "reg_lambda": {"type": "float", "low": 0.001, "high": 1.0, "log": True},
    "num_leaves": {"type": "int", "low": 15, "high": 63},
}


class HyperparameterOptimizer:
    """Bayesian hyperparameter optimization.

    Uses Optuna for efficient search with walk-forward CV as the
    objective function.

    Example:
        optimizer = HyperparameterOptimizer()
        best_params = optimizer.optimize(
            model_class=StockRankingModel,
            X=features,
            y=targets,
            n_trials=50,
        )
    """

    def __init__(
        self,
        search_space: Optional[dict] = None,
        n_trials: int = 50,
        metric: str = "information_coefficient",
        direction: str = "maximize",
    ):
        self.search_space = search_space or DEFAULT_SEARCH_SPACE
        self.n_trials = n_trials
        self.metric = metric
        self.direction = direction
        self.best_params: dict = {}
        self.study_results: list[dict] = []

    def optimize(
        self,
        model_factory: Callable,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        n_trials: Optional[int] = None,
    ) -> dict:
        """Run hyperparameter optimization.

        Args:
            model_factory: Callable that takes config dict and returns a model.
            X: Training features.
            y: Training target.
            X_val: Validation features.
            y_val: Validation target.
            n_trials: Number of trials to run.

        Returns:
            Best hyperparameters.
        """
        n_trials = n_trials or self.n_trials

        if OPTUNA_AVAILABLE:
            return self._optimize_optuna(model_factory, X, y, X_val, y_val, n_trials)
        else:
            return self._optimize_grid(model_factory, X, y, X_val, y_val)

    def _optimize_optuna(
        self,
        model_factory: Callable,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        n_trials: int,
    ) -> dict:
        """Optimize using Optuna Bayesian search."""
        def objective(trial):
            params = {}
            for name, spec in self.search_space.items():
                if spec["type"] == "int":
                    params[name] = trial.suggest_int(
                        name, spec["low"], spec["high"],
                        step=spec.get("step", 1)
                    )
                elif spec["type"] == "float":
                    if spec.get("log"):
                        params[name] = trial.suggest_float(
                            name, spec["low"], spec["high"], log=True
                        )
                    else:
                        params[name] = trial.suggest_float(
                            name, spec["low"], spec["high"]
                        )
                elif spec["type"] == "categorical":
                    params[name] = trial.suggest_categorical(name, spec["choices"])

            # Create model with these params
            config = RankingModelConfig(**params)
            model = model_factory(config)

            # Train and evaluate
            metrics = model.train(X, y, X_val=X_val, y_val=y_val)

            # Get validation metric
            val_key = f"val_{self.metric}"
            if val_key in metrics:
                return metrics[val_key]
            return metrics.get(self.metric, 0)

        study = optuna.create_study(direction=self.direction)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        self.best_params = study.best_params
        self.study_results = [
            {"number": t.number, "value": t.value, "params": t.params}
            for t in study.trials
        ]

        logger.info(f"Best params: {self.best_params}, metric: {study.best_value:.4f}")
        return self.best_params

    def _optimize_grid(
        self,
        model_factory: Callable,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
    ) -> dict:
        """Fallback grid search when Optuna is not available."""
        from itertools import product

        # Create small grid from search space
        grid = {}
        for name, spec in self.search_space.items():
            if spec["type"] == "int":
                grid[name] = [spec["low"], (spec["low"] + spec["high"]) // 2, spec["high"]]
            elif spec["type"] == "float":
                grid[name] = [spec["low"], (spec["low"] + spec["high"]) / 2, spec["high"]]
            elif spec["type"] == "categorical":
                grid[name] = spec["choices"]

        # Limit grid size
        param_names = list(grid.keys())[:4]  # Limit to 4 params
        param_values = [grid[k][:3] for k in param_names]  # Max 3 values each

        best_metric = float("-inf") if self.direction == "maximize" else float("inf")
        best_params = {}

        for values in product(*param_values):
            params = dict(zip(param_names, values))

            try:
                config = RankingModelConfig(**params)
                model = model_factory(config)
                metrics = model.train(X, y, X_val=X_val, y_val=y_val)

                val_key = f"val_{self.metric}"
                metric_val = metrics.get(val_key, metrics.get(self.metric, 0))

                if self.direction == "maximize" and metric_val > best_metric:
                    best_metric = metric_val
                    best_params = params
                elif self.direction == "minimize" and metric_val < best_metric:
                    best_metric = metric_val
                    best_params = params

            except Exception as e:
                logger.warning(f"Grid trial failed: {e}")
                continue

        self.best_params = best_params
        logger.info(f"Grid search best: {best_params}, metric: {best_metric:.4f}")
        return best_params
