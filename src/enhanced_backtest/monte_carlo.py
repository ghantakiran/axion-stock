"""Monte Carlo Simulator — path sampling for robust backtest analysis.

Generates thousands of random permutations of trade sequences to
estimate the distribution of possible outcomes, giving confidence
intervals rather than point estimates.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo simulation.

    Attributes:
        num_simulations: Number of random paths to generate.
        confidence_levels: Confidence levels for interval estimation.
        shuffle_trades: Whether to shuffle trade order.
        resample_with_replacement: Use bootstrap resampling.
        random_seed: Seed for reproducibility (None = random).
    """

    num_simulations: int = 1000
    confidence_levels: list[float] = field(
        default_factory=lambda: [0.05, 0.25, 0.50, 0.75, 0.95]
    )
    shuffle_trades: bool = True
    resample_with_replacement: bool = True
    random_seed: int | None = None


@dataclass
class PathStatistics:
    """Statistics for a single simulated equity path.

    Attributes:
        final_equity: Ending equity.
        max_drawdown_pct: Maximum drawdown percentage.
        total_return_pct: Total return percentage.
        sharpe_ratio: Annualized Sharpe ratio.
        max_equity: Peak equity reached.
        min_equity: Lowest equity point.
    """

    final_equity: float = 0.0
    max_drawdown_pct: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_equity: float = 0.0
    min_equity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_equity": round(self.final_equity, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "max_equity": round(self.max_equity, 2),
            "min_equity": round(self.min_equity, 2),
        }


@dataclass
class MonteCarloResult:
    """Aggregated result from Monte Carlo simulation.

    Attributes:
        num_simulations: Paths generated.
        initial_equity: Starting equity.
        percentiles: Dict of metric → percentile values.
        median_final_equity: 50th percentile final equity.
        worst_case_drawdown: 95th percentile max drawdown.
        probability_of_profit: Fraction of paths that ended profitable.
        probability_of_ruin: Fraction of paths with >50% drawdown.
        confidence_interval_return: (low, high) return at 90% confidence.
        all_paths: Optional list of all path statistics.
    """

    num_simulations: int = 0
    initial_equity: float = 100_000.0
    percentiles: dict[str, dict[str, float]] = field(default_factory=dict)
    median_final_equity: float = 0.0
    worst_case_drawdown: float = 0.0
    probability_of_profit: float = 0.0
    probability_of_ruin: float = 0.0
    confidence_interval_return: tuple[float, float] = (0.0, 0.0)
    all_paths: list[PathStatistics] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_simulations": self.num_simulations,
            "initial_equity": self.initial_equity,
            "percentiles": self.percentiles,
            "median_final_equity": round(self.median_final_equity, 2),
            "worst_case_drawdown": round(self.worst_case_drawdown, 2),
            "probability_of_profit": round(self.probability_of_profit, 3),
            "probability_of_ruin": round(self.probability_of_ruin, 3),
            "confidence_interval_return": (
                round(self.confidence_interval_return[0], 2),
                round(self.confidence_interval_return[1], 2),
            ),
        }


