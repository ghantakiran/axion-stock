"""Walk-Forward Validation.

Implements expanding window walk-forward validation to prevent
overfitting in time-series financial data.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import WalkForwardConfig

logger = logging.getLogger(__name__)


@dataclass
class Split:
    """A single train/test split."""

    train_start: date
    train_end: date
    test_start: date
    test_end: date
    split_idx: int = 0

    @property
    def train_days(self) -> int:
        return (self.train_end - self.train_start).days

    @property
    def test_days(self) -> int:
        return (self.test_end - self.test_start).days

    def __repr__(self):
        return (
            f"Split({self.split_idx}: "
            f"train [{self.train_start} → {self.train_end}], "
            f"test [{self.test_start} → {self.test_end}])"
        )


@dataclass
class WalkForwardResult:
    """Result of a single walk-forward fold."""

    split: Split
    metrics: dict
    predictions: Optional[pd.DataFrame] = None
    feature_importance: Optional[pd.Series] = None


class WalkForwardValidator:
    """Expanding window walk-forward validation.

    Ensures no future data leakage by always training on past data
    and testing on the next period.

    Example:
        validator = WalkForwardValidator()
        splits = validator.generate_splits(end_date=date(2026, 1, 1))

        for split in splits:
            X_train = X.loc[split.train_start:split.train_end]
            X_test = X.loc[split.test_start:split.test_end]
            model.train(X_train, y_train)
            metrics = model.evaluate(X_test, y_test)
    """

    def __init__(self, config: Optional[WalkForwardConfig] = None):
        self.config = config or WalkForwardConfig()

    def generate_splits(
        self,
        end_date: Optional[date] = None,
        data_dates: Optional[pd.DatetimeIndex] = None,
    ) -> list[Split]:
        """Generate train/test splits.

        Args:
            end_date: Last date to include in splits.
            data_dates: Actual dates in the data (for aligning splits).

        Returns:
            List of Split objects.
        """
        if end_date is None:
            end_date = date.today()

        splits = []
        train_start = self.config.train_start
        train_end = date(
            train_start.year + self.config.initial_train_years,
            train_start.month,
            train_start.day,
        )

        idx = 0
        while train_end < end_date:
            # Add purge gap between train and test
            test_start = train_end + timedelta(days=self.config.purge_days)
            test_end = test_start + timedelta(days=30 * self.config.test_months)
            test_end = min(test_end, end_date)

            if test_start >= end_date:
                break

            # Align to actual data dates if provided
            if data_dates is not None:
                train_end_aligned = self._align_date(train_end, data_dates, direction="backward")
                test_start_aligned = self._align_date(test_start, data_dates, direction="forward")
                test_end_aligned = self._align_date(test_end, data_dates, direction="backward")

                if train_end_aligned and test_start_aligned and test_end_aligned:
                    train_end = train_end_aligned
                    test_start = test_start_aligned
                    test_end = test_end_aligned

            splits.append(Split(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                split_idx=idx,
            ))

            # Advance train_end by retrain_months
            month = train_end.month + self.config.retrain_months
            year = train_end.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            train_end = date(year, month, min(train_end.day, 28))

            idx += 1

        logger.info(f"Generated {len(splits)} walk-forward splits")
        return splits

    def run_walk_forward(
        self,
        model,
        X: pd.DataFrame,
        y: pd.Series,
        splits: Optional[list[Split]] = None,
    ) -> list[WalkForwardResult]:
        """Run walk-forward validation on a model.

        Args:
            model: Model with train() and predict() methods.
            X: Full feature matrix indexed by date (or multi-index date/symbol).
            y: Full target series.
            splits: Pre-generated splits (or auto-generate).

        Returns:
            List of WalkForwardResult for each fold.
        """
        if splits is None:
            if isinstance(X.index, pd.MultiIndex):
                dates = X.index.get_level_values(0)
            else:
                dates = X.index
            splits = self.generate_splits(
                end_date=dates.max().date() if hasattr(dates.max(), 'date') else dates.max(),
                data_dates=pd.DatetimeIndex(dates.unique()),
            )

        results = []

        for split in splits:
            # Filter data for this split
            if isinstance(X.index, pd.MultiIndex):
                train_mask = (X.index.get_level_values(0) >= pd.Timestamp(split.train_start)) & \
                             (X.index.get_level_values(0) <= pd.Timestamp(split.train_end))
                test_mask = (X.index.get_level_values(0) >= pd.Timestamp(split.test_start)) & \
                            (X.index.get_level_values(0) <= pd.Timestamp(split.test_end))
            else:
                train_mask = (X.index >= pd.Timestamp(split.train_start)) & \
                             (X.index <= pd.Timestamp(split.train_end))
                test_mask = (X.index >= pd.Timestamp(split.test_start)) & \
                            (X.index <= pd.Timestamp(split.test_end))

            X_train = X[train_mask]
            y_train = y[train_mask]
            X_test = X[test_mask]
            y_test = y[test_mask]

            if len(X_train) < self.config.min_train_samples:
                logger.warning(f"Split {split.split_idx}: insufficient train data ({len(X_train)})")
                continue

            if len(X_test) == 0:
                logger.warning(f"Split {split.split_idx}: no test data")
                continue

            # Train
            try:
                metrics = model.train(X_train, y_train, X_val=X_test, y_val=y_test)
            except Exception as e:
                logger.error(f"Split {split.split_idx} training failed: {e}")
                continue

            # Predict on test
            try:
                predictions = model.predict(X_test)
            except Exception as e:
                logger.error(f"Split {split.split_idx} prediction failed: {e}")
                predictions = None

            # Feature importance
            try:
                importance = model.get_feature_importance()
            except Exception:
                importance = None

            results.append(WalkForwardResult(
                split=split,
                metrics=metrics,
                predictions=predictions,
                feature_importance=importance,
            ))

            logger.info(f"Split {split.split_idx}: {metrics}")

        return results

    def aggregate_results(self, results: list[WalkForwardResult]) -> dict:
        """Aggregate walk-forward results across splits.

        Args:
            results: List of WalkForwardResult.

        Returns:
            Dict of aggregated metrics.
        """
        if not results:
            return {}

        # Collect all metric keys
        metric_keys = set()
        for r in results:
            metric_keys.update(r.metrics.keys())

        aggregated = {}
        for key in metric_keys:
            values = [r.metrics[key] for r in results if key in r.metrics]
            if values:
                aggregated[f"{key}_mean"] = float(np.mean(values))
                aggregated[f"{key}_std"] = float(np.std(values))
                aggregated[f"{key}_min"] = float(np.min(values))
                aggregated[f"{key}_max"] = float(np.max(values))

        aggregated["n_splits"] = len(results)

        return aggregated

    def _align_date(
        self,
        target: date,
        dates: pd.DatetimeIndex,
        direction: str = "backward",
    ) -> Optional[date]:
        """Align a date to the nearest date in the data."""
        ts = pd.Timestamp(target)
        if direction == "backward":
            valid = dates[dates <= ts]
            return valid.max().date() if len(valid) > 0 else None
        else:
            valid = dates[dates >= ts]
            return valid.min().date() if len(valid) > 0 else None
