"""Fund Flow Tracking.

Aggregates daily/weekly fund flows, computes net flows,
momentum, cumulative totals, and flow-to-AUM ratios.
"""

import logging
from typing import Optional

import numpy as np

from src.fundflow.config import (
    FlowTrackerConfig,
    FlowStrength,
    DEFAULT_TRACKER_CONFIG,
)
from src.fundflow.models import FundFlow, FlowSummary

logger = logging.getLogger(__name__)


class FlowTracker:
    """Tracks and aggregates fund flows."""

    def __init__(self, config: Optional[FlowTrackerConfig] = None) -> None:
        self.config = config or DEFAULT_TRACKER_CONFIG
        self._history: dict[str, list[FundFlow]] = {}

    def add_flow(self, flow: FundFlow) -> None:
        """Record a fund flow observation."""
        if flow.fund_name not in self._history:
            self._history[flow.fund_name] = []
        self._history[flow.fund_name].append(flow)

    def add_flows(self, flows: list[FundFlow]) -> None:
        """Record multiple fund flow observations."""
        for f in flows:
            self.add_flow(f)

    def summarize(self, fund_name: str) -> FlowSummary:
        """Compute flow summary for a fund.

        Args:
            fund_name: Fund identifier.

        Returns:
            FlowSummary with aggregated metrics.
        """
        flows = self._history.get(fund_name, [])
        if not flows:
            return self._empty_summary(fund_name)

        # Use lookback window
        recent = flows[-self.config.lookback_days:]
        n = len(recent)

        inflows = np.array([f.inflow for f in recent])
        outflows = np.array([f.outflow for f in recent])
        net_flows = np.array([f.net_flow for f in recent])
        aums = np.array([f.aum for f in recent])

        total_inflow = float(np.sum(inflows))
        total_outflow = float(np.sum(outflows))
        net_flow = float(np.sum(net_flows))
        cumulative = float(np.cumsum(net_flows)[-1])

        # Flow momentum: rate of change over momentum window
        momentum = self._compute_momentum(net_flows)

        # Average flow as % of AUM
        valid_aum = aums > 0
        if np.any(valid_aum):
            flow_pcts = net_flows[valid_aum] / aums[valid_aum] * 100
            avg_flow_pct = float(np.mean(flow_pcts))
        else:
            avg_flow_pct = 0.0

        # Classify strength
        strength = self._classify_strength(avg_flow_pct)

        return FlowSummary(
            name=fund_name,
            total_inflow=round(total_inflow, 2),
            total_outflow=round(total_outflow, 2),
            net_flow=round(net_flow, 2),
            flow_momentum=round(momentum, 4),
            cumulative_flow=round(cumulative, 2),
            avg_flow_pct=round(avg_flow_pct, 4),
            strength=strength,
            n_days=n,
        )

    def summarize_all(self) -> list[FlowSummary]:
        """Summarize all tracked funds."""
        return [self.summarize(name) for name in self._history]

    def _compute_momentum(self, net_flows: np.ndarray) -> float:
        """Flow momentum as rate of change.

        Compares recent window average to prior window average.
        """
        w = self.config.momentum_window
        if len(net_flows) < 2 * w:
            if len(net_flows) < 2:
                return 0.0
            half = len(net_flows) // 2
            recent_avg = float(np.mean(net_flows[half:]))
            prior_avg = float(np.mean(net_flows[:half]))
        else:
            recent_avg = float(np.mean(net_flows[-w:]))
            prior_avg = float(np.mean(net_flows[-2 * w:-w]))

        if prior_avg == 0:
            return 1.0 if recent_avg > 0 else (-1.0 if recent_avg < 0 else 0.0)

        return (recent_avg - prior_avg) / abs(prior_avg)

    def _classify_strength(self, avg_flow_pct: float) -> FlowStrength:
        """Classify flow strength based on average flow %."""
        sig = self.config.significant_flow_pct * 100  # convert to pct
        abs_pct = abs(avg_flow_pct)

        if abs_pct >= sig * 2:
            return FlowStrength.STRONG
        elif abs_pct >= sig:
            return FlowStrength.MODERATE
        elif abs_pct >= sig * 0.5:
            return FlowStrength.WEAK
        return FlowStrength.NEUTRAL

    def get_history(self, fund_name: str) -> list[FundFlow]:
        """Get flow history for a fund."""
        return self._history.get(fund_name, [])

    def reset(self) -> None:
        """Clear all flow history."""
        self._history.clear()

    def _empty_summary(self, name: str) -> FlowSummary:
        return FlowSummary(
            name=name,
            total_inflow=0.0, total_outflow=0.0, net_flow=0.0,
            flow_momentum=0.0, cumulative_flow=0.0, avg_flow_pct=0.0,
        )
