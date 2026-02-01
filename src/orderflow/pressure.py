"""Buy/Sell Pressure Analyzer.

Computes volume-weighted directional pressure, net flow,
cumulative delta, and pressure ratios from trade data.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.orderflow.config import (
    PressureConfig,
    PressureDirection,
    DEFAULT_PRESSURE_CONFIG,
)
from src.orderflow.models import FlowPressure

logger = logging.getLogger(__name__)


class PressureAnalyzer:
    """Analyzes buy/sell pressure from trade flow."""

    def __init__(self, config: Optional[PressureConfig] = None) -> None:
        self.config = config or DEFAULT_PRESSURE_CONFIG
        self._cumulative_delta: float = 0.0
        self._history: list[FlowPressure] = []

    def compute_pressure(
        self,
        buy_volume: float,
        sell_volume: float,
        symbol: str = "",
    ) -> FlowPressure:
        """Compute buy/sell pressure for a single period.

        Args:
            buy_volume: Volume on bid (buy-initiated).
            sell_volume: Volume on ask (sell-initiated).
            symbol: Asset symbol.

        Returns:
            FlowPressure with directional metrics.
        """
        net_flow = buy_volume - sell_volume
        self._cumulative_delta += net_flow

        ratio = buy_volume / sell_volume if sell_volume > 0 else (999.0 if buy_volume > 0 else 1.0)
        direction = self._classify(ratio)

        result = FlowPressure(
            symbol=symbol,
            buy_volume=round(buy_volume, 0),
            sell_volume=round(sell_volume, 0),
            net_flow=round(net_flow, 0),
            pressure_ratio=round(min(ratio, 999.0), 3),
            direction=direction,
            cumulative_delta=round(self._cumulative_delta, 0),
        )

        self._history.append(result)
        return result

    def compute_series(
        self,
        buy_volumes: pd.Series,
        sell_volumes: pd.Series,
        symbol: str = "",
    ) -> list[FlowPressure]:
        """Compute pressure for a series of periods.

        Args:
            buy_volumes: Buy volume per period.
            sell_volumes: Sell volume per period.
            symbol: Asset symbol.

        Returns:
            List of FlowPressure, one per period.
        """
        n = min(len(buy_volumes), len(sell_volumes))
        results: list[FlowPressure] = []

        for i in range(n):
            bv = float(buy_volumes.iloc[i])
            sv = float(sell_volumes.iloc[i])
            results.append(self.compute_pressure(bv, sv, symbol=symbol))

        return results

    def smoothed_ratio(
        self,
        buy_volumes: pd.Series,
        sell_volumes: pd.Series,
    ) -> pd.Series:
        """Compute smoothed buy/sell ratio.

        Returns:
            Smoothed pressure ratio series.
        """
        n = min(len(buy_volumes), len(sell_volumes))
        bv = buy_volumes.values[:n].astype(float)
        sv = sell_volumes.values[:n].astype(float)

        # Avoid division by zero
        sv_safe = np.where(sv == 0, 1.0, sv)
        raw_ratio = bv / sv_safe

        # Simple moving average smoothing
        window = self.config.smoothing_window
        smoothed = pd.Series(raw_ratio).rolling(window, min_periods=1).mean()
        return smoothed

    def _classify(self, ratio: float) -> PressureDirection:
        """Classify pressure ratio into direction."""
        if ratio >= self.config.strong_buying_threshold:
            return PressureDirection.BUYING
        elif ratio <= self.config.strong_selling_threshold:
            return PressureDirection.SELLING
        else:
            return PressureDirection.NEUTRAL

    def get_cumulative_delta(self) -> float:
        return self._cumulative_delta

    def get_history(self) -> list[FlowPressure]:
        return list(self._history)

    def reset(self) -> None:
        self._cumulative_delta = 0.0
        self._history.clear()
