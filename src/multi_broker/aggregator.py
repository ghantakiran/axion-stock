"""Portfolio Aggregator -- unified portfolio view across all brokers (PRD-146).

Merges positions from all connected brokers into a single consolidated view,
computing cross-broker exposure, allocation percentages, and total P&L.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import logging

from src.multi_broker.registry import BrokerInfo, BrokerRegistry, BrokerStatus

logger = logging.getLogger(__name__)


# =====================================================================
# Dataclasses
# =====================================================================


@dataclass
class AggregatedPosition:
    """A single symbol's position aggregated across multiple brokers.

    Attributes:
        symbol: Ticker symbol.
        total_qty: Total quantity across all brokers.
        by_broker: Mapping of broker_name -> quantity.
        avg_cost: Weighted average cost basis per share.
        total_market_value: Current market value across all brokers.
        total_pnl: Unrealized P&L across all brokers.
        total_cost_basis: Total cost basis.
        pnl_pct: Percentage P&L.
    """
    symbol: str = ""
    total_qty: float = 0.0
    by_broker: dict[str, float] = field(default_factory=dict)
    avg_cost: float = 0.0
    total_market_value: float = 0.0
    total_pnl: float = 0.0
    total_cost_basis: float = 0.0
    pnl_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "total_qty": self.total_qty,
            "by_broker": self.by_broker,
            "avg_cost": round(self.avg_cost, 4),
            "total_market_value": round(self.total_market_value, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_cost_basis": round(self.total_cost_basis, 2),
            "pnl_pct": round(self.pnl_pct, 2),
        }


@dataclass
class AggregatedPortfolio:
    """Unified portfolio view across all connected brokers.

    Attributes:
        total_value: Total market value of all positions + cash.
        total_pnl: Total unrealized P&L.
        total_cash: Total cash across all brokers.
        positions: List of aggregated positions.
        by_broker: Per-broker summary (value, cash, position_count).
        allocation: Per-broker allocation percentage.
        last_sync: When the portfolio was last synced.
    """
    total_value: float = 0.0
    total_pnl: float = 0.0
    total_cash: float = 0.0
    positions: list[AggregatedPosition] = field(default_factory=list)
    by_broker: dict[str, dict[str, Any]] = field(default_factory=dict)
    allocation: dict[str, float] = field(default_factory=dict)
    last_sync: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "total_value": round(self.total_value, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_cash": round(self.total_cash, 2),
            "position_count": len(self.positions),
            "positions": [p.to_dict() for p in self.positions],
            "by_broker": self.by_broker,
            "allocation": {k: round(v, 2) for k, v in self.allocation.items()},
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
        }


# =====================================================================
# Portfolio Aggregator
# =====================================================================


class PortfolioAggregator:
    """Aggregates positions and account data across all connected brokers.

    Queries each connected broker for accounts and positions, then merges
    them into a unified AggregatedPortfolio with cross-broker exposure
    and allocation tracking.

    Example:
        aggregator = PortfolioAggregator(registry)
        await aggregator.sync_all()
        portfolio = aggregator.get_unified_portfolio()
        exposure = aggregator.get_cross_broker_exposure("AAPL")
    """

    def __init__(self, registry: BrokerRegistry) -> None:
        self._registry = registry
        self._broker_accounts: dict[str, dict] = {}
        self._broker_positions: dict[str, list[dict]] = {}
        self._last_sync: Optional[datetime] = None

    @property
    def last_sync(self) -> Optional[datetime]:
        return self._last_sync

    async def sync_all(self) -> dict[str, bool]:
        """Sync account and position data from all connected brokers.

        Returns:
            Dict mapping broker_name -> success (True/False).
        """
        results: dict[str, bool] = {}
        connected = self._registry.get_connected()

        for broker_info in connected:
            name = broker_info.broker_name
            try:
                adapter = broker_info.adapter
                # Fetch account
                account = await adapter.get_account()
                self._broker_accounts[name] = account if isinstance(account, dict) else {"raw": account}

                # Fetch positions
                positions = await adapter.get_positions()
                if isinstance(positions, list):
                    self._broker_positions[name] = [
                        p if isinstance(p, dict) else {"raw": p} for p in positions
                    ]
                else:
                    self._broker_positions[name] = []

                results[name] = True
                logger.info(f"Synced {name}: {len(self._broker_positions.get(name, []))} positions")
            except Exception as e:
                logger.warning(f"Failed to sync {name}: {e}")
                results[name] = False
                self._registry.update_status(name, BrokerStatus.ERROR, str(e))

        self._last_sync = datetime.now(timezone.utc)
        return results

    def get_unified_portfolio(self) -> AggregatedPortfolio:
        """Build a unified portfolio view from the last sync data.

        Returns:
            AggregatedPortfolio with merged positions, totals, and allocation.
        """
        # Merge positions by symbol
        symbol_map: dict[str, AggregatedPosition] = {}
        broker_summaries: dict[str, dict[str, Any]] = {}

        for broker_name, positions in self._broker_positions.items():
            broker_value = 0.0
            broker_pnl = 0.0

            for pos in positions:
                symbol = pos.get("symbol", pos.get("ticker", "UNKNOWN"))
                qty = float(pos.get("qty", pos.get("quantity", pos.get("size", 0))))
                market_value = float(pos.get("market_value", pos.get("marketValue", 0)))
                cost_basis = float(pos.get("cost_basis", pos.get("costBasis", 0)))
                unrealized_pnl = float(pos.get("unrealized_pnl", pos.get("unrealizedPnl", 0)))
                avg_price = float(pos.get("avg_entry_price", pos.get("average_price", pos.get("avgCost", 0))))

                if symbol not in symbol_map:
                    symbol_map[symbol] = AggregatedPosition(symbol=symbol)

                agg = symbol_map[symbol]
                agg.total_qty += qty
                agg.by_broker[broker_name] = qty
                agg.total_market_value += market_value
                agg.total_pnl += unrealized_pnl
                agg.total_cost_basis += cost_basis

                broker_value += market_value
                broker_pnl += unrealized_pnl

            # Account-level data
            acct = self._broker_accounts.get(broker_name, {})
            broker_cash = float(acct.get("cash", acct.get("usd_balance", 0)))
            broker_equity = float(acct.get("equity", acct.get("total_value_usd", broker_value + broker_cash)))

            broker_summaries[broker_name] = {
                "equity": round(broker_equity, 2),
                "cash": round(broker_cash, 2),
                "positions": len(positions),
                "pnl": round(broker_pnl, 2),
            }

        # Compute weighted average costs
        for agg in symbol_map.values():
            if agg.total_qty > 0 and agg.total_cost_basis > 0:
                agg.avg_cost = agg.total_cost_basis / agg.total_qty
            if agg.total_cost_basis > 0:
                agg.pnl_pct = (agg.total_pnl / agg.total_cost_basis) * 100.0

        # Build portfolio totals
        total_value = sum(s.get("equity", 0) for s in broker_summaries.values())
        total_cash = sum(s.get("cash", 0) for s in broker_summaries.values())
        total_pnl = sum(s.get("pnl", 0) for s in broker_summaries.values())

        # Allocation percentages
        allocation: dict[str, float] = {}
        if total_value > 0:
            for name, summary in broker_summaries.items():
                allocation[name] = (summary.get("equity", 0) / total_value) * 100.0

        return AggregatedPortfolio(
            total_value=total_value,
            total_pnl=total_pnl,
            total_cash=total_cash,
            positions=sorted(symbol_map.values(), key=lambda p: p.total_market_value, reverse=True),
            by_broker=broker_summaries,
            allocation=allocation,
            last_sync=self._last_sync,
        )

    def get_cross_broker_exposure(self, symbol: str) -> dict[str, Any]:
        """Get cross-broker exposure for a specific symbol.

        Args:
            symbol: Ticker symbol.

        Returns:
            Dict with total qty, per-broker breakdown, and concentration.
        """
        exposure: dict[str, float] = {}
        total_qty = 0.0

        for broker_name, positions in self._broker_positions.items():
            for pos in positions:
                pos_symbol = pos.get("symbol", pos.get("ticker", ""))
                if pos_symbol == symbol:
                    qty = float(pos.get("qty", pos.get("quantity", pos.get("size", 0))))
                    exposure[broker_name] = qty
                    total_qty += qty

        # Concentration percentages
        concentration: dict[str, float] = {}
        if total_qty > 0:
            for name, qty in exposure.items():
                concentration[name] = (qty / total_qty) * 100.0

        return {
            "symbol": symbol,
            "total_qty": total_qty,
            "by_broker": exposure,
            "concentration": concentration,
            "broker_count": len(exposure),
        }

    def get_broker_allocation(self) -> dict[str, float]:
        """Get allocation percentage per broker based on equity.

        Returns:
            Dict mapping broker_name -> percentage of total portfolio.
        """
        portfolio = self.get_unified_portfolio()
        return portfolio.allocation
