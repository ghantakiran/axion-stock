"""Demand forecasting for PRD-130: Capacity Planning & Auto-Scaling."""

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from .config import CapacityConfig, ResourceType
from .monitor import ResourceMetric, ResourceMonitor


@dataclass
class ForecastPoint:
    """Single point in a demand forecast."""

    timestamp: datetime
    predicted_value: float
    confidence_lower: float
    confidence_upper: float


@dataclass
class DemandForecast:
    """Complete demand forecast for a resource."""

    forecast_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    resource_type: ResourceType = ResourceType.CPU
    service: str = "default"
    horizon_hours: int = 24
    points: List[ForecastPoint] = field(default_factory=list)
    model_used: str = "moving_average"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DemandForecaster:
    """Forecasts future resource demand using statistical methods."""

    def __init__(
        self,
        monitor: Optional[ResourceMonitor] = None,
        config: Optional[CapacityConfig] = None,
    ):
        self.monitor = monitor or ResourceMonitor()
        self.config = config or CapacityConfig()
        self._forecasts: Dict[str, DemandForecast] = {}
        self._actuals: Dict[str, List[float]] = {}

    def forecast(
        self,
        resource_type: ResourceType,
        service: str = "default",
        horizon_hours: int = 24,
    ) -> DemandForecast:
        """Generate a demand forecast for a resource type and service."""
        history = self.monitor.get_utilization_history(
            resource_type, service, hours=horizon_hours * 2
        )
        values = [m.utilization_pct for m in history]

        if len(values) < 3:
            # Not enough data, return flat forecast from last known or 50%
            base = values[-1] if values else 50.0
            points = self._flat_forecast(base, horizon_hours)
            model_used = "flat"
        else:
            is_seasonal, period = self.detect_seasonality(values)
            if is_seasonal and period > 0:
                points = self.forecast_with_moving_average(
                    values, horizon_hours, window=min(period, len(values))
                )
                model_used = "seasonal_moving_average"
            else:
                points = self.forecast_with_exponential_smoothing(
                    values, horizon_hours, alpha=0.3
                )
                model_used = "exponential_smoothing"

        fc = DemandForecast(
            resource_type=resource_type,
            service=service,
            horizon_hours=horizon_hours,
            points=points,
            model_used=model_used,
        )
        self._forecasts[fc.forecast_id] = fc
        return fc

    def forecast_with_moving_average(
        self,
        history: List[float],
        horizon: int,
        window: int = 5,
    ) -> List[ForecastPoint]:
        """Generate forecast points using moving average."""
        if not history:
            return []

        window = min(window, len(history))
        if window < 1:
            window = 1

        # Calculate the moving average from the last 'window' points
        recent = history[-window:]
        avg = sum(recent) / len(recent)

        # Compute standard deviation for confidence bands
        if len(recent) > 1:
            variance = sum((x - avg) ** 2 for x in recent) / (len(recent) - 1)
            std = math.sqrt(variance)
        else:
            std = avg * 0.1  # 10% default

        now = datetime.now(timezone.utc)
        points = []
        for i in range(1, horizon + 1):
            ts = now + timedelta(hours=i)
            # Widen confidence interval over time
            spread = std * (1 + 0.1 * i)
            points.append(
                ForecastPoint(
                    timestamp=ts,
                    predicted_value=round(avg, 2),
                    confidence_lower=round(max(0, avg - spread), 2),
                    confidence_upper=round(min(100, avg + spread), 2),
                )
            )
        return points

    def forecast_with_exponential_smoothing(
        self,
        history: List[float],
        horizon: int,
        alpha: float = 0.3,
    ) -> List[ForecastPoint]:
        """Generate forecast points using exponential smoothing."""
        if not history:
            return []

        alpha = max(0.01, min(1.0, alpha))

        # Apply exponential smoothing
        smoothed = history[0]
        for val in history[1:]:
            smoothed = alpha * val + (1 - alpha) * smoothed

        # Compute residual variance for confidence bands
        residuals = []
        s = history[0]
        for val in history[1:]:
            s = alpha * val + (1 - alpha) * s
            residuals.append(abs(val - s))
        avg_residual = sum(residuals) / len(residuals) if residuals else smoothed * 0.1

        now = datetime.now(timezone.utc)
        points = []
        for i in range(1, horizon + 1):
            ts = now + timedelta(hours=i)
            spread = avg_residual * (1 + 0.15 * i)
            points.append(
                ForecastPoint(
                    timestamp=ts,
                    predicted_value=round(smoothed, 2),
                    confidence_lower=round(max(0, smoothed - spread), 2),
                    confidence_upper=round(min(100, smoothed + spread), 2),
                )
            )
        return points

    def detect_seasonality(
        self, history: List[float]
    ) -> Tuple[bool, int]:
        """Detect seasonality in the history data.

        Returns (is_seasonal, period).
        """
        if len(history) < 6:
            return False, 0

        # Simple autocorrelation-based detection
        n = len(history)
        mean = sum(history) / n
        variance = sum((x - mean) ** 2 for x in history) / n

        if variance < 1e-6:
            return False, 0

        best_corr = 0.0
        best_period = 0

        max_lag = min(n // 2, 48)  # Check up to half the data length
        for lag in range(2, max_lag + 1):
            autocorr = 0.0
            for i in range(n - lag):
                autocorr += (history[i] - mean) * (history[i + lag] - mean)
            autocorr /= (n * variance)

            if autocorr > best_corr:
                best_corr = autocorr
                best_period = lag

        # Consider seasonal if autocorrelation > 0.3
        is_seasonal = best_corr > 0.3
        return is_seasonal, best_period if is_seasonal else 0

    def predict_peak(
        self,
        resource_type: ResourceType,
        service: str = "default",
    ) -> Tuple[datetime, float]:
        """Predict when the next peak utilization will occur."""
        fc = self.forecast(resource_type, service, horizon_hours=24)
        if not fc.points:
            return datetime.now(timezone.utc), 0.0

        peak_point = max(fc.points, key=lambda p: p.predicted_value)
        return peak_point.timestamp, peak_point.predicted_value

    def forecast_accuracy(self, forecast_id: str) -> float:
        """Calculate accuracy of a past forecast (MAPE-based).

        Returns accuracy as a percentage (0-100). Higher is better.
        """
        fc = self._forecasts.get(forecast_id)
        if not fc:
            return 0.0

        actuals = self._actuals.get(forecast_id, [])
        if not actuals or not fc.points:
            return 0.0

        # Calculate MAPE
        n = min(len(actuals), len(fc.points))
        errors = []
        for i in range(n):
            actual = actuals[i]
            predicted = fc.points[i].predicted_value
            if actual > 0:
                errors.append(abs(actual - predicted) / actual)
            else:
                errors.append(0.0 if predicted == 0 else 1.0)

        mape = sum(errors) / len(errors) if errors else 1.0
        accuracy = max(0.0, (1.0 - mape) * 100.0)
        return round(accuracy, 2)

    def record_actuals(self, forecast_id: str, actuals: List[float]) -> None:
        """Record actual values for accuracy tracking."""
        self._actuals[forecast_id] = actuals

    def _flat_forecast(
        self, base_value: float, horizon_hours: int
    ) -> List[ForecastPoint]:
        """Generate a flat forecast when insufficient data."""
        now = datetime.now(timezone.utc)
        points = []
        spread = base_value * 0.2
        for i in range(1, horizon_hours + 1):
            ts = now + timedelta(hours=i)
            points.append(
                ForecastPoint(
                    timestamp=ts,
                    predicted_value=round(base_value, 2),
                    confidence_lower=round(max(0, base_value - spread), 2),
                    confidence_upper=round(min(100, base_value + spread), 2),
                )
            )
        return points
