"""Active position lifecycle management.

Solves three critical production gaps:

1. **Frozen prices**: Position.current_price is set at entry and never
   updated, making unrealized P&L and exit decisions stale.
   LifecycleManager.update_prices() refreshes all open positions.

2. **Exit monitor not invoked**: ExitMonitor.check_all() exists but
   nothing calls it periodically. LifecycleManager.check_exits() runs
   the exit monitor across all open positions.

3. **No graceful shutdown**: The kill switch blocks new signals but
   doesn't close existing positions. emergency_close_all() closes
   everything and activates the kill switch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

import pandas as pd

from src.ema_signals.clouds import CloudState
from src.trade_executor.executor import Position
from src.trade_executor.exit_monitor import ExitMonitor, ExitSignal

if TYPE_CHECKING:
    from src.bot_pipeline.orchestrator import BotOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class PortfolioSnapshot:
    """Real-time portfolio summary."""

    timestamp: datetime
    open_positions: int
    total_unrealized_pnl: float
    total_exposure: float
    daily_realized_pnl: float
    positions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open_positions": self.open_positions,
            "total_unrealized_pnl": round(self.total_unrealized_pnl, 2),
            "total_exposure": round(self.total_exposure, 2),
            "daily_realized_pnl": round(self.daily_realized_pnl, 2),
            "positions": self.positions,
        }


class LifecycleManager:
    """Manages the active lifecycle of open positions.

    Bridges the gap between position creation (BotOrchestrator) and
    position monitoring (ExitMonitor) by providing:
    - Price updates to keep unrealized P&L accurate
    - Periodic exit checks across all positions
    - Emergency close-all for graceful shutdown
    - Portfolio snapshot for real-time monitoring

    Args:
        orchestrator: The BotOrchestrator holding open positions.
        exit_monitor: ExitMonitor for checking exit conditions.

    Example:
        lifecycle = LifecycleManager(orchestrator, exit_monitor)

        # On every price tick:
        lifecycle.update_prices({"AAPL": 195.50, "NVDA": 880.00})

        # Periodically (e.g. every 30 seconds):
        exits = lifecycle.check_exits(price_map)
        closed = lifecycle.execute_exits(exits)

        # On shutdown signal:
        lifecycle.emergency_close_all("Graceful shutdown")
    """

    def __init__(
        self,
        orchestrator: BotOrchestrator,
        exit_monitor: Optional[ExitMonitor] = None,
    ) -> None:
        self._orch = orchestrator
        self._exit_monitor = exit_monitor or ExitMonitor(
            orchestrator.config.executor_config
        )

    def update_prices(self, price_map: dict[str, float]) -> int:
        """Update current_price on all open positions.

        Args:
            price_map: Mapping of ticker -> latest price.

        Returns:
            Number of positions updated.
        """
        updated = 0
        with self._orch._lock:
            for pos in self._orch.positions:
                if pos.ticker in price_map:
                    pos.current_price = price_map[pos.ticker]
                    updated += 1
        if updated:
            logger.debug("Updated prices on %d positions", updated)
        return updated

    def check_exits(
        self,
        price_map: dict[str, float],
        cloud_states_map: Optional[dict[str, list[CloudState]]] = None,
        bars_map: Optional[dict[str, pd.DataFrame]] = None,
    ) -> list[ExitSignal]:
        """Run exit monitor on all open positions.

        Args:
            price_map: Current prices by ticker.
            cloud_states_map: Optional cloud states by ticker.
            bars_map: Optional OHLCV bars by ticker.

        Returns:
            List of ExitSignal for positions that should be closed.
        """
        exits: list[ExitSignal] = []

        # Update prices first
        self.update_prices(price_map)

        with self._orch._lock:
            positions_copy = list(self._orch.positions)

        for pos in positions_copy:
            current_price = price_map.get(pos.ticker, pos.current_price)
            clouds = (cloud_states_map or {}).get(pos.ticker)
            bars = (bars_map or {}).get(pos.ticker)

            exit_sig = self._exit_monitor.check_all(
                position=pos,
                current_price=current_price,
                cloud_states=clouds,
                bars=bars,
            )
            if exit_sig:
                exits.append(exit_sig)

        if exits:
            logger.info(
                "Exit signals detected: %s",
                [(e.ticker, e.exit_type) for e in exits],
            )
        return exits

    def execute_exits(
        self,
        exits: list[ExitSignal],
        price_map: Optional[dict[str, float]] = None,
    ) -> list[Position]:
        """Close positions for each exit signal.

        Args:
            exits: Exit signals from check_exits().
            price_map: Current prices for exit pricing.

        Returns:
            List of closed Position objects.
        """
        closed: list[Position] = []
        price_map = price_map or {}

        for exit_sig in exits:
            exit_price = price_map.get(exit_sig.ticker, 0.0)
            pos = self._orch.close_position(
                ticker=exit_sig.ticker,
                exit_reason=f"{exit_sig.exit_type}: {exit_sig.reason}",
                exit_price=exit_price,
            )
            if pos:
                closed.append(pos)

        return closed

    def emergency_close_all(self, reason: str) -> list[Position]:
        """Close all open positions and activate kill switch.

        Used for graceful shutdown or emergency situations.

        Args:
            reason: Why the emergency close was triggered.

        Returns:
            List of closed Position objects.
        """
        logger.critical("EMERGENCY CLOSE ALL: %s", reason)
        closed: list[Position] = []

        with self._orch._lock:
            tickers = [p.ticker for p in self._orch.positions]

        for ticker in tickers:
            pos = self._orch.close_position(
                ticker=ticker,
                exit_reason=f"emergency_close: {reason}",
            )
            if pos:
                closed.append(pos)

        # Activate kill switch after closing all positions
        self._orch._state.activate_kill_switch(f"Emergency close: {reason}")

        logger.critical(
            "Emergency close complete: %d positions closed, kill switch activated",
            len(closed),
        )
        return closed

    def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        """Get real-time portfolio summary.

        Returns:
            PortfolioSnapshot with current P&L and exposure data.
        """
        with self._orch._lock:
            positions = list(self._orch.positions)
            daily_pnl = self._orch._state.daily_pnl

        total_unrealized = sum(p.unrealized_pnl for p in positions)
        total_exposure = sum(abs(p.shares * p.current_price) for p in positions)

        return PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            open_positions=len(positions),
            total_unrealized_pnl=total_unrealized,
            total_exposure=total_exposure,
            daily_realized_pnl=daily_pnl,
            positions=[p.to_dict() for p in positions],
        )
