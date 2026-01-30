"""Model Performance Tracker.

Tracks model predictions vs actuals over time to compute
rolling metrics and detect degradation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import MonitoringConfig

try:
    from scipy.stats import spearmanr
    SCIPY_AVAILABLE = True
except (ImportError, ValueError):
    SCIPY_AVAILABLE = False

    def spearmanr(a, b):
        """Fallback Spearman rank correlation using numpy."""
        from pandas import Series
        rank_a = Series(a).rank()
        rank_b = Series(b).rank()
        n = len(rank_a)
        d_sq = ((rank_a - rank_b) ** 2).sum()
        rho = 1 - (6 * d_sq) / (n * (n**2 - 1))
        return rho, 0.0  # p-value not computed in fallback

logger = logging.getLogger(__name__)


@dataclass
class ModelHealthStatus:
    """Health status for a model."""

    model_name: str = ""
    status: str = "healthy"  # healthy, warning, degraded, stale
    current_ic: float = 0.0
    rolling_ic_3m: float = 0.0
    ic_trend: str = "stable"  # improving, stable, declining
    last_prediction_date: str = ""
    last_retrained_date: str = ""
    model_age_days: int = 0
    needs_retraining: bool = False
    message: str = ""

    # Model-specific metrics
    additional_metrics: dict = field(default_factory=dict)


class ModelPerformanceTracker:
    """Track model performance over time.

    Records predictions and actual outcomes to compute rolling
    metrics like Information Coefficient.

    Example:
        tracker = ModelPerformanceTracker()

        # Record monthly prediction
        tracker.record_prediction("ranking", predictions, date)

        # Later, record actual outcomes
        tracker.record_actuals("ranking", actuals, date)

        # Check health
        status = tracker.get_health_status("ranking")
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()

        # Storage: {model_name: DataFrame with columns [date, symbol, predicted, actual]}
        self._records: dict[str, pd.DataFrame] = {}

        # Model metadata
        self._model_dates: dict[str, dict] = {}  # {model: {trained_at, last_prediction}}

    def record_prediction(
        self,
        model_name: str,
        predictions: pd.Series,
        prediction_date: date,
    ) -> None:
        """Record model predictions for later evaluation.

        Args:
            model_name: Name of the model.
            predictions: Series of predictions indexed by symbol.
            prediction_date: Date of prediction.
        """
        records = []
        for symbol, pred in predictions.items():
            records.append({
                "date": prediction_date,
                "symbol": symbol,
                "predicted": pred,
                "actual": np.nan,
            })

        new_df = pd.DataFrame(records)

        if model_name in self._records:
            self._records[model_name] = pd.concat(
                [self._records[model_name], new_df], ignore_index=True
            )
        else:
            self._records[model_name] = new_df

        if model_name not in self._model_dates:
            self._model_dates[model_name] = {}
        self._model_dates[model_name]["last_prediction"] = prediction_date.isoformat()

    def record_actuals(
        self,
        model_name: str,
        actuals: pd.Series,
        prediction_date: date,
    ) -> None:
        """Record actual outcomes for a prediction date.

        Args:
            model_name: Name of the model.
            actuals: Series of actual outcomes indexed by symbol.
            prediction_date: Date of the original prediction.
        """
        if model_name not in self._records:
            return

        df = self._records[model_name]
        mask = df["date"] == prediction_date

        for symbol, actual in actuals.items():
            symbol_mask = mask & (df["symbol"] == symbol)
            df.loc[symbol_mask, "actual"] = actual

    def set_model_trained_date(self, model_name: str, trained_date: str) -> None:
        """Record when a model was last trained."""
        if model_name not in self._model_dates:
            self._model_dates[model_name] = {}
        self._model_dates[model_name]["trained_at"] = trained_date

    def calculate_ic(
        self,
        model_name: str,
        lookback_months: Optional[int] = None,
    ) -> float:
        """Calculate Information Coefficient.

        IC is the rank correlation between predictions and actuals.

        Args:
            model_name: Model name.
            lookback_months: Only use this many months of data.

        Returns:
            Information Coefficient value.
        """
        if model_name not in self._records:
            return 0.0

        df = self._records[model_name].dropna(subset=["actual"])
        if len(df) < 10:
            return 0.0

        if lookback_months:
            cutoff = pd.Timestamp.now() - pd.DateOffset(months=lookback_months)
            df = df[pd.to_datetime(df["date"]) >= cutoff]

        if len(df) < 10:
            return 0.0

        try:
            ic, _ = spearmanr(df["predicted"], df["actual"])
            return float(ic)
        except Exception:
            return 0.0

    def calculate_monthly_ic(self, model_name: str) -> pd.Series:
        """Calculate IC for each month.

        Args:
            model_name: Model name.

        Returns:
            Series of monthly IC values.
        """
        if model_name not in self._records:
            return pd.Series(dtype=float)

        df = self._records[model_name].dropna(subset=["actual"])
        if df.empty:
            return pd.Series(dtype=float)

        df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
        monthly_ics = {}

        for month, group in df.groupby("month"):
            if len(group) >= 5:
                try:
                    ic, _ = spearmanr(group["predicted"], group["actual"])
                    monthly_ics[str(month)] = float(ic)
                except Exception:
                    pass

        return pd.Series(monthly_ics)

    def get_health_status(self, model_name: str) -> ModelHealthStatus:
        """Get health status for a model.

        Args:
            model_name: Model name.

        Returns:
            ModelHealthStatus with current metrics and status.
        """
        status = ModelHealthStatus(model_name=model_name)

        # IC metrics
        status.current_ic = self.calculate_ic(model_name, lookback_months=1)
        status.rolling_ic_3m = self.calculate_ic(model_name, lookback_months=3)

        monthly_ics = self.calculate_monthly_ic(model_name)

        # IC trend
        if len(monthly_ics) >= 3:
            recent = monthly_ics.iloc[-3:]
            if recent.is_monotonic_increasing:
                status.ic_trend = "improving"
            elif recent.is_monotonic_decreasing:
                status.ic_trend = "declining"
            else:
                status.ic_trend = "stable"

        # Dates
        dates = self._model_dates.get(model_name, {})
        status.last_prediction_date = dates.get("last_prediction", "")
        status.last_retrained_date = dates.get("trained_at", "")

        # Model age
        if status.last_retrained_date:
            try:
                trained_dt = datetime.fromisoformat(status.last_retrained_date)
                status.model_age_days = (datetime.now() - trained_dt).days
            except Exception:
                pass

        # Determine status
        if status.model_age_days > self.config.max_model_age_days:
            status.status = "stale"
            status.needs_retraining = True
            status.message = f"Model age ({status.model_age_days}d) exceeds max ({self.config.max_model_age_days}d)"
        elif status.rolling_ic_3m < self.config.ic_degraded:
            status.status = "degraded"
            status.needs_retraining = True
            status.message = f"IC ({status.rolling_ic_3m:.4f}) below degraded threshold ({self.config.ic_degraded})"
        elif status.rolling_ic_3m < self.config.ic_acceptable:
            status.status = "warning"
            status.message = f"IC ({status.rolling_ic_3m:.4f}) below acceptable ({self.config.ic_acceptable})"
        else:
            status.status = "healthy"
            status.message = "Model performing within expectations"

        # Check if retraining is due
        if status.model_age_days > self.config.retrain_interval_days:
            status.needs_retraining = True

        return status

    def get_all_health(self) -> dict[str, ModelHealthStatus]:
        """Get health status for all tracked models."""
        return {name: self.get_health_status(name) for name in self._records}
