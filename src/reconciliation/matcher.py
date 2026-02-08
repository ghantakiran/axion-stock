"""PRD-126: Trade Reconciliation — Matching Engine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .config import (
    BreakType,
    MatchStrategy,
    ReconciliationConfig,
    ReconciliationStatus,
    ToleranceConfig,
)


@dataclass
class TradeRecord:
    """A trade record from either internal or broker source."""

    trade_id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    timestamp: datetime
    source: str  # "internal" or broker name
    order_id: Optional[str] = None
    account_id: Optional[str] = None
    venue: Optional[str] = None
    fees: float = 0.0

    @property
    def notional(self) -> float:
        return self.quantity * self.price


@dataclass
class MatchResult:
    """Result of matching two trade records."""

    match_id: str
    internal_trade: Optional[TradeRecord]
    broker_trade: Optional[TradeRecord]
    status: ReconciliationStatus
    break_type: Optional[BreakType] = None
    confidence: float = 0.0
    matched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


class MatchingEngine:
    """Engine for matching internal trades against broker confirmations."""

    def __init__(self, config: Optional[ReconciliationConfig] = None) -> None:
        self.config = config or ReconciliationConfig()
        self._match_history: list[MatchResult] = []

    def match_trades(
        self,
        internal_trades: list[TradeRecord],
        broker_trades: list[TradeRecord],
    ) -> list[MatchResult]:
        """Match internal trades against broker trades."""
        results: list[MatchResult] = []
        matched_broker_ids: set[str] = set()
        matched_internal_ids: set[str] = set()

        # Phase 1: exact matches
        for itrade in internal_trades:
            for btrade in broker_trades:
                if btrade.trade_id in matched_broker_ids:
                    continue
                if self.exact_match(itrade, btrade):
                    result = MatchResult(
                        match_id=uuid.uuid4().hex[:16],
                        internal_trade=itrade,
                        broker_trade=btrade,
                        status=ReconciliationStatus.MATCHED,
                        confidence=1.0,
                    )
                    results.append(result)
                    matched_broker_ids.add(btrade.trade_id)
                    matched_internal_ids.add(itrade.trade_id)
                    break

        # Phase 2: fuzzy matches for unmatched
        if self.config.strategy in (MatchStrategy.FUZZY, MatchStrategy.MANUAL):
            for itrade in internal_trades:
                if itrade.trade_id in matched_internal_ids:
                    continue
                best_match: Optional[MatchResult] = None
                best_confidence = 0.0
                for btrade in broker_trades:
                    if btrade.trade_id in matched_broker_ids:
                        continue
                    is_match, confidence = self.fuzzy_match(
                        itrade, btrade, self.config.tolerances
                    )
                    if is_match and confidence > best_confidence:
                        best_confidence = confidence
                        break_type = self._identify_break(itrade, btrade)
                        status = (
                            ReconciliationStatus.MATCHED
                            if confidence >= self.config.auto_resolve_threshold
                            else ReconciliationStatus.BROKEN
                        )
                        best_match = MatchResult(
                            match_id=uuid.uuid4().hex[:16],
                            internal_trade=itrade,
                            broker_trade=btrade,
                            status=status,
                            break_type=break_type,
                            confidence=confidence,
                        )
                if best_match:
                    results.append(best_match)
                    if best_match.broker_trade:
                        matched_broker_ids.add(best_match.broker_trade.trade_id)
                    matched_internal_ids.add(itrade.trade_id)

        # Phase 3: unmatched trades
        for itrade in internal_trades:
            if itrade.trade_id not in matched_internal_ids:
                results.append(
                    MatchResult(
                        match_id=uuid.uuid4().hex[:16],
                        internal_trade=itrade,
                        broker_trade=None,
                        status=ReconciliationStatus.BROKEN,
                        break_type=BreakType.MISSING_BROKER,
                        confidence=0.0,
                    )
                )
        for btrade in broker_trades:
            if btrade.trade_id not in matched_broker_ids:
                results.append(
                    MatchResult(
                        match_id=uuid.uuid4().hex[:16],
                        internal_trade=None,
                        broker_trade=btrade,
                        status=ReconciliationStatus.BROKEN,
                        break_type=BreakType.MISSING_INTERNAL,
                        confidence=0.0,
                    )
                )

        self._match_history.extend(results)
        return results

    def exact_match(self, trade1: TradeRecord, trade2: TradeRecord) -> bool:
        """Check if two trades match exactly."""
        return (
            trade1.symbol == trade2.symbol
            and trade1.side == trade2.side
            and trade1.quantity == trade2.quantity
            and trade1.price == trade2.price
        )

    def fuzzy_match(
        self,
        trade1: TradeRecord,
        trade2: TradeRecord,
        tolerances: ToleranceConfig,
    ) -> tuple[bool, float]:
        """Check if two trades match within tolerance. Returns (is_match, confidence)."""
        if trade1.symbol != trade2.symbol or trade1.side != trade2.side:
            return False, 0.0

        score = 1.0

        # Price comparison
        if trade1.price > 0:
            price_diff_pct = abs(trade1.price - trade2.price) / trade1.price
            if price_diff_pct > tolerances.price_tolerance_pct:
                return False, 0.0
            score -= price_diff_pct * 10  # penalty

        # Quantity comparison
        if trade1.quantity > 0:
            qty_diff_pct = abs(trade1.quantity - trade2.quantity) / trade1.quantity
            if qty_diff_pct > tolerances.quantity_tolerance_pct and not (
                tolerances.allow_partial_fills and trade2.quantity <= trade1.quantity
            ):
                return False, 0.0
            if qty_diff_pct > 0:
                score -= qty_diff_pct * 5

        # Time comparison
        time_diff = abs((trade1.timestamp - trade2.timestamp).total_seconds())
        if time_diff > tolerances.time_window_seconds:
            return False, 0.0
        score -= (time_diff / tolerances.time_window_seconds) * 0.2

        confidence = max(0.0, min(1.0, score))
        return True, confidence

    def find_unmatched(
        self, results: list[MatchResult]
    ) -> tuple[list[TradeRecord], list[TradeRecord]]:
        """Find unmatched trades from match results."""
        missing_broker: list[TradeRecord] = []
        missing_internal: list[TradeRecord] = []
        for r in results:
            if r.break_type == BreakType.MISSING_BROKER and r.internal_trade:
                missing_broker.append(r.internal_trade)
            elif r.break_type == BreakType.MISSING_INTERNAL and r.broker_trade:
                missing_internal.append(r.broker_trade)
        return missing_broker, missing_internal

    def batch_reconcile(
        self,
        internal_trades: list[TradeRecord],
        broker_trades: list[TradeRecord],
    ) -> dict:
        """Run batch reconciliation and return summary statistics."""
        results = self.match_trades(internal_trades, broker_trades)
        matched = [r for r in results if r.status == ReconciliationStatus.MATCHED]
        broken = [r for r in results if r.status == ReconciliationStatus.BROKEN]
        total = len(internal_trades) + len(broker_trades)
        return {
            "total_internal": len(internal_trades),
            "total_broker": len(broker_trades),
            "matched": len(matched),
            "broken": len(broken),
            "match_rate": len(matched) / max(len(internal_trades), 1),
            "results": results,
        }

    def get_match_history(self) -> list[MatchResult]:
        """Return all historical match results."""
        return list(self._match_history)

    def _identify_break(
        self, internal: TradeRecord, broker: TradeRecord
    ) -> Optional[BreakType]:
        """Identify the type of break between two trades."""
        if internal.side != broker.side:
            return BreakType.SIDE_MISMATCH
        if internal.price != broker.price:
            return BreakType.PRICE_MISMATCH
        if internal.quantity != broker.quantity:
            return BreakType.QUANTITY_MISMATCH
        time_diff = abs((internal.timestamp - broker.timestamp).total_seconds())
        if time_diff > self.config.tolerances.time_window_seconds:
            return BreakType.TIMING
        return None
