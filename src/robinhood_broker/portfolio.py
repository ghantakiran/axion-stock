"""Robinhood Portfolio Tracker (PRD-143).

Tracks positions, calculates portfolio metrics, allocation weights,
and provides historical value snapshots.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta, date
from typing import Any, Optional
import logging

from src.robinhood_broker.client import RobinhoodClient, RobinhoodPosition

logger = logging.getLogger(__name__)


# =====================================================================
# Portfolio Snapshot
# =====================================================================


@dataclass
class PortfolioSnapshot:
    """A point-in-time portfolio snapshot."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_value: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    unrealized_pnl: float = 0.0
    position_count: int = 0

    def to_dict(self) -> dict:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


# =====================================================================
# Portfolio Tracker
# =====================================================================


class PortfolioTracker:
    """Tracks Robinhood portfolio state, positions, and performance.

    Example:
        client = RobinhoodClient(config)
        client.connect()
        tracker = PortfolioTracker(client)
        tracker.sync_positions()
        print(tracker.get_total_value())
        print(tracker.get_allocation())
    """

    def __init__(self, client: Optional[RobinhoodClient] = None):
        self._client = client
        self._positions: list[RobinhoodPosition] = []
        self._cash: float = 0.0
        self._equity: float = 0.0
        self._last_sync: Optional[datetime] = None
        self._snapshots: list[PortfolioSnapshot] = []

    @property
    def positions(self) -> list[RobinhoodPosition]:
        return list(self._positions)

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def last_sync(self) -> Optional[datetime]:
        return self._last_sync

    def sync_positions(self) -> None:
        """Synchronize positions and account data from the API."""
        if not self._client:
            self._load_demo_data()
            return

        try:
            account = self._client.get_account()
            self._cash = account.cash
            self._equity = account.equity
        except Exception as e:
            logger.warning(f"Failed to sync account: {e}")

        try:
            self._positions = self._client.get_positions()
        except Exception as e:
            logger.warning(f"Failed to sync positions: {e}")

        self._last_sync = datetime.now(timezone.utc)

        # Record snapshot
        snapshot = PortfolioSnapshot(
            timestamp=self._last_sync,
            total_value=self.get_total_value(),
            cash=self._cash,
            positions_value=sum(p.market_value for p in self._positions),
            unrealized_pnl=self.get_daily_pnl(),
            position_count=len(self._positions),
        )
        self._snapshots.append(snapshot)
        logger.info(f"Portfolio synced: {len(self._positions)} positions, total=${self.get_total_value():,.2f}")

    def get_total_value(self) -> float:
        """Get total portfolio value (positions + cash)."""
        positions_value = sum(p.market_value for p in self._positions)
        return round(positions_value + self._cash, 2)

    def get_daily_pnl(self) -> float:
        """Get total unrealized P&L across all positions."""
        return round(sum(p.unrealized_pnl for p in self._positions), 2)

    def get_allocation(self) -> dict[str, float]:
        """Get portfolio allocation as symbol -> weight (0.0 to 1.0).

        Includes 'CASH' entry for uninvested cash.
        """
        total = self.get_total_value()
        if total <= 0:
            return {}

        allocation: dict[str, float] = {}
        for p in self._positions:
            weight = p.market_value / total
            allocation[p.symbol] = round(weight, 4)

        if self._cash > 0:
            allocation["CASH"] = round(self._cash / total, 4)

        return allocation

    def get_history(self, days: int = 30) -> list[PortfolioSnapshot]:
        """Get historical portfolio snapshots.

        If real snapshots exist, returns them. Otherwise generates
        demo history for display purposes.
        """
        if self._snapshots:
            return self._snapshots[-days:]

        return self._generate_demo_history(days)

    def get_position_summary(self) -> list[dict]:
        """Get summary of all positions as list of dicts."""
        return [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_cost": p.average_cost,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "pnl_pct": p.unrealized_pnl_pct,
                "weight": round(p.market_value / self.get_total_value(), 4)
                    if self.get_total_value() > 0 else 0.0,
            }
            for p in self._positions
        ]

    # ── Demo Data ────────────────────────────────────────────────────

    def _load_demo_data(self) -> None:
        """Load demo portfolio data."""
        self._cash = 45000.0
        self._equity = 92350.0
        self._positions = [
            RobinhoodPosition(
                symbol="AAPL", instrument_id="instr_aapl",
                quantity=100, average_cost=152.30,
                current_price=187.50, market_value=18750.0,
                unrealized_pnl=3520.0, unrealized_pnl_pct=23.11,
                side="long",
            ),
            RobinhoodPosition(
                symbol="NVDA", instrument_id="instr_nvda",
                quantity=25, average_cost=480.00,
                current_price=624.00, market_value=15600.0,
                unrealized_pnl=3600.0, unrealized_pnl_pct=30.0,
                side="long",
            ),
            RobinhoodPosition(
                symbol="TSLA", instrument_id="instr_tsla",
                quantity=40, average_cost=220.50,
                current_price=325.00, market_value=13000.0,
                unrealized_pnl=4180.0, unrealized_pnl_pct=47.39,
                side="long",
            ),
        ]
        self._last_sync = datetime.now(timezone.utc)

    def _generate_demo_history(self, days: int) -> list[PortfolioSnapshot]:
        """Generate realistic demo portfolio history."""
        import random
        random.seed(42)

        snapshots = []
        base_value = 85000.0
        base_cash = 45000.0
        now = datetime.now(timezone.utc)

        for i in range(days):
            dt = now - timedelta(days=days - i - 1)
            daily_return = random.uniform(-0.015, 0.018)
            base_value *= (1 + daily_return)
            positions_value = base_value - base_cash
            pnl = positions_value * random.uniform(-0.02, 0.03)

            snapshots.append(PortfolioSnapshot(
                timestamp=dt,
                total_value=round(base_value, 2),
                cash=base_cash,
                positions_value=round(positions_value, 2),
                unrealized_pnl=round(pnl, 2),
                position_count=3,
            ))

        return snapshots
