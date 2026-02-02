"""Dark Print Analysis.

Classifies dark pool prints by type, analyzes size
distributions, and measures price improvement.
"""

import logging
from typing import Optional

import numpy as np

from src.darkpool.config import PrintConfig, PrintType, DEFAULT_PRINT_CONFIG
from src.darkpool.models import DarkPrint, PrintSummary

logger = logging.getLogger(__name__)


class PrintAnalyzer:
    """Analyzes dark pool print characteristics."""

    def __init__(self, config: Optional[PrintConfig] = None) -> None:
        self.config = config or DEFAULT_PRINT_CONFIG

    def classify(self, print_: DarkPrint) -> PrintType:
        """Classify a single dark print.

        Args:
            print_: Dark pool print to classify.

        Returns:
            PrintType classification.
        """
        size = print_.size

        # Block: large size
        if size >= self.config.block_threshold:
            return PrintType.BLOCK

        # Retail: very small size
        if size <= self.config.retail_max_size:
            return PrintType.RETAIL

        # Midpoint: price at or very near NBBO midpoint
        if print_.nbbo_bid > 0 and print_.nbbo_ask > 0:
            mid = (print_.nbbo_bid + print_.nbbo_ask) / 2
            if mid > 0:
                distance = abs(print_.price - mid) / mid
                if distance <= self.config.midpoint_tolerance:
                    return PrintType.MIDPOINT

        # Institutional: mid-size, likely institutional
        if size >= self.config.retail_max_size * 5:
            return PrintType.INSTITUTIONAL

        return PrintType.UNKNOWN

    def classify_all(self, prints: list[DarkPrint]) -> list[DarkPrint]:
        """Classify all prints and update their type."""
        for p in prints:
            p.print_type = self.classify(p)
        return prints

    def analyze(
        self, prints: list[DarkPrint], symbol: str = ""
    ) -> PrintSummary:
        """Full print analysis.

        Args:
            prints: List of dark prints.
            symbol: Stock symbol.

        Returns:
            PrintSummary with aggregated metrics.
        """
        if len(prints) < self.config.min_prints:
            return self._empty_summary(symbol)

        # Classify all
        self.classify_all(prints)

        sizes = np.array([p.size for p in prints])
        notionals = np.array([p.notional for p in prints])
        improvements = np.array([p.price_improvement for p in prints])

        # Type distribution
        type_counts: dict[str, int] = {}
        block_count = 0
        block_volume = 0.0
        retail_count = 0
        midpoint_count = 0

        for p in prints:
            t = p.print_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
            if p.print_type == PrintType.BLOCK:
                block_count += 1
                block_volume += p.size
            elif p.print_type == PrintType.RETAIL:
                retail_count += 1
            elif p.print_type == PrintType.MIDPOINT:
                midpoint_count += 1

        return PrintSummary(
            symbol=symbol,
            total_prints=len(prints),
            total_volume=round(float(np.sum(sizes)), 2),
            total_notional=round(float(np.sum(notionals)), 2),
            avg_size=round(float(np.mean(sizes)), 2),
            avg_price_improvement=round(float(np.mean(improvements)), 2),
            block_count=block_count,
            block_volume=round(block_volume, 2),
            retail_count=retail_count,
            midpoint_count=midpoint_count,
            type_distribution=type_counts,
        )

    def _empty_summary(self, symbol: str) -> PrintSummary:
        return PrintSummary(
            symbol=symbol,
            total_prints=0,
            total_volume=0.0,
            total_notional=0.0,
            avg_size=0.0,
            avg_price_improvement=0.0,
        )
