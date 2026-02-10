"""PRD-173: Fusion Bridge — wraps SignalFusion for pipeline use.

Translates between the bot pipeline's TradeSignal format and
SignalFusion's RawSignal/FusedSignal format, enabling multi-source
signal combination within the orchestrator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.signal_fusion.collector import RawSignal, SignalSource
from src.signal_fusion.fusion import FusedSignal, FusionConfig, SignalFusion

logger = logging.getLogger(__name__)


@dataclass
class FusionResult:
    """Pipeline-friendly fusion result."""

    symbol: str
    direction: str  # 'bullish', 'bearish', 'neutral'
    composite_score: float  # -100 to +100
    confidence: float  # 0.0-1.0
    source_count: int
    should_trade: bool = False
    reasoning: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "composite_score": round(self.composite_score, 2),
            "confidence": round(self.confidence, 3),
            "source_count": self.source_count,
            "should_trade": self.should_trade,
            "reasoning": self.reasoning,
        }


class FusionBridge:
    """Bridge between SignalFusion and the bot pipeline.

    Provides a simplified API for fusing signals and managing
    source weights from within the orchestrator.

    Args:
        config: FusionConfig for the underlying engine.
        min_score_to_trade: Minimum |composite_score| to approve a trade.
        min_confidence: Minimum confidence for trade approval.
    """

    def __init__(
        self,
        config: FusionConfig | None = None,
        min_score_to_trade: float = 30.0,
        min_confidence: float = 0.4,
    ) -> None:
        self._fusion = SignalFusion(config)
        self._min_score = min_score_to_trade
        self._min_confidence = min_confidence
        self._history: list[FusionResult] = []

    def fuse_signals(self, signals: list[RawSignal]) -> FusionResult:
        """Fuse a list of raw signals into a pipeline-friendly result.

        Args:
            signals: Raw signals from various sources.

        Returns:
            FusionResult with trade approval decision.
        """
        fused = self._fusion.fuse(signals)

        should_trade = (
            abs(fused.composite_score) >= self._min_score
            and fused.confidence >= self._min_confidence
            and fused.source_count >= 2
        )

        result = FusionResult(
            symbol=fused.symbol,
            direction=fused.direction,
            composite_score=fused.composite_score,
            confidence=fused.confidence,
            source_count=fused.source_count,
            should_trade=should_trade,
            reasoning=fused.reasoning,
        )
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        return result

    def get_fusion_weights(self) -> dict[str, float]:
        """Get current source weights from the fusion config."""
        return {
            src.value: weight
            for src, weight in self._fusion.config.source_weights.items()
        }

    def update_weights(self, weights: dict[str, float]) -> None:
        """Update source weights in the fusion engine.

        Args:
            weights: Dict of source_name → weight (will be normalized).
        """
        new_weights = {}
        for name, weight in weights.items():
            try:
                source = SignalSource(name)
                new_weights[source] = weight
            except ValueError:
                logger.warning("Unknown signal source '%s', skipping", name)

        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v / total for k, v in new_weights.items()}
            self._fusion.config.source_weights = new_weights
            logger.info("Fusion weights updated: %s", {k.value: round(v, 3) for k, v in new_weights.items()})

    def get_fusion_history(self, limit: int = 50) -> list[dict]:
        """Get recent fusion results."""
        return [r.to_dict() for r in self._history[-limit:]]
