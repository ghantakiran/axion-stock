"""Trade Recommender — converts fused signals to actionable recommendations.

Produces buy/sell/hold recommendations with position sizing,
stop-loss, take-profit, and risk classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.signal_fusion.fusion import FusedSignal


class Action:
    """Trade action constants."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


VALID_ACTIONS = {Action.STRONG_BUY, Action.BUY, Action.HOLD, Action.SELL, Action.STRONG_SELL}


@dataclass
class Recommendation:
    """A single trade recommendation.

    Attributes:
        symbol: Ticker symbol.
        action: STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL.
        fused_signal: The fused signal that generated this recommendation.
        position_size_pct: Suggested portfolio allocation (0-15%).
        stop_loss_pct: Suggested stop loss percentage (2-5%).
        take_profit_pct: Suggested take profit percentage.
        time_horizon: 'intraday', 'swing', or 'position'.
        reasoning: Human-readable explanation.
        risk_level: 'low', 'medium', or 'high'.
    """

    symbol: str
    action: str
    fused_signal: FusedSignal
    position_size_pct: float = 0.0
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 6.0
    time_horizon: str = "swing"
    reasoning: str = ""
    risk_level: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "symbol": self.symbol,
            "action": self.action,
            "position_size_pct": round(self.position_size_pct, 2),
            "stop_loss_pct": round(self.stop_loss_pct, 2),
            "take_profit_pct": round(self.take_profit_pct, 2),
            "time_horizon": self.time_horizon,
            "reasoning": self.reasoning,
            "risk_level": self.risk_level,
            "composite_score": round(self.fused_signal.composite_score, 2),
            "confidence": round(self.fused_signal.confidence, 3),
        }


@dataclass
class RecommenderConfig:
    """Configuration for the trade recommender.

    Attributes:
        min_confidence: Minimum fusion confidence to generate a recommendation.
        max_positions: Maximum number of concurrent positions.
        max_single_weight: Maximum portfolio weight for a single position (0-1).
        risk_tolerance: 'conservative', 'moderate', or 'aggressive'.
        enable_short: Whether short selling is allowed.
    """

    min_confidence: float = 0.5
    max_positions: int = 10
    max_single_weight: float = 0.15
    risk_tolerance: str = "moderate"
    enable_short: bool = False


# ── Action thresholds ─────────────────────────────────────────────────

# Composite score thresholds for action classification
STRONG_BUY_THRESHOLD = 50.0
BUY_THRESHOLD = 20.0
SELL_THRESHOLD = -20.0
STRONG_SELL_THRESHOLD = -50.0


