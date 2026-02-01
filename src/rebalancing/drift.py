"""Drift Monitor.

Computes portfolio weight drift from target allocations and flags
assets that exceed rebalance thresholds.
"""

import logging
import math
from datetime import date
from typing import Optional

from src.rebalancing.config import (
    DriftConfig,
    DriftMethod,
    DEFAULT_DRIFT_CONFIG,
)
from src.rebalancing.models import (
    Holding,
    DriftAnalysis,
    PortfolioDrift,
)

logger = logging.getLogger(__name__)


class DriftMonitor:
    """Monitors portfolio drift from target weights."""

    def __init__(self, config: Optional[DriftConfig] = None) -> None:
        self.config = config or DEFAULT_DRIFT_CONFIG
        self._history: list[PortfolioDrift] = []

    def compute_drift(
        self,
        holdings: list[Holding],
        as_of_date: Optional[date] = None,
    ) -> PortfolioDrift:
        """Compute drift for all holdings.

        Args:
            holdings: Current portfolio holdings with target weights.
            as_of_date: Date for the snapshot.

        Returns:
            PortfolioDrift with per-asset and aggregate metrics.
        """
        if not holdings:
            return PortfolioDrift(date=as_of_date)

        asset_drifts: list[DriftAnalysis] = []

        for h in holdings:
            drift = self._compute_asset_drift(h)
            asset_drifts.append(drift)

        # Aggregate metrics
        abs_drifts = [abs(d.drift) for d in asset_drifts]
        max_drift = max(abs_drifts) if abs_drifts else 0.0
        mean_drift = sum(abs_drifts) / len(abs_drifts) if abs_drifts else 0.0
        rmse_drift = math.sqrt(sum(d ** 2 for d in abs_drifts) / len(abs_drifts)) if abs_drifts else 0.0

        n_exceeding = sum(1 for d in asset_drifts if d.needs_rebalance)
        n_critical = sum(1 for d in asset_drifts if d.is_critical)
        needs_rebalance = max_drift >= self.config.threshold

        result = PortfolioDrift(
            asset_drifts=asset_drifts,
            max_drift=round(max_drift, 4),
            mean_drift=round(mean_drift, 4),
            rmse_drift=round(rmse_drift, 4),
            n_exceeding_threshold=n_exceeding,
            n_critical=n_critical,
            needs_rebalance=needs_rebalance,
            date=as_of_date or date.today(),
        )

        self._history.append(result)
        return result

    def _compute_asset_drift(self, holding: Holding) -> DriftAnalysis:
        """Compute drift for a single asset."""
        if self.config.method == DriftMethod.ABSOLUTE:
            drift = holding.current_weight - holding.target_weight
            drift_pct = (drift / holding.target_weight * 100) if holding.target_weight > 0 else 0.0
        else:  # RELATIVE
            if holding.target_weight > 0:
                drift = (holding.current_weight - holding.target_weight) / holding.target_weight
                drift_pct = drift * 100
            else:
                drift = holding.current_weight
                drift_pct = 100.0 if holding.current_weight > 0 else 0.0

        needs_rebalance = abs(drift) >= self.config.threshold
        is_critical = abs(drift) >= self.config.critical_threshold

        return DriftAnalysis(
            symbol=holding.symbol,
            target_weight=holding.target_weight,
            current_weight=holding.current_weight,
            drift=round(drift, 4),
            drift_pct=round(drift_pct, 2),
            needs_rebalance=needs_rebalance,
            is_critical=is_critical,
        )

    def get_history(self) -> list[PortfolioDrift]:
        """Return drift history."""
        return list(self._history)

    def reset(self) -> None:
        """Clear drift history."""
        self._history.clear()
