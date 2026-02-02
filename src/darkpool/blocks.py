"""Dark Pool Block Detection.

Identifies institutional block trades, clusters them,
infers direction, and computes ADV-relative sizing.
"""

import logging
from typing import Optional

import numpy as np

from src.darkpool.config import BlockConfig, BlockDirection, DEFAULT_BLOCK_CONFIG
from src.darkpool.models import DarkPrint, DarkBlock

logger = logging.getLogger(__name__)


class BlockDetector:
    """Detects and analyzes dark pool block trades."""

    def __init__(self, config: Optional[BlockConfig] = None) -> None:
        self.config = config or DEFAULT_BLOCK_CONFIG

    def detect(
        self,
        prints: list[DarkPrint],
        adv: float = 0.0,
        symbol: str = "",
    ) -> list[DarkBlock]:
        """Detect block trades from dark prints.

        Args:
            prints: List of dark prints.
            adv: Average daily volume for ADV ratio.
            symbol: Stock symbol.

        Returns:
            List of detected blocks.
        """
        blocks: list[DarkBlock] = []

        for p in prints:
            notional = p.price * p.size
            if p.size < self.config.min_block_size:
                continue
            if notional < self.config.min_block_value:
                continue

            adv_ratio = p.size / adv if adv > 0 else 0.0
            direction = self._infer_direction(p)

            block = DarkBlock(
                symbol=symbol or p.symbol,
                size=p.size,
                notional=round(notional, 2),
                price=p.price,
                direction=direction,
                adv_ratio=round(adv_ratio, 6),
                venue=p.venue,
                timestamp=p.timestamp,
            )
            blocks.append(block)

        # Assign cluster IDs
        self._cluster_blocks(blocks)

        return blocks

    def _infer_direction(self, print_: DarkPrint) -> BlockDirection:
        """Infer block direction from price relative to NBBO.

        Price near ask -> buyer initiated.
        Price near bid -> seller initiated.
        """
        if print_.nbbo_bid <= 0 or print_.nbbo_ask <= 0:
            return BlockDirection.UNKNOWN

        mid = (print_.nbbo_bid + print_.nbbo_ask) / 2
        if print_.price > mid:
            return BlockDirection.BUY
        elif print_.price < mid:
            return BlockDirection.SELL
        return BlockDirection.UNKNOWN

    def _cluster_blocks(self, blocks: list[DarkBlock]) -> None:
        """Group blocks into clusters by time proximity.

        Blocks within cluster_window seconds get same cluster_id.
        """
        if not blocks:
            return

        # Sort by timestamp
        blocks.sort(key=lambda b: b.timestamp)

        cluster_id = 1
        cluster_start = blocks[0].timestamp
        cluster_count = 1

        for i, block in enumerate(blocks):
            if block.timestamp - cluster_start <= self.config.cluster_window:
                cluster_count += 1
            else:
                # Assign cluster if enough blocks
                if cluster_count >= self.config.cluster_min_blocks:
                    for j in range(i - cluster_count, i):
                        if j >= 0:
                            blocks[j].cluster_id = cluster_id
                    cluster_id += 1
                cluster_start = block.timestamp
                cluster_count = 1

        # Handle last cluster
        if cluster_count >= self.config.cluster_min_blocks:
            for j in range(len(blocks) - cluster_count, len(blocks)):
                blocks[j].cluster_id = cluster_id

    def summarize_blocks(
        self, blocks: list[DarkBlock]
    ) -> dict:
        """Summarize detected blocks.

        Returns:
            Dict with block statistics.
        """
        if not blocks:
            return {
                "total_blocks": 0, "total_volume": 0,
                "total_notional": 0, "avg_size": 0,
                "buy_blocks": 0, "sell_blocks": 0,
                "clusters": 0, "significant_blocks": 0,
            }

        sizes = [b.size for b in blocks]
        buy_count = sum(1 for b in blocks if b.direction == BlockDirection.BUY)
        sell_count = sum(1 for b in blocks if b.direction == BlockDirection.SELL)
        cluster_ids = set(b.cluster_id for b in blocks if b.cluster_id > 0)
        significant = sum(1 for b in blocks if b.is_significant)

        return {
            "total_blocks": len(blocks),
            "total_volume": round(sum(sizes), 2),
            "total_notional": round(sum(b.notional for b in blocks), 2),
            "avg_size": round(float(np.mean(sizes)), 2),
            "buy_blocks": buy_count,
            "sell_blocks": sell_count,
            "clusters": len(cluster_ids),
            "significant_blocks": significant,
        }
