"""Block Trade Detector.

Identifies large block trades, classifies them by size,
and computes institutional flow metrics.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from src.orderflow.config import (
    BlockConfig,
    BlockSize,
    FlowSignal,
    DEFAULT_BLOCK_CONFIG,
)
from src.orderflow.models import BlockTrade, SmartMoneySignal

logger = logging.getLogger(__name__)


class BlockDetector:
    """Detects and classifies block trades."""

    def __init__(self, config: Optional[BlockConfig] = None) -> None:
        self.config = config or DEFAULT_BLOCK_CONFIG

    def detect_blocks(
        self,
        sizes: pd.Series,
        prices: pd.Series,
        sides: pd.Series,
        symbol: str = "",
    ) -> list[BlockTrade]:
        """Detect block trades from trade data.

        Args:
            sizes: Trade sizes (shares).
            prices: Trade prices.
            sides: Trade sides ("buy" or "sell").
            symbol: Asset symbol.

        Returns:
            List of BlockTrade for trades above medium threshold.
        """
        n = min(len(sizes), len(prices), len(sides))
        blocks: list[BlockTrade] = []

        for i in range(n):
            size = int(sizes.iloc[i])
            price = float(prices.iloc[i])
            side = str(sides.iloc[i])
            dollar_value = size * price

            block_size = self._classify_size(size, dollar_value)
            if block_size == BlockSize.SMALL:
                continue

            blocks.append(BlockTrade(
                symbol=symbol,
                size=size,
                price=round(price, 4),
                side=side,
                dollar_value=round(dollar_value, 0),
                block_size=block_size,
            ))

        return blocks

    def compute_smart_money(
        self,
        blocks: list[BlockTrade],
        total_volume: float = 0.0,
        symbol: str = "",
    ) -> SmartMoneySignal:
        """Compute smart money signal from block trades.

        Args:
            blocks: List of detected block trades.
            total_volume: Total market volume for block ratio.
            symbol: Asset symbol.

        Returns:
            SmartMoneySignal with institutional flow analysis.
        """
        if not blocks:
            return SmartMoneySignal(symbol=symbol)

        institutional = [b for b in blocks if b.is_institutional]
        inst_buy_vol = sum(b.size for b in institutional if b.side == "buy")
        inst_sell_vol = sum(b.size for b in institutional if b.side == "sell")
        inst_total = inst_buy_vol + inst_sell_vol
        inst_net = inst_buy_vol - inst_sell_vol

        inst_buy_pct = (inst_buy_vol / inst_total * 100) if inst_total > 0 else 50.0

        block_volume = sum(b.size for b in blocks)
        block_ratio = block_volume / total_volume if total_volume > 0 else 0.0

        # Signal from institutional direction
        signal, confidence = self._compute_signal(inst_buy_pct, block_ratio, len(institutional))

        return SmartMoneySignal(
            symbol=symbol,
            signal=signal,
            confidence=round(confidence, 2),
            block_ratio=round(block_ratio, 3),
            institutional_net_flow=round(inst_net, 0),
            institutional_buy_pct=round(inst_buy_pct, 1),
        )

    def _classify_size(self, size: int, dollar_value: float) -> BlockSize:
        """Classify trade by size."""
        if size >= self.config.institutional_threshold or dollar_value >= self.config.institutional_dollar_threshold:
            return BlockSize.INSTITUTIONAL
        elif size >= self.config.large_threshold:
            return BlockSize.LARGE
        elif size >= self.config.medium_threshold:
            return BlockSize.MEDIUM
        else:
            return BlockSize.SMALL

    def _compute_signal(
        self,
        inst_buy_pct: float,
        block_ratio: float,
        n_institutional: int,
    ) -> tuple[FlowSignal, float]:
        """Compute signal from institutional metrics."""
        if n_institutional == 0:
            return FlowSignal.NEUTRAL, 0.0

        # Direction from institutional buy %
        if inst_buy_pct >= 70:
            signal = FlowSignal.STRONG_BUY
        elif inst_buy_pct >= 55:
            signal = FlowSignal.BUY
        elif inst_buy_pct <= 30:
            signal = FlowSignal.STRONG_SELL
        elif inst_buy_pct <= 45:
            signal = FlowSignal.SELL
        else:
            signal = FlowSignal.NEUTRAL

        # Confidence from block ratio and count
        confidence = min(1.0, block_ratio * 2 + min(n_institutional, 10) / 20)
        return signal, confidence
