"""PRD-177: VWAP Mean-Reversion Strategy.

Buys when price drops below VWAP and RSI is oversold,
sells when price rises above VWAP and RSI is overbought.
Classic intraday mean-reversion approach.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType


@dataclass
class VWAPConfig:
    """Configuration for VWAP strategy.

    Attributes:
        rsi_period: RSI lookback period.
        rsi_oversold: RSI threshold for long entry.
        rsi_overbought: RSI threshold for short entry.
        vwap_deviation_pct: Minimum % distance from VWAP to trigger.
        min_volume_ratio: Minimum volume vs average to confirm.
        risk_reward: Target risk/reward ratio.
    """

    rsi_period: int = 14
    rsi_oversold: float = 40.0
    rsi_overbought: float = 60.0
    vwap_deviation_pct: float = 0.5
    min_volume_ratio: float = 1.0
    risk_reward: float = 2.0


class VWAPStrategy:
    """VWAP mean-reversion strategy.

    Entry logic:
    - Long: price < VWAP * (1 - deviation%) AND RSI < oversold
    - Short: price > VWAP * (1 + deviation%) AND RSI > overbought

    Exit: target at VWAP, stop at 2x deviation from VWAP.
    """

    def __init__(self, config: VWAPConfig | None = None) -> None:
        self.config = config or VWAPConfig()

    @property
    def name(self) -> str:
        return "vwap_reversion"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze bars for VWAP mean-reversion opportunity."""
        if len(closes) < self.config.rsi_period + 1 or len(volumes) < 2:
            return None

        vwap = self._compute_vwap(highs, lows, closes, volumes)
        rsi = self._compute_rsi(closes, self.config.rsi_period)
        price = closes[-1]
        avg_vol = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)
        vol_ratio = volumes[-1] / max(avg_vol, 1)

        if vol_ratio < self.config.min_volume_ratio:
            return None

        deviation = (price - vwap) / max(vwap, 0.01) * 100

        if deviation < -self.config.vwap_deviation_pct and rsi < self.config.rsi_oversold:
            # Long: price below VWAP and RSI oversold
            stop = price - abs(price - vwap) * 2
            target = vwap
            conviction = min(90, 50 + abs(deviation) * 5 + (self.config.rsi_oversold - rsi))
            return TradeSignal(
                ticker=ticker,
                direction="long",
                signal_type=SignalType.CLOUD_BOUNCE_LONG,
                entry_price=price,
                stop_loss=stop,
                target_price=target,
                conviction=conviction,
                timeframe="5m",
                timestamp=datetime.now(timezone.utc),
            )

        if deviation > self.config.vwap_deviation_pct and rsi > self.config.rsi_overbought:
            # Short: price above VWAP and RSI overbought
            stop = price + abs(price - vwap) * 2
            target = vwap
            conviction = min(90, 50 + abs(deviation) * 5 + (rsi - self.config.rsi_overbought))
            return TradeSignal(
                ticker=ticker,
                direction="short",
                signal_type=SignalType.CLOUD_BOUNCE_SHORT,
                entry_price=price,
                stop_loss=stop,
                target_price=target,
                conviction=conviction,
                timeframe="5m",
                timestamp=datetime.now(timezone.utc),
            )

        return None

    @staticmethod
    def _compute_vwap(
        highs: list[float], lows: list[float],
        closes: list[float], volumes: list[float],
    ) -> float:
        """Compute VWAP from OHLCV data."""
        total_vp = 0.0
        total_v = 0.0
        for h, l, c, v in zip(highs, lows, closes, volumes):
            typical = (h + l + c) / 3
            total_vp += typical * v
            total_v += v
        return total_vp / max(total_v, 1)

    @staticmethod
    def _compute_rsi(closes: list[float], period: int) -> float:
        """Compute RSI from close prices."""
        if len(closes) < period + 1:
            return 50.0
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        recent = changes[-period:]
        gains = [c for c in recent if c > 0]
        losses = [-c for c in recent if c < 0]
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        if avg_loss < 1e-10:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
