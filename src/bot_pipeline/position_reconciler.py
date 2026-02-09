"""Position reconciliation — syncs local state with broker positions.

Detects discrepancies between what the bot thinks it holds and what
the broker actually reports. Catches:
- Ghost positions (local but not at broker — failed sells)
- Orphaned positions (at broker but not local — manual trades or missed fills)
- Quantity mismatches (partial fills not reflected)
- Price drift (stale local prices vs broker marks)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.trade_executor.executor import Position

logger = logging.getLogger(__name__)


@dataclass
class PositionMismatch:
    """A detected discrepancy between local and broker state.

    Attributes:
        ticker: The symbol with the mismatch.
        mismatch_type: ghost | orphaned | qty_mismatch | price_drift.
        local_qty: Quantity tracked locally (0 if orphaned).
        broker_qty: Quantity at broker (0 if ghost).
        local_price: Local mark price.
        broker_price: Broker mark price.
        severity: low | medium | high | critical.
        detail: Human-readable description.
    """

    ticker: str
    mismatch_type: str
    local_qty: int = 0
    broker_qty: int = 0
    local_price: float = 0.0
    broker_price: float = 0.0
    severity: str = "medium"
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "mismatch_type": self.mismatch_type,
            "local_qty": self.local_qty,
            "broker_qty": self.broker_qty,
            "severity": self.severity,
            "detail": self.detail,
        }


@dataclass
class ReconciliationReport:
    """Result of reconciling local vs broker positions.

    Attributes:
        matched: Tickers that match in both systems.
        ghosts: Positions in local but NOT at broker.
        orphaned: Positions at broker but NOT in local.
        mismatched: Positions in both but with discrepancies.
        total_local: Count of local positions.
        total_broker: Count of broker positions.
        is_clean: True if no discrepancies found.
        timestamp: When reconciliation was performed.
    """

    matched: list[str] = field(default_factory=list)
    ghosts: list[PositionMismatch] = field(default_factory=list)
    orphaned: list[PositionMismatch] = field(default_factory=list)
    mismatched: list[PositionMismatch] = field(default_factory=list)
    total_local: int = 0
    total_broker: int = 0
    is_clean: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "matched": self.matched,
            "ghosts": [g.to_dict() for g in self.ghosts],
            "orphaned": [o.to_dict() for o in self.orphaned],
            "mismatched": [m.to_dict() for m in self.mismatched],
            "total_local": self.total_local,
            "total_broker": self.total_broker,
            "is_clean": self.is_clean,
            "timestamp": self.timestamp.isoformat(),
        }


class PositionReconciler:
    """Reconcile local position state with broker-reported positions.

    Compares ticker, quantity, and direction between the bot's internal
    position list and the broker's account positions. Reports discrepancies
    by severity.

    Args:
        price_drift_threshold_pct: Max acceptable price drift before flagging.

    Example:
        reconciler = PositionReconciler()
        report = reconciler.reconcile(
            local_positions=executor.positions,
            broker_positions=broker.get_positions()
        )
        if not report.is_clean:
            for ghost in report.ghosts:
                logger.error("Ghost position: %s", ghost.detail)
    """

    def __init__(self, price_drift_threshold_pct: float = 5.0) -> None:
        self.price_drift_threshold_pct = price_drift_threshold_pct

    def reconcile(
        self,
        local_positions: list[Position],
        broker_positions: list[dict[str, Any]],
    ) -> ReconciliationReport:
        """Compare local positions against broker positions.

        Args:
            local_positions: Bot's internal Position objects.
            broker_positions: Broker-reported positions as dicts with keys:
                symbol, qty, side, market_value, current_price.

        Returns:
            ReconciliationReport with all discrepancies.
        """
        local_map: dict[str, Position] = {}
        for pos in local_positions:
            local_map[pos.ticker] = pos

        broker_map: dict[str, dict] = {}
        for bp in broker_positions:
            symbol = bp.get("symbol", bp.get("ticker", ""))
            if symbol:
                broker_map[symbol] = bp

        matched: list[str] = []
        ghosts: list[PositionMismatch] = []
        orphaned: list[PositionMismatch] = []
        mismatched: list[PositionMismatch] = []

        all_tickers = set(local_map.keys()) | set(broker_map.keys())

        for ticker in sorted(all_tickers):
            in_local = ticker in local_map
            in_broker = ticker in broker_map

            if in_local and not in_broker:
                # Ghost: we think we hold it, broker says no
                pos = local_map[ticker]
                ghosts.append(PositionMismatch(
                    ticker=ticker,
                    mismatch_type="ghost",
                    local_qty=pos.shares,
                    broker_qty=0,
                    local_price=pos.current_price,
                    severity="critical",
                    detail=f"Ghost position: {pos.shares} {pos.direction} {ticker} not at broker",
                ))

            elif in_broker and not in_local:
                # Orphaned: broker has it, we don't track it
                bp = broker_map[ticker]
                orphaned.append(PositionMismatch(
                    ticker=ticker,
                    mismatch_type="orphaned",
                    local_qty=0,
                    broker_qty=int(bp.get("qty", 0)),
                    broker_price=float(bp.get("current_price", 0)),
                    severity="high",
                    detail=f"Orphaned position: {bp.get('qty', 0)} {ticker} at broker, not tracked locally",
                ))

            else:
                # Both exist — check for mismatches
                pos = local_map[ticker]
                bp = broker_map[ticker]
                broker_qty = int(bp.get("qty", 0))
                broker_price = float(bp.get("current_price", 0))

                issues: list[str] = []

                # Quantity mismatch
                if pos.shares != broker_qty:
                    issues.append(
                        f"qty mismatch: local={pos.shares}, broker={broker_qty}"
                    )

                # Direction mismatch
                broker_side = bp.get("side", "").lower()
                if broker_side and broker_side != pos.direction:
                    issues.append(
                        f"direction mismatch: local={pos.direction}, broker={broker_side}"
                    )

                # Price drift
                if pos.current_price > 0 and broker_price > 0:
                    drift_pct = abs(pos.current_price - broker_price) / pos.current_price * 100
                    if drift_pct > self.price_drift_threshold_pct:
                        issues.append(
                            f"price drift {drift_pct:.1f}%: local=${pos.current_price:.2f}, "
                            f"broker=${broker_price:.2f}"
                        )

                if issues:
                    mismatched.append(PositionMismatch(
                        ticker=ticker,
                        mismatch_type="qty_mismatch" if pos.shares != broker_qty else "price_drift",
                        local_qty=pos.shares,
                        broker_qty=broker_qty,
                        local_price=pos.current_price,
                        broker_price=broker_price,
                        severity="high" if pos.shares != broker_qty else "medium",
                        detail=f"{ticker}: {'; '.join(issues)}",
                    ))
                else:
                    matched.append(ticker)

        is_clean = not ghosts and not orphaned and not mismatched

        report = ReconciliationReport(
            matched=matched,
            ghosts=ghosts,
            orphaned=orphaned,
            mismatched=mismatched,
            total_local=len(local_positions),
            total_broker=len(broker_positions),
            is_clean=is_clean,
        )

        if not is_clean:
            logger.warning(
                "Reconciliation: %d matched, %d ghosts, %d orphaned, %d mismatched",
                len(matched), len(ghosts), len(orphaned), len(mismatched),
            )

        return report