class TradeRecommender:
    """Converts fused signals into actionable trade recommendations.

    Handles action classification, position sizing, risk parameters,
    and portfolio-level ranking and limiting.

    Args:
        config: RecommenderConfig with thresholds and constraints.
    """

    def __init__(self, config: RecommenderConfig | None = None) -> None:
        self.config = config or RecommenderConfig()

    def recommend(self, fused: FusedSignal) -> Optional[Recommendation]:
        """Generate a recommendation from a single fused signal.

        Returns None if the signal doesn't meet minimum thresholds.

        Args:
            fused: A FusedSignal for one symbol.

        Returns:
            Recommendation or None if below min_confidence.
        """
        if fused.confidence < self.config.min_confidence:
            return None

        action = self._classify_action(fused)

        # Skip SELL/STRONG_SELL if shorting disabled
        if not self.config.enable_short and action in (
            Action.SELL,
            Action.STRONG_SELL,
        ):
            action = Action.HOLD

        position_size = self._calculate_position_size(fused, action)
        stop_loss = self._calculate_stop_loss(fused, action)
        take_profit = self._calculate_take_profit(fused, action)
        time_horizon = self._determine_time_horizon(fused)
        risk_level = self._assess_risk(fused)
        reasoning = self._build_reasoning(fused, action, risk_level)

        return Recommendation(
            symbol=fused.symbol,
            action=action,
            fused_signal=fused,
            position_size_pct=position_size,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit,
            time_horizon=time_horizon,
            reasoning=reasoning,
            risk_level=risk_level,
        )

    def recommend_portfolio(
        self, fused_signals: dict[str, FusedSignal]
    ) -> list[Recommendation]:
        """Generate recommendations for an entire portfolio of fused signals.

        Args:
            fused_signals: Dict mapping symbol -> FusedSignal.

        Returns:
            List of recommendations, ranked and limited to max_positions.
        """
        recs: list[Recommendation] = []
        for _symbol, fused in fused_signals.items():
            rec = self.recommend(fused)
            if rec is not None and rec.action != Action.HOLD:
                recs.append(rec)

        return self.rank_opportunities(recs)

    def rank_opportunities(
        self, recommendations: list[Recommendation]
    ) -> list[Recommendation]:
        """Rank and limit recommendations by opportunity quality.

        Sorts by absolute composite score * confidence (descending),
        then truncates to max_positions.

        Args:
            recommendations: Unranked list of recommendations.

        Returns:
            Ranked and limited list.
        """
        ranked = sorted(
            recommendations,
            key=lambda r: abs(r.fused_signal.composite_score) * r.fused_signal.confidence,
            reverse=True,
        )
        return ranked[: self.config.max_positions]

    # ── internal helpers ──────────────────────────────────────────

    def _classify_action(self, fused: FusedSignal) -> str:
        """Map composite score to an action."""
        score = fused.composite_score
        if score >= STRONG_BUY_THRESHOLD:
            return Action.STRONG_BUY
        elif score >= BUY_THRESHOLD:
            return Action.BUY
        elif score <= STRONG_SELL_THRESHOLD:
            return Action.STRONG_SELL
        elif score <= SELL_THRESHOLD:
            return Action.SELL
        else:
            return Action.HOLD

    def _calculate_position_size(self, fused: FusedSignal, action: str) -> float:
        """Size the position based on confidence and max weight.

        Formula: position_size = min(confidence * max_weight, max_weight)
        HOLD positions get 0% allocation.
        """
        if action == Action.HOLD:
            return 0.0
        max_weight = self.config.max_single_weight * 100.0  # convert to pct
        size = fused.confidence * max_weight
        return min(size, max_weight)

    def _calculate_stop_loss(self, fused: FusedSignal, action: str) -> float:
        """Calculate stop loss percentage (2-5%) based on risk."""
        if action == Action.HOLD:
            return 0.0
        # Higher confidence -> tighter stop
        base_stop = 3.5
        confidence_adj = (1.0 - fused.confidence) * 1.5
        risk_adj = {
            "conservative": 0.5,
            "moderate": 0.0,
            "aggressive": -0.5,
        }.get(self.config.risk_tolerance, 0.0)
        stop = base_stop + confidence_adj + risk_adj
        return max(2.0, min(5.0, stop))

    def _calculate_take_profit(self, fused: FusedSignal, action: str) -> float:
        """Calculate take profit percentage based on score strength."""
        if action == Action.HOLD:
            return 0.0
        score_abs = abs(fused.composite_score)
        # Stronger signals get larger profit targets
        base_tp = 4.0
        strength_bonus = (score_abs / 100.0) * 6.0
        return round(base_tp + strength_bonus, 2)

    def _determine_time_horizon(self, fused: FusedSignal) -> str:
        """Determine suggested time horizon from signal characteristics."""
        score_abs = abs(fused.composite_score)
        if score_abs >= 70:
            return "intraday"
        elif score_abs >= 35:
            return "swing"
        else:
            return "position"

    def _assess_risk(self, fused: FusedSignal) -> str:
        """Assess risk level based on agreement and confidence."""
        agreement_ratio = len(fused.agreeing_sources) / max(fused.source_count, 1)
        if fused.confidence >= 0.7 and agreement_ratio >= 0.7:
            return "low"
        elif fused.confidence >= 0.4 and agreement_ratio >= 0.4:
            return "medium"
        else:
            return "high"

    def _build_reasoning(
        self, fused: FusedSignal, action: str, risk_level: str
    ) -> str:
        """Build a human-readable reasoning string."""
        parts = [
            f"{action} {fused.symbol}:",
            f"Composite score {fused.composite_score:+.1f},",
            f"confidence {fused.confidence:.0%},",
            f"{len(fused.agreeing_sources)}/{fused.source_count} sources agree.",
            f"Risk: {risk_level}.",
        ]
        if fused.dissenting_sources:
            parts.append(
                f"Dissent from: {', '.join(fused.dissenting_sources)}."
            )
        return " ".join(parts)
