"""Fusion Agent — autonomous pipeline orchestrator.

Runs the full collect -> fuse -> recommend pipeline on a schedule,
tracks state and history, and optionally executes via broker integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.signal_fusion.collector import DEMO_TICKERS, RawSignal, SignalCollector
from src.signal_fusion.fusion import FusedSignal, FusionConfig, SignalFusion
from src.signal_fusion.recommender import (
    Recommendation,
    RecommenderConfig,
    TradeRecommender,
)


@dataclass
class AgentConfig:
    """Configuration for the autonomous fusion agent.

    Attributes:
        scan_interval_minutes: How often to run the pipeline (minutes).
        max_recommendations: Max recommendations per scan.
        auto_execute: Whether to send orders to the broker.
        paper_mode: If True, use paper trading even if auto_execute is True.
        symbols: List of symbols to scan. Defaults to DEMO_TICKERS.
    """

    scan_interval_minutes: int = 15
    max_recommendations: int = 5
    auto_execute: bool = False
    paper_mode: bool = True
    symbols: list[str] = field(default_factory=lambda: list(DEMO_TICKERS))


@dataclass
class AgentState:
    """Snapshot of agent state after a scan.

    Attributes:
        last_scan: When the scan ran.
        signals_collected: Total raw signals gathered.
        fusions_produced: Number of fused signals created.
        recommendations: List of trade recommendations from this scan.
        execution_results: Results if auto_execute was on.
        scan_duration_ms: How long the scan took (milliseconds).
    """

    last_scan: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signals_collected: int = 0
    fusions_produced: int = 0
    recommendations: list[Recommendation] = field(default_factory=list)
    execution_results: list[dict[str, Any]] = field(default_factory=list)
    scan_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to a dictionary."""
        return {
            "last_scan": self.last_scan.isoformat(),
            "signals_collected": self.signals_collected,
            "fusions_produced": self.fusions_produced,
            "recommendations_count": len(self.recommendations),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "execution_results": self.execution_results,
            "scan_duration_ms": round(self.scan_duration_ms, 1),
        }


class FusionAgent:
    """Autonomous signal fusion pipeline orchestrator.

    Pipeline: collect -> fuse -> recommend -> (optionally execute).

    Maintains a history of scan states for auditing and analysis.

    Args:
        agent_config: AgentConfig for scan behavior.
        fusion_config: FusionConfig for signal fusion weights.
        recommender_config: RecommenderConfig for recommendation thresholds.
        collector: Optional custom SignalCollector instance.
    """

    def __init__(
        self,
        agent_config: AgentConfig | None = None,
        fusion_config: FusionConfig | None = None,
        recommender_config: RecommenderConfig | None = None,
        collector: SignalCollector | None = None,
    ) -> None:
        self.config = agent_config or AgentConfig()
        self._collector = collector or SignalCollector(demo_mode=True)
        self._fusion = SignalFusion(config=fusion_config)
        self._recommender = TradeRecommender(config=recommender_config)
        self._state: AgentState | None = None
        self._history: list[AgentState] = []

    def scan(self) -> AgentState:
        """Run the full pipeline: collect -> fuse -> recommend.

        Returns:
            AgentState with all results from this scan.
        """
        start = datetime.now(timezone.utc)

        # 1. Collect signals for all configured symbols
        all_signals: dict[str, list[RawSignal]] = {}
        total_signals = 0
        for symbol in self.config.symbols:
            signals = self._collector.collect_all(symbol)
            if signals:
                all_signals[symbol] = signals
                total_signals += len(signals)

        # 2. Fuse signals per symbol
        fused: dict[str, FusedSignal] = self._fusion.fuse_batch(all_signals)

        # 3. Generate recommendations
        recs = self._recommender.recommend_portfolio(fused)
        # Limit to max_recommendations
        recs = recs[: self.config.max_recommendations]

        # 4. Optionally execute (placeholder for broker integration)
        execution_results: list[dict[str, Any]] = []
        if self.config.auto_execute and recs:
            execution_results = self._execute(recs)

        end = datetime.now(timezone.utc)
        duration_ms = (end - start).total_seconds() * 1000.0

        state = AgentState(
            last_scan=start,
            signals_collected=total_signals,
            fusions_produced=len(fused),
            recommendations=recs,
            execution_results=execution_results,
            scan_duration_ms=duration_ms,
        )

        self._state = state
        self._history.append(state)

        return state

    def get_recommendations(self) -> list[Recommendation]:
        """Return recommendations from the most recent scan.

        Returns:
            List of Recommendation objects (empty if no scan has run).
        """
        if self._state is None:
            return []
        return list(self._state.recommendations)

    def get_state(self) -> AgentState | None:
        """Return the current agent state (None if no scan has run)."""
        return self._state

    def get_history(self, limit: int = 10) -> list[AgentState]:
        """Return recent scan history.

        Args:
            limit: Max number of historical states to return.

        Returns:
            List of AgentState objects, most recent first.
        """
        return list(reversed(self._history[-limit:]))

    def _execute(self, recs: list[Recommendation]) -> list[dict[str, Any]]:
        """Execute recommendations via broker (placeholder).

        In production, this would integrate with MultiBrokerExecutor
        or the trade_executor module. For now, returns mock results.

        Args:
            recs: Recommendations to execute.

        Returns:
            List of execution result dicts.
        """
        results: list[dict[str, Any]] = []
        for rec in recs:
            result = {
                "symbol": rec.symbol,
                "action": rec.action,
                "status": "simulated" if self.config.paper_mode else "pending",
                "position_size_pct": rec.position_size_pct,
                "paper_mode": self.config.paper_mode,
            }
            results.append(result)
        return results
