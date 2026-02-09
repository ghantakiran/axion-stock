"""Live Attribution Engine.

High-level API that orchestrates signal linking, P&L decomposition,
and rolling performance tracking into a unified attribution pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AttributionResult:
    """Result for a single attributed trade."""

    linked_trade: object = None  # LinkedTrade
    breakdown: object = None  # PnLBreakdown

    def to_dict(self) -> dict:
        return {
            "trade": (
                self.linked_trade.to_dict() if self.linked_trade else {}
            ),
            "breakdown": (
                self.breakdown.to_dict() if self.breakdown else {}
            ),
        }


@dataclass
class LiveAttributionReport:
    """Comprehensive live attribution report."""

    results: list[AttributionResult] = field(default_factory=list)
    linkage_report: object = None  # LinkageReport
    decomposition_report: object = None  # DecompositionReport
    performance_snapshot: object = None  # TrackerSnapshot

    @property
    def total_trades(self) -> int:
        return len(self.results)

    @property
    def total_pnl(self) -> float:
        return sum(
            r.linked_trade.realized_pnl
            for r in self.results
            if r.linked_trade
        )

    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "total_pnl": round(self.total_pnl, 2),
            "results": [
                r.to_dict() for r in self.results[:50]
            ],  # Limit output
            "linkage": (
                self.linkage_report.to_dict()
                if self.linkage_report
                else {}
            ),
            "decomposition": (
                self.decomposition_report.to_dict()
                if self.decomposition_report
                else {}
            ),
            "performance": (
                self.performance_snapshot.to_dict()
                if self.performance_snapshot
                else {}
            ),
        }

    def to_dataframe(self):
        import pandas as pd

        if not self.results:
            return pd.DataFrame()
        rows = []
        for r in self.results:
            row = {}
            if r.linked_trade:
                row.update(r.linked_trade.to_dict())
            if r.breakdown:
                bd = r.breakdown.to_dict()
                row.update(
                    {
                        f"decomp_{k}": v
                        for k, v in bd.items()
                        if k not in ("trade_id", "symbol")
                    }
                )
            rows.append(row)
        return pd.DataFrame(rows)


class AttributionEngine:
    """Main orchestrator for live trade attribution.

    Usage:
        engine = AttributionEngine()
        engine.register_signal(signal_dict)
        # ... later when trade completes ...
        result = engine.attribute_trade(trade_dict)
        report = engine.get_report()
    """

    def __init__(self, config: Optional[object] = None):
        from src.trade_attribution.config import AttributionConfig
        from src.trade_attribution.linker import TradeSignalLinker
        from src.trade_attribution.decomposer import TradeDecomposer
        from src.trade_attribution.tracker import SignalPerformanceTracker

        self.config = config or AttributionConfig()
        self.linker = TradeSignalLinker(self.config)
        self.decomposer = TradeDecomposer(self.config)
        self.tracker = SignalPerformanceTracker(self.config)
        self._results: list[AttributionResult] = []

    def register_signal(self, signal: dict) -> None:
        """Register a signal for future trade matching."""
        self.linker.register_signal(signal)

    def attribute_trade(
        self,
        trade: dict,
        entry_bar: Optional[dict] = None,
        exit_bar: Optional[dict] = None,
    ) -> AttributionResult:
        """Attribute a completed trade: link, decompose, and track."""
        linked = self.linker.link_trade(trade)
        breakdown = self.decomposer.decompose(trade, entry_bar, exit_bar)
        self.tracker.record_trade(linked)
        result = AttributionResult(
            linked_trade=linked, breakdown=breakdown
        )
        self._results.append(result)
        return result

    def get_report(self) -> LiveAttributionReport:
        """Generate comprehensive attribution report."""
        return LiveAttributionReport(
            results=list(self._results),
            linkage_report=self.linker.get_linkage_report(),
            decomposition_report=self.decomposer.decompose_batch(
                [
                    {
                        "trade_id": r.linked_trade.trade_id,
                        "symbol": r.linked_trade.symbol,
                        "entry_price": r.linked_trade.entry_price,
                        "exit_price": r.linked_trade.exit_price,
                        "shares": r.linked_trade.entry_shares,
                        "direction": r.linked_trade.signal_direction,
                        "pnl": r.linked_trade.realized_pnl,
                    }
                    for r in self._results
                    if r.linked_trade
                ]
            ),
            performance_snapshot=self.tracker.get_snapshot(),
        )

    def get_performance_snapshot(self):
        """Get current signal performance snapshot."""
        return self.tracker.get_snapshot()

    def get_trade_count(self) -> int:
        return len(self._results)

    def clear(self) -> None:
        self.linker.clear()
        self.tracker.clear()
        self._results.clear()
