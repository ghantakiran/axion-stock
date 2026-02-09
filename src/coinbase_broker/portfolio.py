"""Coinbase Crypto Portfolio Tracker (PRD-144).

Tracks crypto holdings, calculates allocation weights, P&L,
and historical portfolio values. Syncs from CoinbaseClient.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import logging
import random

from src.coinbase_broker.client import CoinbaseClient, CoinbaseAccount

logger = logging.getLogger(__name__)


@dataclass
class PortfolioSnapshot:
    """A point-in-time portfolio snapshot."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_value_usd: float = 0.0
    holdings: dict[str, float] = field(default_factory=dict)  # currency -> usd value
    allocation: dict[str, float] = field(default_factory=dict)  # currency -> weight 0-1

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_value_usd": self.total_value_usd,
            "holdings": self.holdings,
            "allocation": self.allocation,
        }


class CryptoPortfolioTracker:
    """Tracks crypto portfolio value, allocation, and P&L.

    Example:
        tracker = CryptoPortfolioTracker(client)
        await tracker.sync_accounts()
        value = tracker.get_total_value_usd()
        alloc = tracker.get_allocation()
    """

    # Demo cost basis for P&L calculation
    DEMO_COST_BASIS: dict[str, float] = {
        "BTC": 82000.0,    # avg buy price per unit
        "ETH": 2800.0,
        "SOL": 150.0,
        "DOGE": 0.25,
        "ADA": 0.70,
        "XRP": 1.80,
    }

    def __init__(self, client: CoinbaseClient):
        self._client = client
        self._accounts: list[CoinbaseAccount] = []
        self._last_sync: Optional[datetime] = None

    @property
    def accounts(self) -> list[CoinbaseAccount]:
        return self._accounts

    @property
    def last_sync(self) -> Optional[datetime]:
        return self._last_sync

    async def sync_accounts(self) -> list[CoinbaseAccount]:
        """Sync accounts from Coinbase API."""
        self._accounts = await self._client.get_accounts()
        self._last_sync = datetime.now(timezone.utc)
        logger.info(f"Synced {len(self._accounts)} Coinbase accounts")
        return self._accounts

    def get_total_value_usd(self) -> float:
        """Get total portfolio value in USD."""
        return sum(a.native_balance_amount for a in self._accounts)

    def get_allocation(self) -> dict[str, float]:
        """Get portfolio allocation as currency -> weight (0-1)."""
        total = self.get_total_value_usd()
        if total <= 0:
            return {}
        result: dict[str, float] = {}
        for a in self._accounts:
            if a.native_balance_amount > 0:
                result[a.currency] = round(a.native_balance_amount / total, 4)
        return result

    def get_pnl(self) -> dict[str, dict[str, float]]:
        """Get unrealized P&L per holding.

        Returns dict of currency -> {"cost_basis", "current_value", "pnl", "pnl_pct"}.
        """
        result: dict[str, dict[str, float]] = {}
        for a in self._accounts:
            if a.currency == "USD" or a.balance <= 0:
                continue
            cost_per_unit = self.DEMO_COST_BASIS.get(a.currency, 0)
            if cost_per_unit <= 0:
                continue
            cost_basis = a.balance * cost_per_unit
            current_value = a.native_balance_amount
            pnl = current_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
            result[a.currency] = {
                "cost_basis": round(cost_basis, 2),
                "current_value": round(current_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        return result

    def get_historical_values(self, days: int = 30) -> list[PortfolioSnapshot]:
        """Get historical portfolio value snapshots (demo data).

        Returns a list of PortfolioSnapshot over the past N days.
        """
        current_total = self.get_total_value_usd()
        if current_total <= 0:
            current_total = 80000.0  # fallback demo value

        rng = random.Random(42)
        snapshots: list[PortfolioSnapshot] = []
        now = datetime.now(timezone.utc)
        value = current_total * 0.90  # start 10% lower

        for i in range(days):
            ts = now - timedelta(days=days - i)
            change = rng.uniform(-0.02, 0.025)
            value = value * (1 + change)
            snapshots.append(PortfolioSnapshot(
                timestamp=ts,
                total_value_usd=round(value, 2),
            ))

        return snapshots

    def get_snapshot(self) -> PortfolioSnapshot:
        """Get current portfolio snapshot."""
        total = self.get_total_value_usd()
        holdings: dict[str, float] = {}
        for a in self._accounts:
            if a.native_balance_amount > 0:
                holdings[a.currency] = a.native_balance_amount

        return PortfolioSnapshot(
            total_value_usd=total,
            holdings=holdings,
            allocation=self.get_allocation(),
        )
