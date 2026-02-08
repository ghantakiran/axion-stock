"""Bid-ask spread analysis."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict

from src.liquidity.config import SpreadComponent
from src.liquidity.models import SpreadSnapshot


class SpreadAnalyzer:
    """Analyzes bid-ask spreads."""

    def __init__(self):
        # symbol -> list of snapshots
        self._snapshots: dict[str, list[SpreadSnapshot]] = defaultdict(list)

    def record_spread(
        self,
        symbol: str,
        bid_price: float,
        ask_price: float,
        bid_size: int = 0,
        ask_size: int = 0,
    ) -> SpreadSnapshot:
        """Record a bid-ask spread snapshot."""
        snapshot = SpreadSnapshot(
            symbol=symbol,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
        )

        self._snapshots[symbol].append(snapshot)
        return snapshot

    def get_current_spread(self, symbol: str) -> Optional[SpreadSnapshot]:
        """Get most recent spread snapshot."""
        snapshots = self._snapshots.get(symbol, [])
        return snapshots[-1] if snapshots else None

    def get_spread_history(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[SpreadSnapshot]:
        """Get spread history."""
        return self._snapshots.get(symbol, [])[-limit:]

    def get_average_spread(
        self,
        symbol: str,
        periods: int = 20,
    ) -> Optional[float]:
        """Get average spread in bps over recent periods."""
        snapshots = self._snapshots.get(symbol, [])
        if not snapshots:
            return None

        recent = snapshots[-periods:]
        return sum(s.spread_bps for s in recent) / len(recent)

    def get_spread_statistics(self, symbol: str) -> dict:
        """Get comprehensive spread statistics."""
        snapshots = self._snapshots.get(symbol, [])
        if not snapshots:
            return {"symbol": symbol, "data_points": 0}

        spreads_bps = [s.spread_bps for s in snapshots]
        spreads = [s.spread for s in snapshots]

        avg_bps = sum(spreads_bps) / len(spreads_bps)
        min_bps = min(spreads_bps)
        max_bps = max(spreads_bps)

        # Calculate standard deviation
        variance = sum((s - avg_bps) ** 2 for s in spreads_bps) / len(spreads_bps)
        std_bps = variance ** 0.5

        # Bid-ask imbalance
        imbalances = []
        for s in snapshots:
            total = s.bid_size + s.ask_size
            if total > 0:
                imbalances.append((s.bid_size - s.ask_size) / total)

        avg_imbalance = sum(imbalances) / len(imbalances) if imbalances else 0

        return {
            "symbol": symbol,
            "data_points": len(snapshots),
            "avg_spread_bps": avg_bps,
            "min_spread_bps": min_bps,
            "max_spread_bps": max_bps,
            "std_spread_bps": std_bps,
            "avg_spread_dollars": sum(spreads) / len(spreads),
            "avg_bid_ask_imbalance": avg_imbalance,
            "current_spread_bps": spreads_bps[-1],
            "spread_widening": spreads_bps[-1] > avg_bps * 1.5 if spreads_bps else False,
        }

    def decompose_spread(
        self,
        symbol: str,
        volatility: float = 0.02,
        informed_fraction: float = 0.2,
    ) -> dict[str, float]:
        """Decompose spread into components."""
        current = self.get_current_spread(symbol)
        if not current:
            return {}

        total_spread_bps = current.spread_bps

        # Simple decomposition model
        # Adverse selection: proportion due to informed traders
        adverse_selection = total_spread_bps * informed_fraction * (1 + volatility * 10)

        # Order processing: fixed cost component
        order_processing = max(1.0, total_spread_bps * 0.2)

        # Inventory: remainder
        inventory = max(0, total_spread_bps - adverse_selection - order_processing)

        return {
            SpreadComponent.ADVERSE_SELECTION.value: adverse_selection,
            SpreadComponent.INVENTORY.value: inventory,
            SpreadComponent.ORDER_PROCESSING.value: order_processing,
            "total_spread_bps": total_spread_bps,
        }

    def detect_spread_anomalies(
        self,
        symbol: str,
        threshold_multiplier: float = 2.0,
    ) -> list[dict]:
        """Detect unusual spread widening events."""
        snapshots = self._snapshots.get(symbol, [])
        if len(snapshots) < 20:
            return []

        spreads = [s.spread_bps for s in snapshots]
        avg = sum(spreads) / len(spreads)
        variance = sum((s - avg) ** 2 for s in spreads) / len(spreads)
        std = variance ** 0.5

        threshold = avg + std * threshold_multiplier
        anomalies = []

        for snap in snapshots:
            if snap.spread_bps > threshold:
                anomalies.append({
                    "timestamp": snap.timestamp.isoformat(),
                    "spread_bps": snap.spread_bps,
                    "avg_spread_bps": avg,
                    "z_score": (snap.spread_bps - avg) / std if std > 0 else 0,
                })

        return anomalies

    def get_stats(self) -> dict:
        """Get analyzer statistics."""
        total = sum(len(snaps) for snaps in self._snapshots.values())
        return {
            "total_snapshots": total,
            "symbols_tracked": len(self._snapshots),
            "avg_snapshots_per_symbol": total / len(self._snapshots) if self._snapshots else 0,
        }
