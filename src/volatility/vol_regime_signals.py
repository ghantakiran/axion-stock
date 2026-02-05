"""Volatility Regime Signals.

Generates trading signals from volatility regime states,
vol-of-vol, mean-reversion dynamics, and regime transitions.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class VolOfVol:
    """Volatility of volatility (vol-of-vol) measurement."""
    symbol: str = ""
    vol_of_vol: float = 0.0  # Std dev of vol changes
    vol_of_vol_percentile: float = 50.0
    current_vol: float = 0.0
    avg_vol: float = 0.0
    n_periods: int = 0

    @property
    def is_elevated(self) -> bool:
        return self.vol_of_vol_percentile > 75.0

    @property
    def is_suppressed(self) -> bool:
        return self.vol_of_vol_percentile < 25.0

    @property
    def stability_score(self) -> float:
        """0-1 score: 1 = very stable, 0 = very unstable."""
        return max(0.0, 1.0 - self.vol_of_vol_percentile / 100.0)


@dataclass
class MeanReversionSignal:
    """Volatility mean-reversion signal."""
    symbol: str = ""
    current_vol: float = 0.0
    mean_vol: float = 0.0
    half_life_days: float = 0.0
    z_score: float = 0.0
    expected_change: float = 0.0  # Expected vol change toward mean
    signal: str = "neutral"  # sell_vol, buy_vol, neutral

    @property
    def is_actionable(self) -> bool:
        return abs(self.z_score) > 1.5 and self.half_life_days > 0

    @property
    def signal_strength(self) -> float:
        return min(1.0, abs(self.z_score) / 3.0)


@dataclass
class RegimeTransitionSignal:
    """Signal from vol regime transition."""
    symbol: str = ""
    from_regime: str = ""
    to_regime: str = ""
    transition_type: str = ""  # escalation, de-escalation, spike, normalization
    signal: str = "neutral"  # risk_off, risk_on, hedge, neutral
    strength: float = 0.0  # 0-1
    days_in_new_regime: int = 0

    @property
    def is_risk_off(self) -> bool:
        return self.signal == "risk_off"

    @property
    def is_confirmed(self) -> bool:
        return self.days_in_new_regime >= 3


@dataclass
class VolSignalSummary:
    """Combined vol regime signal summary."""
    symbol: str = ""
    vol_of_vol: Optional[VolOfVol] = None
    mean_reversion: Optional[MeanReversionSignal] = None
    regime_transition: Optional[RegimeTransitionSignal] = None
    composite_signal: str = "neutral"  # strong_risk_off, risk_off, neutral, risk_on, strong_risk_on
    composite_strength: float = 0.0
    n_signals: int = 0

    @property
    def is_strong_signal(self) -> bool:
        return self.composite_strength >= 0.6

    @property
    def recommended_action(self) -> str:
        if self.composite_signal == "strong_risk_off":
            return "reduce_exposure"
        elif self.composite_signal == "risk_off":
            return "add_hedges"
        elif self.composite_signal == "strong_risk_on":
            return "increase_exposure"
        elif self.composite_signal == "risk_on":
            return "reduce_hedges"
        return "hold"


# ---------------------------------------------------------------------------
# Regime transition signal map
# ---------------------------------------------------------------------------
TRANSITION_SIGNALS = {
    ("low", "normal"): ("escalation", "neutral", 0.3),
    ("low", "high"): ("spike", "risk_off", 0.7),
    ("low", "extreme"): ("spike", "risk_off", 1.0),
    ("normal", "low"): ("de-escalation", "risk_on", 0.3),
    ("normal", "high"): ("escalation", "risk_off", 0.6),
    ("normal", "extreme"): ("spike", "risk_off", 0.9),
    ("high", "low"): ("normalization", "risk_on", 0.6),
    ("high", "normal"): ("de-escalation", "risk_on", 0.4),
    ("high", "extreme"): ("escalation", "risk_off", 0.8),
    ("extreme", "low"): ("normalization", "risk_on", 0.8),
    ("extreme", "normal"): ("normalization", "risk_on", 0.6),
    ("extreme", "high"): ("de-escalation", "risk_on", 0.3),
}


# ---------------------------------------------------------------------------
# Vol Regime Signal Generator
# ---------------------------------------------------------------------------
class VolRegimeSignalGenerator:
    """Generates trading signals from volatility regime analysis.

    Combines vol-of-vol, mean-reversion, and regime transition
    signals into actionable recommendations.
    """

    def __init__(
        self,
        mean_reversion_hl: float = 21.0,
        vov_window: int = 63,
    ) -> None:
        self.mean_reversion_hl = mean_reversion_hl
        self.vov_window = vov_window

    def compute_vol_of_vol(
        self,
        vol_series: list[float],
        symbol: str = "",
    ) -> VolOfVol:
        """Compute volatility of volatility.

        Args:
            vol_series: Historical volatility readings.
            symbol: Ticker symbol.

        Returns:
            VolOfVol measurement.
        """
        if len(vol_series) < 10:
            return VolOfVol(
                symbol=symbol,
                current_vol=vol_series[-1] if vol_series else 0.0,
                n_periods=len(vol_series),
            )

        arr = np.array(vol_series)
        vol_changes = np.diff(arr)
        vov = float(np.std(vol_changes))

        # Rolling vov for percentile
        window = min(self.vov_window, len(vol_changes))
        rolling_vov = []
        for i in range(window, len(vol_changes) + 1):
            rolling_vov.append(float(np.std(vol_changes[i - window:i])))

        if rolling_vov:
            pct = float(np.mean(np.array(rolling_vov) <= vov)) * 100
        else:
            pct = 50.0

        return VolOfVol(
            symbol=symbol,
            vol_of_vol=round(vov, 6),
            vol_of_vol_percentile=round(pct, 2),
            current_vol=round(float(arr[-1]), 6),
            avg_vol=round(float(np.mean(arr)), 6),
            n_periods=len(vol_series),
        )

    def mean_reversion_signal(
        self,
        vol_series: list[float],
        symbol: str = "",
    ) -> MeanReversionSignal:
        """Generate mean-reversion signal from vol series.

        Args:
            vol_series: Historical volatility readings.
            symbol: Ticker symbol.

        Returns:
            MeanReversionSignal with direction and strength.
        """
        if len(vol_series) < 20:
            return MeanReversionSignal(symbol=symbol)

        arr = np.array(vol_series)
        current = float(arr[-1])
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        z = (current - mean) / std if std > 0 else 0.0

        # Half-life estimation via AR(1) regression
        y = arr[1:]
        x = arr[:-1]
        if len(x) > 10:
            cov_xy = float(np.cov(x, y)[0, 1])
            var_x = float(np.var(x))
            if var_x > 0:
                phi = cov_xy / var_x
                if 0 < phi < 1:
                    half_life = -np.log(2) / np.log(phi)
                else:
                    half_life = self.mean_reversion_hl
            else:
                half_life = self.mean_reversion_hl
        else:
            half_life = self.mean_reversion_hl

        # Expected change: vol moves toward mean
        expected = (mean - current) * (1 - np.exp(-np.log(2) / max(1, half_life)))

        # Signal
        if z > 1.5:
            signal = "sell_vol"
        elif z < -1.5:
            signal = "buy_vol"
        else:
            signal = "neutral"

        return MeanReversionSignal(
            symbol=symbol,
            current_vol=round(current, 6),
            mean_vol=round(mean, 6),
            half_life_days=round(float(half_life), 2),
            z_score=round(z, 4),
            expected_change=round(float(expected), 6),
            signal=signal,
        )

    def regime_transition_signal(
        self,
        from_regime: str,
        to_regime: str,
        days_in_new: int = 1,
        symbol: str = "",
    ) -> RegimeTransitionSignal:
        """Generate signal from regime transition.

        Args:
            from_regime: Previous regime (low/normal/high/extreme).
            to_regime: New regime.
            days_in_new: Days in new regime.
            symbol: Ticker symbol.

        Returns:
            RegimeTransitionSignal.
        """
        key = (from_regime, to_regime)
        if key in TRANSITION_SIGNALS:
            trans_type, signal, strength = TRANSITION_SIGNALS[key]
        else:
            trans_type = "stable"
            signal = "neutral"
            strength = 0.0

        # Strength increases with confirmation
        if days_in_new >= 5:
            strength = min(1.0, strength * 1.2)
        elif days_in_new >= 3:
            strength = min(1.0, strength * 1.1)

        return RegimeTransitionSignal(
            symbol=symbol,
            from_regime=from_regime,
            to_regime=to_regime,
            transition_type=trans_type,
            signal=signal,
            strength=round(strength, 4),
            days_in_new_regime=days_in_new,
        )

    def generate_summary(
        self,
        vol_series: list[float],
        current_regime: str = "normal",
        prev_regime: Optional[str] = None,
        days_in_regime: int = 1,
        symbol: str = "",
    ) -> VolSignalSummary:
        """Generate comprehensive vol signal summary.

        Args:
            vol_series: Historical vol readings.
            current_regime: Current vol regime.
            prev_regime: Previous regime (if transition occurred).
            days_in_regime: Days in current regime.
            symbol: Ticker symbol.

        Returns:
            VolSignalSummary with composite signal.
        """
        vov = self.compute_vol_of_vol(vol_series, symbol)
        mr = self.mean_reversion_signal(vol_series, symbol)

        transition = None
        if prev_regime and prev_regime != current_regime:
            transition = self.regime_transition_signal(
                prev_regime, current_regime, days_in_regime, symbol
            )

        # Composite signal
        signals = []
        if mr.signal == "sell_vol":
            signals.append(-mr.signal_strength)
        elif mr.signal == "buy_vol":
            signals.append(mr.signal_strength)

        if transition:
            if transition.is_risk_off:
                signals.append(-transition.strength)
            elif transition.signal == "risk_on":
                signals.append(transition.strength)

        if vov.is_elevated:
            signals.append(-0.3)  # Elevated vov = caution
        elif vov.is_suppressed:
            signals.append(0.2)  # Low vov = opportunity

        n_signals = len(signals)
        if signals:
            avg_signal = float(np.mean(signals))
        else:
            avg_signal = 0.0

        if avg_signal > 0.5:
            composite = "strong_risk_on"
        elif avg_signal > 0.2:
            composite = "risk_on"
        elif avg_signal < -0.5:
            composite = "strong_risk_off"
        elif avg_signal < -0.2:
            composite = "risk_off"
        else:
            composite = "neutral"

        return VolSignalSummary(
            symbol=symbol,
            vol_of_vol=vov,
            mean_reversion=mr,
            regime_transition=transition,
            composite_signal=composite,
            composite_strength=round(abs(avg_signal), 4),
            n_signals=n_signals,
        )