class MonteCarloSimulator:
    """Monte Carlo path simulator for backtesting robustness.

    Takes a sequence of trade P&Ls and generates thousands of
    random permutations to estimate the distribution of outcomes.

    Args:
        config: MonteCarloConfig with simulation parameters.

    Example:
        sim = MonteCarloSimulator()
        result = sim.simulate(
            trade_pnls=[150, -50, 200, -100, 75, ...],
            initial_equity=100_000
        )
        print(f"Probability of profit: {result.probability_of_profit:.1%}")
        print(f"Median final equity: ${result.median_final_equity:,.0f}")
    """

    def __init__(self, config: MonteCarloConfig | None = None) -> None:
        self.config = config or MonteCarloConfig()

    def simulate(
        self,
        trade_pnls: list[float],
        initial_equity: float = 100_000.0,
        include_all_paths: bool = False,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation on trade P&L sequence.

        Args:
            trade_pnls: List of trade P&Ls (ordered by execution time).
            initial_equity: Starting account equity.
            include_all_paths: Whether to include all path stats in result.

        Returns:
            MonteCarloResult with distribution statistics.
        """
        if not trade_pnls:
            return MonteCarloResult(initial_equity=initial_equity)

        rng = random.Random(self.config.random_seed)
        paths: list[PathStatistics] = []

        for _ in range(self.config.num_simulations):
            # Generate a random trade sequence
            if self.config.resample_with_replacement:
                # Bootstrap: sample with replacement
                sampled = rng.choices(trade_pnls, k=len(trade_pnls))
            elif self.config.shuffle_trades:
                # Permutation: shuffle without replacement
                sampled = list(trade_pnls)
                rng.shuffle(sampled)
            else:
                sampled = list(trade_pnls)

            # Simulate equity curve
            stats = self._simulate_path(sampled, initial_equity)
            paths.append(stats)

        return self._aggregate(paths, initial_equity, include_all_paths)

    def _simulate_path(
        self, pnls: list[float], initial_equity: float
    ) -> PathStatistics:
        """Simulate a single equity path."""
        equity = initial_equity
        peak = initial_equity
        min_equity = initial_equity
        max_drawdown = 0.0
        returns = []

        for pnl in pnls:
            prev = equity
            equity += pnl
            if prev > 0:
                returns.append(pnl / prev)

            if equity > peak:
                peak = equity
            if equity < min_equity:
                min_equity = equity

            drawdown = (peak - equity) / max(peak, 1) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        total_return = (equity - initial_equity) / initial_equity * 100

        # Sharpe ratio
        sharpe = 0.0
        if returns:
            mean = sum(returns) / len(returns)
            var = sum((r - mean) ** 2 for r in returns) / max(len(returns), 1)
            std = math.sqrt(var) if var > 0 else 0.0
            if std > 0:
                sharpe = (mean / std) * math.sqrt(252)

        return PathStatistics(
            final_equity=equity,
            max_drawdown_pct=max_drawdown,
            total_return_pct=total_return,
            sharpe_ratio=sharpe,
            max_equity=peak,
            min_equity=min_equity,
        )

    def _aggregate(
        self,
        paths: list[PathStatistics],
        initial_equity: float,
        include_all: bool,
    ) -> MonteCarloResult:
        """Aggregate path statistics into summary result."""
        n = len(paths)
        if n == 0:
            return MonteCarloResult(initial_equity=initial_equity)

        finals = sorted(p.final_equity for p in paths)
        drawdowns = sorted(p.max_drawdown_pct for p in paths)
        returns = sorted(p.total_return_pct for p in paths)

        # Percentiles
        percentiles = {}
        for level in self.config.confidence_levels:
            idx = min(int(n * level), n - 1)
            percentiles[f"p{int(level*100)}"] = {
                "final_equity": finals[idx],
                "max_drawdown": drawdowns[idx],
                "return_pct": returns[idx],
            }

        # Key statistics
        median_idx = n // 2
        profitable = sum(1 for p in paths if p.final_equity > initial_equity)
        ruined = sum(1 for p in paths if p.max_drawdown_pct > 50)

        # 90% confidence interval on returns
        ci_low_idx = min(int(n * 0.05), n - 1)
        ci_high_idx = min(int(n * 0.95), n - 1)

        return MonteCarloResult(
            num_simulations=n,
            initial_equity=initial_equity,
            percentiles=percentiles,
            median_final_equity=finals[median_idx],
            worst_case_drawdown=drawdowns[min(int(n * 0.95), n - 1)],
            probability_of_profit=profitable / n,
            probability_of_ruin=ruined / n,
            confidence_interval_return=(returns[ci_low_idx], returns[ci_high_idx]),
            all_paths=paths if include_all else None,
        )
