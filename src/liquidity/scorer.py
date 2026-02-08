"""Liquidity scoring engine."""

from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict
import math

from src.liquidity.config import (
    LiquidityTier,
    TIER_THRESHOLDS,
    LiquidityConfig,
    DEFAULT_LIQUIDITY_CONFIG,
)
from src.liquidity.models import LiquidityScore


class LiquidityScorer:
    """Multi-factor liquidity scoring."""

    def __init__(self, config: LiquidityConfig = DEFAULT_LIQUIDITY_CONFIG):
        self.config = config
        # symbol -> list of scores
        self._history: dict[str, list[LiquidityScore]] = defaultdict(list)

    def score(
        self,
        symbol: str,
        avg_daily_volume: int,
        avg_spread_bps: float,
        market_cap: Optional[int] = None,
        volatility: Optional[float] = None,
        order_book_depth: Optional[int] = None,
        turnover_ratio: Optional[float] = None,
    ) -> LiquidityScore:
        """Calculate composite liquidity score."""
        volume_score = self._score_volume(avg_daily_volume)
        spread_score = self._score_spread(avg_spread_bps)
        depth_score = self._score_depth(order_book_depth, avg_daily_volume)
        volatility_score = self._score_volatility(volatility)

        # Weighted composite
        composite = (
            volume_score * self.config.volume_weight +
            spread_score * self.config.spread_weight +
            depth_score * self.config.depth_weight +
            volatility_score * self.config.volatility_weight
        )

        composite = max(0, min(100, composite))
        tier = self._classify_tier(composite)

        score = LiquidityScore(
            symbol=symbol,
            composite_score=composite,
            volume_score=volume_score,
            spread_score=spread_score,
            depth_score=depth_score,
            volatility_score=volatility_score,
            turnover_ratio=turnover_ratio,
            avg_daily_volume=avg_daily_volume,
            avg_spread_bps=avg_spread_bps,
            market_cap=market_cap,
            liquidity_tier=tier,
        )

        self._history[symbol].append(score)
        return score

    def _score_volume(self, avg_daily_volume: int) -> float:
        """Score based on average daily volume (0-100)."""
        if avg_daily_volume <= 0:
            return 0.0

        high = self.config.high_volume_threshold
        low = self.config.low_volume_threshold

        if avg_daily_volume >= high:
            return 100.0
        elif avg_daily_volume <= low:
            return max(0, (avg_daily_volume / low) * 20)
        else:
            # Log scale between low and high
            log_vol = math.log10(avg_daily_volume)
            log_low = math.log10(low)
            log_high = math.log10(high)
            return 20 + (log_vol - log_low) / (log_high - log_low) * 80

    def _score_spread(self, avg_spread_bps: float) -> float:
        """Score based on bid-ask spread (0-100, lower spread = higher score)."""
        if avg_spread_bps <= 0:
            return 100.0

        tight = self.config.tight_spread_bps
        wide = self.config.wide_spread_bps

        if avg_spread_bps <= tight:
            return 100.0
        elif avg_spread_bps >= wide:
            return max(0, 100 - (avg_spread_bps - wide) * 2)
        else:
            return 100 - ((avg_spread_bps - tight) / (wide - tight)) * 80

    def _score_depth(self, order_book_depth: Optional[int], avg_daily_volume: int) -> float:
        """Score based on order book depth (0-100)."""
        if order_book_depth is not None:
            # Direct depth scoring
            if order_book_depth >= 1_000_000:
                return 100.0
            elif order_book_depth >= 100_000:
                return 60 + (order_book_depth - 100_000) / 900_000 * 40
            else:
                return max(0, order_book_depth / 100_000 * 60)

        # Estimate from volume
        return min(100, self._score_volume(avg_daily_volume) * 0.8)

    def _score_volatility(self, volatility: Optional[float]) -> float:
        """Score based on volatility (0-100, lower vol = higher score for liquidity)."""
        if volatility is None:
            return 50.0  # Neutral

        if volatility <= 0.10:
            return 100.0
        elif volatility <= 0.20:
            return 100 - (volatility - 0.10) / 0.10 * 30
        elif volatility <= 0.40:
            return 70 - (volatility - 0.20) / 0.20 * 40
        elif volatility <= 0.60:
            return 30 - (volatility - 0.40) / 0.20 * 20
        else:
            return max(0, 10 - (volatility - 0.60) * 20)

    def _classify_tier(self, composite_score: float) -> LiquidityTier:
        """Classify into liquidity tier based on composite score."""
        for tier_name, (low, high) in TIER_THRESHOLDS.items():
            if low <= composite_score < high:
                return LiquidityTier(tier_name)
        return LiquidityTier.HIGHLY_LIQUID if composite_score >= 100 else LiquidityTier.HIGHLY_ILLIQUID

    def score_portfolio(
        self,
        holdings: dict[str, dict],
    ) -> dict:
        """Score liquidity for a portfolio of holdings."""
        scores = {}
        total_value = sum(h.get("value", 0) for h in holdings.values())

        for symbol, holding in holdings.items():
            score = self.score(
                symbol=symbol,
                avg_daily_volume=holding.get("avg_daily_volume", 0),
                avg_spread_bps=holding.get("avg_spread_bps", 10.0),
                market_cap=holding.get("market_cap"),
                volatility=holding.get("volatility"),
            )
            scores[symbol] = score

        # Portfolio-level metrics
        if scores and total_value > 0:
            weighted_score = sum(
                s.composite_score * holdings[sym].get("value", 0) / total_value
                for sym, s in scores.items()
            )
        else:
            weighted_score = 0

        tier_counts: dict[str, int] = defaultdict(int)
        for s in scores.values():
            tier_counts[s.liquidity_tier.value] += 1

        return {
            "symbol_scores": {sym: s.to_dict() for sym, s in scores.items()},
            "portfolio_score": weighted_score,
            "portfolio_tier": self._classify_tier(weighted_score).value,
            "tier_distribution": dict(tier_counts),
            "illiquid_holdings": [
                sym for sym, s in scores.items()
                if s.composite_score < 40
            ],
        }

    def get_score_history(self, symbol: str, limit: int = 50) -> list[LiquidityScore]:
        """Get score history for a symbol."""
        return self._history.get(symbol, [])[-limit:]

    def compare_symbols(self, symbols: list[str]) -> list[LiquidityScore]:
        """Get latest scores for comparison."""
        result = []
        for symbol in symbols:
            history = self._history.get(symbol, [])
            if history:
                result.append(history[-1])
        return sorted(result, key=lambda s: s.composite_score, reverse=True)
