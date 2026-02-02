"""Smart Money Detection.

Identifies smart money flows by contrasting institutional
vs retail positioning, with conviction scoring and
flow-price divergence detection.
"""

import logging
from typing import Optional

import numpy as np

from src.fundflow.config import (
    SmartMoneyConfig,
    SmartMoneySignal,
    DEFAULT_SMARTMONEY_CONFIG,
)
from src.fundflow.models import SmartMoneyResult

logger = logging.getLogger(__name__)


class SmartMoneyDetector:
    """Detects smart money accumulation and distribution."""

    def __init__(self, config: Optional[SmartMoneyConfig] = None) -> None:
        self.config = config or DEFAULT_SMARTMONEY_CONFIG

    def analyze(
        self,
        institutional_flows: list[float],
        retail_flows: list[float],
        prices: Optional[list[float]] = None,
        symbol: str = "",
    ) -> SmartMoneyResult:
        """Detect smart money signals.

        Args:
            institutional_flows: Daily institutional net flows.
            retail_flows: Daily retail net flows.
            prices: Optional daily prices for divergence detection.
            symbol: Stock symbol.

        Returns:
            SmartMoneyResult with signal and conviction.
        """
        if not institutional_flows or not retail_flows:
            return self._empty_result(symbol)

        inst = np.array(institutional_flows, dtype=float)
        ret = np.array(retail_flows, dtype=float)

        # Trim to same length
        n = min(len(inst), len(ret))
        inst = inst[-n:]
        ret = ret[-n:]

        # Smart money score: weighted institutional vs retail
        inst_total = float(np.sum(inst))
        ret_total = float(np.sum(ret))

        score = self._compute_score(inst, ret)
        conviction = self._compute_conviction(inst, ret)
        signal = self._classify_signal(score)

        # Flow-price divergence
        divergence = 0.0
        is_contrarian = False
        if prices is not None and len(prices) >= 2:
            price_arr = np.array(prices[-n:], dtype=float)
            divergence = self._flow_price_divergence(inst, price_arr)
            is_contrarian = self._is_contrarian(score, price_arr)

        return SmartMoneyResult(
            symbol=symbol,
            institutional_flow=round(inst_total, 2),
            retail_flow=round(ret_total, 2),
            smart_money_score=round(score, 4),
            conviction=round(conviction, 4),
            signal=signal,
            flow_price_divergence=round(divergence, 4),
            is_contrarian=is_contrarian,
        )

    def _compute_score(
        self, inst: np.ndarray, ret: np.ndarray
    ) -> float:
        """Compute smart money score.

        Score = weighted combination of institutional vs retail flow
        direction. Range: -1 (strong distribution) to +1 (strong accumulation).
        """
        cfg = self.config

        # Normalize flows
        inst_norm = self._normalize(inst)
        ret_norm = self._normalize(ret)

        # Weighted average of recent flows
        n = len(inst_norm)
        weights = np.exp(np.linspace(-1, 0, n))
        weights /= weights.sum()

        inst_signal = float(np.sum(inst_norm * weights))
        ret_signal = float(np.sum(ret_norm * weights))

        # Smart money = institutional direction minus retail direction
        # Clamp to [-1, 1]
        raw = cfg.institutional_weight * inst_signal - cfg.retail_weight * ret_signal
        return float(np.clip(raw, -1.0, 1.0))

    def _compute_conviction(
        self, inst: np.ndarray, ret: np.ndarray
    ) -> float:
        """Compute conviction score (0 to 1).

        Higher conviction when:
        - Institutional flows are consistent in direction
        - Flow magnitude is large relative to average
        """
        if len(inst) < 2:
            return 0.0

        # Consistency: fraction of days with same sign as total
        inst_total = np.sum(inst)
        if inst_total == 0:
            return 0.0

        same_sign = np.sum(np.sign(inst) == np.sign(inst_total))
        consistency = same_sign / len(inst)

        # Magnitude: coefficient of variation (inverted)
        inst_abs = np.abs(inst)
        mean_abs = np.mean(inst_abs)
        if mean_abs == 0:
            return 0.0
        cv = np.std(inst_abs) / mean_abs
        magnitude = 1.0 / (1.0 + cv)

        # Divergence from retail
        if len(ret) > 0 and np.sum(np.abs(ret)) > 0:
            inst_dir = np.sign(inst_total)
            ret_dir = np.sign(np.sum(ret))
            divergence_bonus = 0.2 if inst_dir != ret_dir else 0.0
        else:
            divergence_bonus = 0.0

        conviction = 0.5 * consistency + 0.3 * magnitude + divergence_bonus
        return float(np.clip(conviction, 0.0, 1.0))

    def _classify_signal(self, score: float) -> SmartMoneySignal:
        """Classify signal from smart money score."""
        if score >= self.config.accumulation_threshold:
            return SmartMoneySignal.ACCUMULATION
        elif score <= self.config.distribution_threshold:
            return SmartMoneySignal.DISTRIBUTION
        return SmartMoneySignal.NEUTRAL

    def _flow_price_divergence(
        self, inst: np.ndarray, prices: np.ndarray
    ) -> float:
        """Detect divergence between institutional flow and price.

        Positive = bullish divergence (smart money buying, price falling).
        Negative = bearish divergence (smart money selling, price rising).
        """
        n = min(len(inst), len(prices))
        if n < 2:
            return 0.0

        inst = inst[-n:]
        prices = prices[-n:]

        # Normalize both to z-scores
        inst_z = self._zscore(inst)
        price_returns = np.diff(prices) / prices[:-1]
        price_z = self._zscore(price_returns)

        # Divergence = flow direction minus price direction
        # Use recent window
        w = min(self.config.divergence_lookback, len(inst_z), len(price_z))
        flow_dir = float(np.mean(inst_z[-w:]))
        price_dir = float(np.mean(price_z[-w:]))

        return flow_dir - price_dir

    def _is_contrarian(self, score: float, prices: np.ndarray) -> bool:
        """Check if smart money is going against recent price trend."""
        if len(prices) < 2:
            return False

        price_return = (prices[-1] - prices[0]) / prices[0]

        # Contrarian: buying into decline or selling into rally
        return (score > 0.2 and price_return < -0.02) or \
               (score < -0.2 and price_return > 0.02)

    def _normalize(self, arr: np.ndarray) -> np.ndarray:
        """Normalize array to [-1, 1] range."""
        max_abs = np.max(np.abs(arr))
        if max_abs == 0:
            return np.zeros_like(arr)
        return arr / max_abs

    def _zscore(self, arr: np.ndarray) -> np.ndarray:
        """Compute z-scores."""
        if len(arr) < 2:
            return np.zeros_like(arr)
        std = np.std(arr)
        if std == 0:
            return np.zeros_like(arr)
        return (arr - np.mean(arr)) / std

    def _empty_result(self, symbol: str) -> SmartMoneyResult:
        return SmartMoneyResult(
            symbol=symbol,
            institutional_flow=0.0,
            retail_flow=0.0,
            smart_money_score=0.0,
            conviction=0.0,
        )
