"""Correlation Guard — blocks trades that would create correlated clusters.

Computes return-based correlation matrix for open positions and
rejects new trades that are too correlated with existing holdings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class CorrelationConfig:
    """Configuration for the correlation guard.

    Attributes:
        max_pairwise_correlation: Block new trade if correlated > this with any holding.
        max_cluster_size: Max positions in a correlated cluster.
        lookback_days: Days of return history for correlation calculation.
        min_data_points: Minimum data points needed for valid correlation.
        cluster_threshold: Correlation threshold to define a cluster.
    """

    max_pairwise_correlation: float = 0.80
    max_cluster_size: int = 4
    lookback_days: int = 60
    min_data_points: int = 20
    cluster_threshold: float = 0.70


@dataclass
class CorrelationMatrix:
    """Result of a correlation computation.

    Attributes:
        tickers: Ordered list of tickers.
        matrix: NxN correlation values (list of lists for JSON safety).
        clusters: Groups of highly correlated tickers.
        max_correlation: Highest pairwise correlation found.
        computed_at: Timestamp of computation.
    """

    tickers: list[str] = field(default_factory=list)
    matrix: list[list[float]] = field(default_factory=list)
    clusters: list[list[str]] = field(default_factory=list)
    max_correlation: float = 0.0
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_correlation(self, ticker_a: str, ticker_b: str) -> Optional[float]:
        """Get pairwise correlation between two tickers."""
        if ticker_a not in self.tickers or ticker_b not in self.tickers:
            return None
        i = self.tickers.index(ticker_a)
        j = self.tickers.index(ticker_b)
        return self.matrix[i][j]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tickers": self.tickers,
            "matrix": [[round(v, 3) for v in row] for row in self.matrix],
            "clusters": self.clusters,
            "max_correlation": round(self.max_correlation, 3),
            "computed_at": self.computed_at.isoformat(),
        }


class CorrelationGuard:
    """Guards against over-concentration in correlated positions.

    Computes return-based correlations from historical prices and
    blocks new trades that would exceed correlation thresholds.

    Args:
        config: CorrelationConfig with thresholds.

    Example:
        guard = CorrelationGuard()
        matrix = guard.compute_matrix(returns_by_ticker)
        approved, reason = guard.check_new_trade("MSFT", matrix, ["AAPL", "GOOGL"])
    """

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        self.config = config or CorrelationConfig()

    def compute_matrix(
        self, returns: dict[str, list[float]]
    ) -> CorrelationMatrix:
        """Compute correlation matrix from daily returns.

        Args:
            returns: Dict mapping ticker → list of daily returns.
                     All lists should be the same length.

        Returns:
            CorrelationMatrix with pairwise correlations and clusters.
        """
        tickers = sorted(returns.keys())
        n = len(tickers)

        if n == 0:
            return CorrelationMatrix()

        # Build NxN matrix
        matrix = [[0.0] * n for _ in range(n)]
        max_corr = 0.0

        for i in range(n):
            matrix[i][i] = 1.0  # Self-correlation
            for j in range(i + 1, n):
                corr = self._pearson(returns[tickers[i]], returns[tickers[j]])
                matrix[i][j] = corr
                matrix[j][i] = corr
                if abs(corr) > abs(max_corr):
                    max_corr = corr

        # Find clusters
        clusters = self._find_clusters(tickers, matrix)

        return CorrelationMatrix(
            tickers=tickers,
            matrix=matrix,
            clusters=clusters,
            max_correlation=max_corr,
        )

    def check_new_trade(
        self,
        new_ticker: str,
        corr_matrix: CorrelationMatrix,
        current_holdings: list[str],
    ) -> tuple[bool, str]:
        """Check if adding new_ticker would violate correlation constraints.

        Args:
            new_ticker: Ticker to add.
            corr_matrix: Pre-computed correlation matrix.
            current_holdings: List of currently held tickers.

        Returns:
            Tuple of (approved, reason).
        """
        if not current_holdings or new_ticker not in corr_matrix.tickers:
            return True, "approved"

        # Check pairwise correlation with each existing holding
        for holding in current_holdings:
            corr = corr_matrix.get_correlation(new_ticker, holding)
            if corr is not None and abs(corr) > self.config.max_pairwise_correlation:
                return False, (
                    f"Correlation {new_ticker}↔{holding} = {corr:.2f} "
                    f"exceeds limit {self.config.max_pairwise_correlation}"
                )

        # Check cluster size
        for cluster in corr_matrix.clusters:
            if new_ticker in cluster:
                # Count how many current holdings are in this cluster
                overlap = sum(1 for h in current_holdings if h in cluster)
                if overlap >= self.config.max_cluster_size - 1:
                    return False, (
                        f"Adding {new_ticker} would create cluster of "
                        f"{overlap + 1} (limit {self.config.max_cluster_size}): "
                        f"{[h for h in current_holdings if h in cluster]}"
                    )

        return True, "approved"

    def get_portfolio_concentration_score(
        self, corr_matrix: CorrelationMatrix, holdings: list[str]
    ) -> float:
        """Score 0-100 measuring how concentrated the portfolio is.

        100 = all positions perfectly correlated (maximum risk)
        0 = all positions uncorrelated (maximum diversification)
        """
        if len(holdings) < 2:
            return 0.0

        total_corr = 0.0
        pairs = 0
        for i, t1 in enumerate(holdings):
            for t2 in holdings[i + 1:]:
                corr = corr_matrix.get_correlation(t1, t2)
                if corr is not None:
                    total_corr += abs(corr)
                    pairs += 1

        if pairs == 0:
            return 0.0

        avg_corr = total_corr / pairs
        return min(100.0, avg_corr * 100.0)

    # ── Internal helpers ─────────────────────────────────────────────

    def _pearson(self, x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation between two return series."""
        n = min(len(x), len(y))
        if n < self.config.min_data_points:
            return 0.0

        x = x[:n]
        y = y[:n]
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)

        denom = math.sqrt(var_x * var_y)
        if denom < 1e-12:
            return 0.0

        return cov / denom

    def _find_clusters(
        self, tickers: list[str], matrix: list[list[float]]
    ) -> list[list[str]]:
        """Find clusters of correlated tickers using simple greedy approach."""
        n = len(tickers)
        visited = set()
        clusters = []

        for i in range(n):
            if i in visited:
                continue
            cluster = [tickers[i]]
            visited.add(i)
            for j in range(i + 1, n):
                if j in visited:
                    continue
                if abs(matrix[i][j]) >= self.config.cluster_threshold:
                    cluster.append(tickers[j])
                    visited.add(j)
            if len(cluster) > 1:
                clusters.append(cluster)

        return clusters
