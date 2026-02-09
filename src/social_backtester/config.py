"""Configuration for Social Signal Backtester."""
from dataclasses import dataclass, field
from enum import Enum


class OutcomeHorizon(str, Enum):
    """Forward return measurement horizons."""

    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    DAY_5 = "5d"
    DAY_10 = "10d"
    DAY_30 = "30d"


class ValidationMethod(str, Enum):
    """Signal validation methodology."""

    DIRECTION_ACCURACY = "direction_accuracy"
    SCORE_CORRELATION = "score_correlation"
    PERCENTILE_BINS = "percentile_bins"


@dataclass
class BacktesterConfig:
    """Configuration for the social signal backtester."""

    horizons: list[OutcomeHorizon] = field(
        default_factory=lambda: [
            OutcomeHorizon.DAY_1,
            OutcomeHorizon.DAY_5,
            OutcomeHorizon.DAY_30,
        ]
    )
    validation_methods: list[ValidationMethod] = field(
        default_factory=lambda: [
            ValidationMethod.DIRECTION_ACCURACY,
            ValidationMethod.SCORE_CORRELATION,
        ]
    )
    min_signals: int = 20
    score_threshold: float = 50.0
    significance_level: float = 0.05
    max_lag_days: int = 10
    lookback_days: int = 90
