"""Fund Overlap Analysis.

Computes pairwise fund portfolio similarity,
identifies most-crowded names, and tracks overlap trends.
"""

import logging
from typing import Optional

import numpy as np

from src.crowding.config import OverlapConfig, OverlapMethod, DEFAULT_OVERLAP_CONFIG
from src.crowding.models import FundOverlap, CrowdedName

logger = logging.getLogger(__name__)


class OverlapAnalyzer:
    """Analyzes hedge fund portfolio overlap."""

    def __init__(self, config: Optional[OverlapConfig] = None) -> None:
        self.config = config or DEFAULT_OVERLAP_CONFIG

    def compute_overlap(
        self,
        portfolio_a: dict[str, float],
        portfolio_b: dict[str, float],
        fund_a: str = "Fund A",
        fund_b: str = "Fund B",
    ) -> FundOverlap:
        """Compute overlap between two fund portfolios.

        Args:
            portfolio_a: Dict of symbol -> weight for fund A.
            portfolio_b: Dict of symbol -> weight for fund B.
            fund_a: Fund A name.
            fund_b: Fund B name.

        Returns:
            FundOverlap with similarity score.
        """
        set_a = set(portfolio_a.keys())
        set_b = set(portfolio_b.keys())
        shared = set_a & set_b

        if self.config.method == OverlapMethod.JACCARD:
            score = self._jaccard(set_a, set_b)
        else:
            score = self._cosine(portfolio_a, portfolio_b)

        top_shared = sorted(
            shared,
            key=lambda s: portfolio_a.get(s, 0) + portfolio_b.get(s, 0),
            reverse=True,
        )[:10]

        return FundOverlap(
            fund_a=fund_a,
            fund_b=fund_b,
            overlap_score=round(score, 4),
            shared_positions=len(shared),
            total_positions_a=len(set_a),
            total_positions_b=len(set_b),
            top_shared=top_shared,
        )

    def compute_all_overlaps(
        self,
        portfolios: dict[str, dict[str, float]],
    ) -> list[FundOverlap]:
        """Compute pairwise overlaps for all fund pairs.

        Args:
            portfolios: Dict of fund_name -> {symbol: weight}.

        Returns:
            List of FundOverlap for all pairs.
        """
        funds = list(portfolios.keys())
        results = []

        for i in range(len(funds)):
            for j in range(i + 1, len(funds)):
                overlap = self.compute_overlap(
                    portfolios[funds[i]], portfolios[funds[j]],
                    funds[i], funds[j],
                )
                results.append(overlap)

        results.sort(key=lambda o: o.overlap_score, reverse=True)
        return results

    def find_crowded_names(
        self,
        portfolios: dict[str, dict[str, float]],
    ) -> list[CrowdedName]:
        """Find most-crowded names across all funds.

        Args:
            portfolios: Dict of fund_name -> {symbol: weight}.

        Returns:
            Ranked list of CrowdedName.
        """
        n_funds = len(portfolios)
        if n_funds == 0:
            return []

        # Count holdings per symbol
        symbol_data: dict[str, dict] = {}
        for fund_name, holdings in portfolios.items():
            for symbol, weight in holdings.items():
                if symbol not in symbol_data:
                    symbol_data[symbol] = {"funds": 0, "total_weight": 0.0, "weights": []}
                symbol_data[symbol]["funds"] += 1
                symbol_data[symbol]["total_weight"] += weight
                symbol_data[symbol]["weights"].append(weight)

        results = []
        for symbol, data in symbol_data.items():
            breadth = data["funds"] / n_funds  # fraction of funds holding
            avg_weight = data["total_weight"] / data["funds"]
            # Depth: how large positions are (normalize by 5% typical position)
            depth = min(avg_weight / 5.0, 1.0)

            results.append(CrowdedName(
                symbol=symbol,
                n_funds=data["funds"],
                total_ownership_pct=round(data["total_weight"], 2),
                avg_position_size=round(avg_weight, 2),
                breadth=round(breadth, 4),
                depth=round(depth, 4),
            ))

        results.sort(key=lambda c: c.crowding_intensity, reverse=True)
        return results[:self.config.top_crowded_count]

    def _jaccard(self, set_a: set, set_b: set) -> float:
        """Jaccard similarity: |A ∩ B| / |A ∪ B|."""
        union = set_a | set_b
        if not union:
            return 0.0
        return len(set_a & set_b) / len(union)

    def _cosine(
        self,
        portfolio_a: dict[str, float],
        portfolio_b: dict[str, float],
    ) -> float:
        """Cosine similarity on portfolio weight vectors."""
        all_symbols = set(portfolio_a.keys()) | set(portfolio_b.keys())
        if not all_symbols:
            return 0.0

        vec_a = np.array([portfolio_a.get(s, 0) for s in all_symbols])
        vec_b = np.array([portfolio_b.get(s, 0) for s in all_symbols])

        dot = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))
