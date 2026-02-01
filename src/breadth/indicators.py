"""Core Market Breadth Indicators.

Computes advance-decline line, new highs/lows, McClellan Oscillator,
McClellan Summation Index, and breadth thrust signals.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np

from src.breadth.config import (
    McClellanConfig,
    ThrustConfig,
    NewHighsLowsConfig,
    DEFAULT_MCCLELLAN_CONFIG,
    DEFAULT_THRUST_CONFIG,
    DEFAULT_NHNL_CONFIG,
    BreadthSignal,
)
from src.breadth.models import (
    AdvanceDecline,
    NewHighsLows,
    McClellanData,
    BreadthThrustData,
    BreadthSnapshot,
)

logger = logging.getLogger(__name__)


class BreadthIndicators:
    """Computes market breadth indicators from daily data.

    Maintains state for cumulative indicators (AD line, Summation Index)
    and detects signals (divergences, thrusts, crossovers).
    """

    def __init__(
        self,
        mcclellan_config: Optional[McClellanConfig] = None,
        thrust_config: Optional[ThrustConfig] = None,
        nhnl_config: Optional[NewHighsLowsConfig] = None,
    ) -> None:
        self._mcclellan_cfg = mcclellan_config or DEFAULT_MCCLELLAN_CONFIG
        self._thrust_cfg = thrust_config or DEFAULT_THRUST_CONFIG
        self._nhnl_cfg = nhnl_config or DEFAULT_NHNL_CONFIG

        # Cumulative state
        self._cumulative_ad: float = 0.0
        self._fast_ema: float = 0.0
        self._slow_ema: float = 0.0
        self._summation_index: float = 0.0
        self._breadth_ema: float = 0.5
        self._prev_oscillator: float = 0.0
        self._bar_count: int = 0
        self._last_thrust_date: Optional[date] = None
        self._thrust_low_seen: bool = False

        # History for signals
        self._ad_history: list[AdvanceDecline] = []
        self._nhnl_history: list[NewHighsLows] = []
        self._snapshots: list[BreadthSnapshot] = []

    def process_day(
        self,
        ad: AdvanceDecline,
        nhnl: Optional[NewHighsLows] = None,
    ) -> BreadthSnapshot:
        """Process one day of breadth data.

        Args:
            ad: Advance-decline data for the day.
            nhnl: Optional new highs/lows data.

        Returns:
            BreadthSnapshot with all computed indicators.
        """
        self._bar_count += 1
        self._ad_history.append(ad)
        signals: list[BreadthSignal] = []

        # 1. Cumulative AD line
        self._cumulative_ad += ad.net_advances

        # 2. McClellan Oscillator
        mcclellan = self._compute_mcclellan(ad)
        signals.extend(self._mcclellan_signals(mcclellan))

        # 3. Breadth thrust
        thrust = self._compute_thrust(ad)
        if thrust.thrust_active:
            signals.append(BreadthSignal.BREADTH_THRUST)

        # 4. New highs/lows
        nhnl_data = None
        if nhnl:
            self._nhnl_history.append(nhnl)
            nhnl_data = nhnl
            signals.extend(self._nhnl_signals(nhnl))

        # 5. Volume signals
        if ad.volume_ratio > 3.0:
            signals.append(BreadthSignal.OVERBOUGHT)
        elif ad.volume_ratio < 0.33:
            signals.append(BreadthSignal.OVERSOLD)

        snapshot = BreadthSnapshot(
            date=ad.date,
            advance_decline=ad,
            new_highs_lows=nhnl_data,
            mcclellan=mcclellan,
            thrust=thrust,
            cumulative_ad_line=self._cumulative_ad,
            signals=signals,
        )
        self._snapshots.append(snapshot)

        return snapshot

    def _compute_mcclellan(self, ad: AdvanceDecline) -> McClellanData:
        """Compute McClellan Oscillator and Summation Index."""
        net = float(ad.net_advances)
        fast_k = 2.0 / (self._mcclellan_cfg.fast_period + 1)
        slow_k = 2.0 / (self._mcclellan_cfg.slow_period + 1)

        if self._bar_count == 1:
            self._fast_ema = net
            self._slow_ema = net
        else:
            self._fast_ema = net * fast_k + self._fast_ema * (1 - fast_k)
            self._slow_ema = net * slow_k + self._slow_ema * (1 - slow_k)

        oscillator = self._fast_ema - self._slow_ema
        self._summation_index += oscillator

        data = McClellanData(
            date=ad.date,
            fast_ema=round(self._fast_ema, 2),
            slow_ema=round(self._slow_ema, 2),
            oscillator=round(oscillator, 2),
            summation_index=round(self._summation_index, 2),
        )

        return data

    def _mcclellan_signals(self, data: McClellanData) -> list[BreadthSignal]:
        """Detect McClellan-based signals."""
        signals = []
        if data.is_overbought:
            signals.append(BreadthSignal.OVERBOUGHT)
        elif data.is_oversold:
            signals.append(BreadthSignal.OVERSOLD)

        # Zero-line crossover (compare previous oscillator to current)
        if self._bar_count > 1:
            if self._prev_oscillator <= 0 < data.oscillator:
                signals.append(BreadthSignal.ZERO_CROSS_UP)
            elif self._prev_oscillator >= 0 > data.oscillator:
                signals.append(BreadthSignal.ZERO_CROSS_DOWN)

        # Update prev AFTER signal detection
        self._prev_oscillator = data.oscillator

        return signals

    def _compute_thrust(self, ad: AdvanceDecline) -> BreadthThrustData:
        """Compute breadth thrust indicator."""
        breadth_pct = ad.breadth_pct
        k = 2.0 / (self._thrust_cfg.ema_period + 1)

        if self._bar_count == 1:
            self._breadth_ema = breadth_pct
        else:
            self._breadth_ema = breadth_pct * k + self._breadth_ema * (1 - k)

        # Thrust detection: EMA goes from <0.40 to >0.615
        thrust_active = False
        if self._breadth_ema < self._thrust_cfg.low_threshold:
            self._thrust_low_seen = True
        elif self._thrust_low_seen and self._breadth_ema > self._thrust_cfg.high_threshold:
            thrust_active = True
            self._last_thrust_date = ad.date
            self._thrust_low_seen = False

        days_since = None
        if self._last_thrust_date and not thrust_active:
            days_since = (ad.date - self._last_thrust_date).days

        return BreadthThrustData(
            date=ad.date,
            breadth_ema=round(self._breadth_ema, 4),
            thrust_active=thrust_active,
            days_since_last_thrust=days_since,
            last_thrust_date=self._last_thrust_date,
        )

    def _nhnl_signals(self, nhnl: NewHighsLows) -> list[BreadthSignal]:
        """Detect new highs/lows signals."""
        signals = []
        if nhnl.new_highs >= self._nhnl_cfg.high_pole_threshold:
            signals.append(BreadthSignal.NEW_HIGH_POLE)
        if nhnl.new_lows >= self._nhnl_cfg.low_pole_threshold:
            signals.append(BreadthSignal.NEW_LOW_POLE)
        return signals

    def get_nhnl_moving_average(self) -> float:
        """Get the moving average of NH-NL difference."""
        period = self._nhnl_cfg.ma_period
        if len(self._nhnl_history) < period:
            if not self._nhnl_history:
                return 0.0
            vals = [d.net for d in self._nhnl_history]
            return sum(vals) / len(vals)

        recent = self._nhnl_history[-period:]
        vals = [d.net for d in recent]
        return sum(vals) / len(vals)

    @property
    def cumulative_ad_line(self) -> float:
        return self._cumulative_ad

    @property
    def summation_index(self) -> float:
        return self._summation_index

    @property
    def bar_count(self) -> int:
        return self._bar_count

    @property
    def snapshots(self) -> list[BreadthSnapshot]:
        return list(self._snapshots)

    def reset(self) -> None:
        """Reset all state."""
        self._cumulative_ad = 0.0
        self._fast_ema = 0.0
        self._slow_ema = 0.0
        self._summation_index = 0.0
        self._breadth_ema = 0.5
        self._prev_oscillator = 0.0
        self._bar_count = 0
        self._last_thrust_date = None
        self._thrust_low_seen = False
        self._ad_history.clear()
        self._nhnl_history.clear()
        self._snapshots.clear()
