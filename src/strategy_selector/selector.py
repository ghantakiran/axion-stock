"""Strategy Selector — dynamic routing between EMA Cloud and Mean-Reversion.

Routes signals to the appropriate strategy based on market regime and
ADX trend strength. When EMA Cloud is selected, further refines to a
specific Ripster sub-strategy (pullback_to_cloud, trend_day, session_scalp,
or generic ema_cloud). Tracks strategy performance for A/B comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.strategy_selector.adx_gate import ADXConfig, ADXGate, TrendStrength
from src.strategy_selector.mean_reversion import (
    MeanReversionConfig,
    MeanReversionSignal,
    MeanReversionStrategy,
)


@dataclass
class SelectorConfig:
    """Configuration for the strategy selector.

    Attributes:
        adx_config: ADX gate configuration.
        mr_config: Mean-reversion strategy configuration.
        force_strategy: Force a specific strategy (None = auto-select).
        blend_mode: Whether to blend both strategies in transition zones.
        blend_ema_weight: EMA Cloud weight when blending (0-1).
        regime_override: Map regime → forced strategy.
    """

    adx_config: ADXConfig = field(default_factory=ADXConfig)
    mr_config: MeanReversionConfig = field(default_factory=MeanReversionConfig)
    force_strategy: Optional[str] = None
    blend_mode: bool = False
    blend_ema_weight: float = 0.6
    regime_override: dict[str, str] = field(default_factory=lambda: {
        "crisis": "mean_reversion",
    })


@dataclass
class StrategyChoice:
    """Result of strategy selection for a ticker.

    Attributes:
        ticker: Symbol analyzed.
        selected_strategy: Which strategy was chosen.
        trend_strength: ADX trend strength classification.
        adx_value: Raw ADX value.
        regime: Current market regime.
        mean_reversion_signal: MR signal if MR was selected/computed.
        confidence: Confidence in strategy selection 0-100.
        reasoning: Why this strategy was selected.
        timestamp: When the selection was made.
    """

    ticker: str = ""
    selected_strategy: str = "ema_cloud"
    trend_strength: TrendStrength = TrendStrength.NO_TREND
    adx_value: float = 0.0
    regime: str = "sideways"
    mean_reversion_signal: Optional[MeanReversionSignal] = None
    confidence: float = 50.0
    reasoning: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "selected_strategy": self.selected_strategy,
            "trend_strength": self.trend_strength.value,
            "adx_value": round(self.adx_value, 1),
            "regime": self.regime,
            "mean_reversion_signal": (
                self.mean_reversion_signal.to_dict()
                if self.mean_reversion_signal else None
            ),
            "confidence": round(self.confidence, 1),
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
        }


class StrategySelector:
    """Routes between EMA Cloud and Mean-Reversion based on conditions.

    Decision logic:
      1. Check for regime override (crisis → always mean-reversion)
      2. Check for forced strategy configuration
      3. Compute ADX to measure trend strength
      4. Route to appropriate strategy

    Tracks per-strategy hit rates for walk-forward A/B comparison.

    Args:
        config: SelectorConfig with routing rules.

    Example:
        selector = StrategySelector()
        choice = selector.select(
            ticker="AAPL",
            highs=[...], lows=[...], closes=[...],
            regime="bull"
        )
        print(f"Use {choice.selected_strategy} for AAPL (ADX={choice.adx_value:.1f})")
    """

    def __init__(self, config: SelectorConfig | None = None) -> None:
        self.config = config or SelectorConfig()
        self._adx_gate = ADXGate(self.config.adx_config)
        self._mr_strategy = MeanReversionStrategy(self.config.mr_config)

        # Ripster sub-strategies (lazy-loaded)
        self._ripster_strategies: dict = {}
        self._load_ripster_strategies()

        # Qullamaggie strategies (lazy-loaded)
        self._qullamaggie_strategies: dict = {}
        self._load_qullamaggie_strategies()

        # Performance tracking for A/B comparison
        self._strategy_stats: dict[str, dict[str, float]] = {
            "ema_cloud": {"signals": 0, "wins": 0, "total_pnl": 0.0},
            "mean_reversion": {"signals": 0, "wins": 0, "total_pnl": 0.0},
            "pullback_to_cloud": {"signals": 0, "wins": 0, "total_pnl": 0.0},
            "trend_day": {"signals": 0, "wins": 0, "total_pnl": 0.0},
            "session_scalp": {"signals": 0, "wins": 0, "total_pnl": 0.0},
            "qullamaggie_breakout": {"signals": 0, "wins": 0, "total_pnl": 0.0},
            "qullamaggie_ep": {"signals": 0, "wins": 0, "total_pnl": 0.0},
            "qullamaggie_parabolic_short": {"signals": 0, "wins": 0, "total_pnl": 0.0},
        }

    def _load_ripster_strategies(self) -> None:
        """Load Ripster sub-strategies for EMA Cloud refinement."""
        try:
            from src.strategies.pullback_strategy import PullbackToCloudStrategy
            from src.strategies.trend_day_strategy import TrendDayStrategy
            from src.strategies.session_scalp_strategy import SessionScalpStrategy
            self._ripster_strategies = {
                "pullback_to_cloud": PullbackToCloudStrategy(),
                "trend_day": TrendDayStrategy(),
                "session_scalp": SessionScalpStrategy(),
            }
        except ImportError:
            self._ripster_strategies = {}

    def _load_qullamaggie_strategies(self) -> None:
        """Load Qullamaggie strategies for momentum routing."""
        try:
            from src.qullamaggie.breakout_strategy import QullamaggieBreakoutStrategy
            from src.qullamaggie.episodic_pivot_strategy import EpisodicPivotStrategy
            from src.qullamaggie.parabolic_short_strategy import ParabolicShortStrategy
            self._qullamaggie_strategies = {
                "qullamaggie_breakout": QullamaggieBreakoutStrategy(),
                "qullamaggie_ep": EpisodicPivotStrategy(),
                "qullamaggie_parabolic_short": ParabolicShortStrategy(),
            }
        except ImportError:
            self._qullamaggie_strategies = {}

    def select(
        self,
        ticker: str,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        regime: str = "sideways",
        opens: list[float] | None = None,
        volumes: list[float] | None = None,
    ) -> StrategyChoice:
        """Select the best strategy for current market conditions.

        Args:
            ticker: Symbol to analyze.
            highs: High prices for ADX.
            lows: Low prices for ADX.
            closes: Close prices for all indicators.
            regime: Current market regime.
            opens: Open prices (optional, enables Ripster sub-strategy refinement).
            volumes: Volume data (optional, enables Ripster sub-strategy refinement).

        Returns:
            StrategyChoice with selected strategy and reasoning.
        """
        # 1. Regime override
        if regime in self.config.regime_override:
            forced = self.config.regime_override[regime]
            mr_signal = None
            if forced == "mean_reversion":
                mr_signal = self._mr_strategy.analyze(ticker, closes)
            return StrategyChoice(
                ticker=ticker,
                selected_strategy=forced,
                regime=regime,
                mean_reversion_signal=mr_signal,
                confidence=80.0,
                reasoning=f"Regime override: {regime} → {forced}",
            )

        # 2. Forced strategy
        if self.config.force_strategy:
            return StrategyChoice(
                ticker=ticker,
                selected_strategy=self.config.force_strategy,
                regime=regime,
                confidence=100.0,
                reasoning=f"Forced strategy: {self.config.force_strategy}",
            )

        # 3. ADX-based selection
        strategy_name, strength, adx = self._adx_gate.analyze_and_select(
            highs, lows, closes
        )

        mr_signal = None
        if strategy_name == "mean_reversion":
            mr_signal = self._mr_strategy.analyze(ticker, closes)

        # 3b. Try Qullamaggie strategies when strong trend + opens/volumes available
        if strategy_name == "ema_cloud" and opens and volumes and self._qullamaggie_strategies:
            q_name, q_conf = self._try_qullamaggie(
                ticker, opens, highs, lows, closes, volumes, strength, adx,
            )
            if q_name:
                return StrategyChoice(
                    ticker=ticker,
                    selected_strategy=q_name,
                    trend_strength=strength,
                    adx_value=adx,
                    regime=regime,
                    confidence=q_conf,
                    reasoning=f"{strength.value} (ADX={adx:.1f}) → {q_name}",
                )

        # 4. Refine EMA Cloud to specific Ripster sub-strategy
        if strategy_name == "ema_cloud" and opens and volumes:
            refined, refined_conf = self.refine_ema_strategy(
                ticker, opens, highs, lows, closes, volumes, strength,
            )
            if refined != "ema_cloud":
                return StrategyChoice(
                    ticker=ticker,
                    selected_strategy=refined,
                    trend_strength=strength,
                    adx_value=adx,
                    regime=regime,
                    confidence=refined_conf,
                    reasoning=f"{strength.value} (ADX={adx:.1f}) → {refined}",
                )

        # Compute confidence based on ADX clarity
        if strength == TrendStrength.STRONG_TREND:
            confidence = 90.0
            reasoning = f"Strong trend (ADX={adx:.1f}) → EMA Cloud"
        elif strength == TrendStrength.MODERATE_TREND:
            confidence = 70.0
            reasoning = f"Moderate trend (ADX={adx:.1f}) → EMA Cloud"
        elif strength == TrendStrength.WEAK_TREND:
            confidence = 55.0
            reasoning = f"Weak trend (ADX={adx:.1f}) → Mean-Reversion"
        else:
            confidence = 75.0
            reasoning = f"No trend (ADX={adx:.1f}) → Mean-Reversion"

        return StrategyChoice(
            ticker=ticker,
            selected_strategy=strategy_name,
            trend_strength=strength,
            adx_value=adx,
            regime=regime,
            mean_reversion_signal=mr_signal,
            confidence=confidence,
            reasoning=reasoning,
        )

    def refine_ema_strategy(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
        trend_strength: TrendStrength,
    ) -> tuple[str, float]:
        """Refine EMA Cloud selection to a specific Ripster sub-strategy.

        Tries each Ripster strategy in priority order. Returns the first
        one that produces a signal, or falls back to generic 'ema_cloud'.

        Priority:
          1. trend_day (highest conviction, rare — strong trends only)
          2. pullback_to_cloud (core entry pattern)
          3. session_scalp (session-aware routing)
          4. ema_cloud (fallback — use generic EMA signals)

        Returns:
            (strategy_name, confidence) tuple.
        """
        if not self._ripster_strategies:
            return "ema_cloud", 70.0

        # Trend day only in strong trends
        if trend_strength == TrendStrength.STRONG_TREND:
            td = self._ripster_strategies.get("trend_day")
            if td:
                try:
                    sig = td.analyze(ticker, opens, highs, lows, closes, volumes)
                    if sig:
                        return "trend_day", 90.0
                except Exception:
                    pass

        # Pullback-to-cloud in moderate+ trends
        if trend_strength in (TrendStrength.STRONG_TREND, TrendStrength.MODERATE_TREND):
            pb = self._ripster_strategies.get("pullback_to_cloud")
            if pb:
                try:
                    sig = pb.analyze(ticker, opens, highs, lows, closes, volumes)
                    if sig:
                        return "pullback_to_cloud", 80.0
                except Exception:
                    pass

        # Session scalp in any trending condition
        ss = self._ripster_strategies.get("session_scalp")
        if ss:
            try:
                sig = ss.analyze(ticker, opens, highs, lows, closes, volumes)
                if sig:
                    return "session_scalp", 65.0
            except Exception:
                pass

        return "ema_cloud", 70.0

    def _try_qullamaggie(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
        trend_strength: TrendStrength,
        adx: float,
    ) -> tuple[str | None, float]:
        """Try Qullamaggie strategies when ADX shows strong trend.

        Priority:
          1. qullamaggie_breakout (strong trend + consolidation detected)
          2. qullamaggie_ep (gap-up with volume)
          3. qullamaggie_parabolic_short (exhaustion after surge)

        Returns:
            (strategy_name, confidence) or (None, 0) if no signal.
        """
        # Breakout requires strong or moderate trend
        if trend_strength in (TrendStrength.STRONG_TREND, TrendStrength.MODERATE_TREND):
            bo = self._qullamaggie_strategies.get("qullamaggie_breakout")
            if bo:
                try:
                    sig = bo.analyze(ticker, opens, highs, lows, closes, volumes)
                    if sig:
                        return "qullamaggie_breakout", 85.0
                except Exception:
                    pass

        # EP can fire in any trending condition
        ep = self._qullamaggie_strategies.get("qullamaggie_ep")
        if ep:
            try:
                sig = ep.analyze(ticker, opens, highs, lows, closes, volumes)
                if sig:
                    return "qullamaggie_ep", 80.0
            except Exception:
                pass

        # Parabolic short — counter-trend, only when exhaustion detected
        ps = self._qullamaggie_strategies.get("qullamaggie_parabolic_short")
        if ps:
            try:
                sig = ps.analyze(ticker, opens, highs, lows, closes, volumes)
                if sig:
                    return "qullamaggie_parabolic_short", 75.0
            except Exception:
                pass

        return None, 0.0

    def select_batch(
        self,
        market_data: dict[str, dict[str, list[float]]],
        regime: str = "sideways",
    ) -> dict[str, StrategyChoice]:
        """Select strategies for multiple tickers.

        Args:
            market_data: Dict of ticker → {"highs": [...], "lows": [...], "closes": [...]}.
            regime: Current market regime.

        Returns:
            Dict of ticker → StrategyChoice.
        """
        results = {}
        for ticker, data in market_data.items():
            highs = data.get("highs", [])
            lows = data.get("lows", [])
            closes = data.get("closes", [])
            if closes:
                results[ticker] = self.select(ticker, highs, lows, closes, regime)
        return results

    def record_outcome(self, strategy: str, pnl: float) -> None:
        """Record a trade outcome for A/B comparison tracking.

        Args:
            strategy: Which strategy produced this trade.
            pnl: Realized P&L.
        """
        if strategy not in self._strategy_stats:
            self._strategy_stats[strategy] = {"signals": 0, "wins": 0, "total_pnl": 0.0}
        stats = self._strategy_stats[strategy]
        stats["signals"] += 1
        if pnl > 0:
            stats["wins"] += 1
        stats["total_pnl"] += pnl

    def get_strategy_stats(self) -> dict[str, dict]:
        """Get A/B comparison statistics."""
        result = {}
        for name, stats in self._strategy_stats.items():
            total = stats["signals"]
            result[name] = {
                "signals": total,
                "wins": stats["wins"],
                "win_rate": stats["wins"] / max(total, 1) * 100,
                "total_pnl": round(stats["total_pnl"], 2),
                "avg_pnl": round(stats["total_pnl"] / max(total, 1), 2),
            }
        return result
