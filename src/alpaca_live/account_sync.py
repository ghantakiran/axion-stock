"""Alpaca Account Synchronization (PRD-139).

Keeps local state in sync with Alpaca via periodic polling.
Tracks positions, balances, orders, and connection health.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional
import asyncio
import logging

from src.alpaca_live.client import (
    AlpacaClient,
    AlpacaAccount,
    AlpacaPosition,
    AlpacaOrder,
)

logger = logging.getLogger(__name__)


@dataclass
class SyncState:
    """Current synchronized account state."""
    account: Optional[AlpacaAccount] = None
    positions: list[AlpacaPosition] = field(default_factory=list)
    open_orders: list[AlpacaOrder] = field(default_factory=list)

    # Derived
    total_equity: float = 0.0
    total_market_value: float = 0.0
    total_unrealized_pnl: float = 0.0
    buying_power: float = 0.0
    position_count: int = 0

    # Timestamps
    last_account_sync: Optional[datetime] = None
    last_position_sync: Optional[datetime] = None
    last_order_sync: Optional[datetime] = None

    # Health
    sync_errors: int = 0
    consecutive_failures: int = 0
    is_healthy: bool = True

    def update_from_account(self, account: AlpacaAccount) -> None:
        """Update state from account data."""
        self.account = account
        self.total_equity = account.equity
        self.buying_power = account.buying_power
        self.last_account_sync = datetime.now(timezone.utc)
        self.consecutive_failures = 0
        self.is_healthy = True

    def update_from_positions(self, positions: list[AlpacaPosition]) -> None:
        """Update state from positions data."""
        self.positions = positions
        self.position_count = len(positions)
        self.total_market_value = sum(p.market_value for p in positions)
        self.total_unrealized_pnl = sum(p.unrealized_pl for p in positions)
        self.last_position_sync = datetime.now(timezone.utc)

    def update_from_orders(self, orders: list[AlpacaOrder]) -> None:
        """Update state from orders data."""
        self.open_orders = [o for o in orders if o.status in ("new", "accepted", "partially_filled")]
        self.last_order_sync = datetime.now(timezone.utc)

    def record_error(self) -> None:
        """Record a sync error."""
        self.sync_errors += 1
        self.consecutive_failures += 1
        if self.consecutive_failures >= 5:
            self.is_healthy = False

    def get_position(self, symbol: str) -> Optional[AlpacaPosition]:
        """Get position by symbol."""
        for p in self.positions:
            if p.symbol == symbol:
                return p
        return None

    @property
    def symbols_held(self) -> list[str]:
        """Get list of symbols with open positions."""
        return [p.symbol for p in self.positions if p.qty > 0]

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "total_equity": self.total_equity,
            "buying_power": self.buying_power,
            "total_market_value": self.total_market_value,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "position_count": self.position_count,
            "open_orders": len(self.open_orders),
            "is_healthy": self.is_healthy,
            "sync_errors": self.sync_errors,
            "last_account_sync": self.last_account_sync.isoformat() if self.last_account_sync else None,
            "last_position_sync": self.last_position_sync.isoformat() if self.last_position_sync else None,
        }


@dataclass
class SyncConfig:
    """Configuration for account synchronization."""
    account_interval: float = 30.0    # seconds between account syncs
    position_interval: float = 10.0   # seconds between position syncs
    order_interval: float = 5.0       # seconds between order syncs
    health_check_interval: float = 60.0
    max_consecutive_failures: int = 10
    enabled: bool = True


# Callback types
SyncCallback = Callable[[SyncState], Any]


class AccountSync:
    """Periodically syncs Alpaca account state.

    Runs background tasks to poll account, positions, and orders
    at configurable intervals.

    Example:
        sync = AccountSync(client, SyncConfig())
        sync.on_state_change(my_callback)
        await sync.start()
        state = sync.state
    """

    def __init__(self, client: AlpacaClient, config: Optional[SyncConfig] = None):
        self._client = client
        self._config = config or SyncConfig()
        self._state = SyncState()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._callbacks: list[SyncCallback] = []

    @property
    def state(self) -> SyncState:
        """Get current synchronized state."""
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    def on_state_change(self, callback: SyncCallback) -> None:
        """Register callback for state changes."""
        self._callbacks.append(callback)

    async def start(self) -> None:
        """Start synchronization tasks."""
        if self._running or not self._config.enabled:
            return

        self._running = True

        # Initial sync
        await self.sync_all()

        # Start periodic tasks
        self._tasks = [
            asyncio.create_task(self._sync_loop(
                self._sync_account, self._config.account_interval
            )),
            asyncio.create_task(self._sync_loop(
                self._sync_positions, self._config.position_interval
            )),
            asyncio.create_task(self._sync_loop(
                self._sync_orders, self._config.order_interval
            )),
        ]

        logger.info("Account sync started")

    async def stop(self) -> None:
        """Stop synchronization tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("Account sync stopped")

    async def sync_all(self) -> SyncState:
        """Perform full synchronization."""
        await self._sync_account()
        await self._sync_positions()
        await self._sync_orders()
        return self._state

    async def _sync_loop(self, sync_fn: Callable, interval: float) -> None:
        """Run a sync function at regular intervals."""
        while self._running:
            try:
                await asyncio.sleep(interval)
                if self._running:
                    await sync_fn()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                self._state.record_error()

    async def _sync_account(self) -> None:
        """Sync account information."""
        try:
            account = await self._client.get_account()
            self._state.update_from_account(account)
            await self._notify_callbacks()
        except Exception as e:
            logger.error(f"Account sync failed: {e}")
            self._state.record_error()

    async def _sync_positions(self) -> None:
        """Sync positions."""
        try:
            positions = await self._client.get_positions()
            self._state.update_from_positions(positions)
            await self._notify_callbacks()
        except Exception as e:
            logger.error(f"Position sync failed: {e}")
            self._state.record_error()

    async def _sync_orders(self) -> None:
        """Sync open orders."""
        try:
            orders = await self._client.get_orders(status="open")
            self._state.update_from_orders(orders)
            await self._notify_callbacks()
        except Exception as e:
            logger.error(f"Order sync failed: {e}")
            self._state.record_error()

    async def _notify_callbacks(self) -> None:
        """Notify all registered callbacks."""
        for cb in self._callbacks:
            try:
                result = cb(self._state)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Sync callback error: {e}")
