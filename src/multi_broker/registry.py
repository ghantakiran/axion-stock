"""Broker Registry -- central registry for all broker connections (PRD-146).

Provides a Protocol-based adapter interface, a BrokerInfo metadata wrapper,
and a BrokerRegistry that tracks connected/disconnected brokers with lookup
by asset type and scoring for best-fit selection.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable
import logging

logger = logging.getLogger(__name__)


# =====================================================================
# Broker Adapter Protocol
# =====================================================================


@runtime_checkable
class BrokerAdapter(Protocol):
    """Protocol that each broker integration must satisfy.

    Implementations: AlpacaClient, RobinhoodClient, CoinbaseClient, SchwabClient.
    """

    async def connect(self) -> bool:
        """Establish connection to the broker API."""
        ...

    async def disconnect(self) -> None:
        """Close connection and release resources."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the broker is currently connected."""
        ...

    async def get_account(self) -> dict:
        """Get account summary (equity, cash, buying_power, etc.)."""
        ...

    async def get_positions(self) -> list[dict]:
        """Get current open positions as list of dicts."""
        ...

    async def place_order(self, order: dict) -> dict:
        """Submit an order and return order confirmation dict."""
        ...

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order by ID."""
        ...

    async def get_quote(self, symbol: str) -> dict:
        """Get a real-time quote for a single symbol."""
        ...

    @property
    def supported_assets(self) -> list[str]:
        """List of asset types this broker supports (stock, crypto, options, mutual_funds)."""
        ...


# =====================================================================
# Enums & Dataclasses
# =====================================================================


class BrokerStatus(str, Enum):
    """Connection status of a registered broker."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


# Default fee schedules per broker (basis points or flat per trade)
DEFAULT_FEE_SCHEDULES: dict[str, dict[str, float]] = {
    "alpaca": {"stock_commission": 0.0, "options_per_contract": 0.65, "base_fee": 0.0},
    "robinhood": {"stock_commission": 0.0, "options_per_contract": 0.0, "crypto_spread_bps": 50, "base_fee": 0.0},
    "coinbase": {"crypto_fee_pct": 0.60, "advanced_fee_pct": 0.40, "base_fee": 0.0},
    "schwab": {"stock_commission": 0.0, "options_per_contract": 0.65, "mutual_fund_fee": 0.0, "base_fee": 0.0},
}

# Default supported assets per broker
DEFAULT_SUPPORTED_ASSETS: dict[str, list[str]] = {
    "alpaca": ["stock", "options"],
    "robinhood": ["stock", "crypto", "options"],
    "coinbase": ["crypto"],
    "schwab": ["stock", "options", "mutual_funds"],
}

# Default latency estimates (ms)
DEFAULT_LATENCY: dict[str, float] = {
    "alpaca": 50.0,
    "robinhood": 80.0,
    "coinbase": 60.0,
    "schwab": 90.0,
}


@dataclass
class BrokerInfo:
    """Metadata wrapper around a registered broker adapter."""
    broker_name: str
    adapter: Any  # BrokerAdapter protocol instance
    status: BrokerStatus = BrokerStatus.DISCONNECTED
    supported_assets: list[str] = field(default_factory=list)
    fee_schedule: dict[str, float] = field(default_factory=dict)
    latency_ms: float = 100.0
    priority: int = 0  # lower = higher priority
    last_sync: Optional[datetime] = None
    error_message: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "broker_name": self.broker_name,
            "status": self.status.value,
            "supported_assets": self.supported_assets,
            "fee_schedule": self.fee_schedule,
            "latency_ms": self.latency_ms,
            "priority": self.priority,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "error_message": self.error_message,
        }


# =====================================================================
# Broker Registry
# =====================================================================


class BrokerRegistry:
    """Central registry for all broker connections.

    Supports registration, unregistration, lookup by asset type,
    and best-fit scoring for order routing decisions.

    Example:
        registry = BrokerRegistry()
        registry.register("alpaca", alpaca_adapter)
        connected = registry.get_connected()
        crypto_brokers = registry.get_by_asset("crypto")
    """

    def __init__(self) -> None:
        self._brokers: dict[str, BrokerInfo] = {}

    @property
    def brokers(self) -> dict[str, BrokerInfo]:
        """All registered brokers."""
        return dict(self._brokers)

    def register(
        self,
        name: str,
        adapter: Any,
        supported_assets: Optional[list[str]] = None,
        fee_schedule: Optional[dict[str, float]] = None,
        latency_ms: Optional[float] = None,
        priority: int = 0,
    ) -> BrokerInfo:
        """Register a broker adapter.

        Args:
            name: Unique broker identifier (e.g. "alpaca", "schwab").
            adapter: Object satisfying BrokerAdapter protocol.
            supported_assets: Override default asset types.
            fee_schedule: Override default fee schedule.
            latency_ms: Override default latency estimate.
            priority: Priority rank (lower = higher priority).

        Returns:
            The created BrokerInfo.

        Raises:
            ValueError: If a broker with this name is already registered.
        """
        if name in self._brokers:
            raise ValueError(f"Broker '{name}' is already registered")

        assets = supported_assets or DEFAULT_SUPPORTED_ASSETS.get(name, ["stock"])
        fees = fee_schedule or DEFAULT_FEE_SCHEDULES.get(name, {"base_fee": 0.0})
        latency = latency_ms if latency_ms is not None else DEFAULT_LATENCY.get(name, 100.0)

        # Detect connection status from adapter
        status = BrokerStatus.DISCONNECTED
        if hasattr(adapter, "is_connected"):
            try:
                if adapter.is_connected:
                    status = BrokerStatus.CONNECTED
            except Exception:
                status = BrokerStatus.ERROR

        info = BrokerInfo(
            broker_name=name,
            adapter=adapter,
            status=status,
            supported_assets=assets,
            fee_schedule=fees,
            latency_ms=latency,
            priority=priority,
        )
        self._brokers[name] = info
        logger.info(f"Registered broker: {name} (assets={assets}, status={status.value})")
        return info

    def unregister(self, name: str) -> bool:
        """Unregister a broker by name.

        Returns True if the broker was found and removed, False otherwise.
        """
        if name in self._brokers:
            del self._brokers[name]
            logger.info(f"Unregistered broker: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[BrokerInfo]:
        """Get a broker by name, or None if not found."""
        return self._brokers.get(name)

    def get_connected(self) -> list[BrokerInfo]:
        """Get all brokers with CONNECTED status."""
        return [b for b in self._brokers.values() if b.status == BrokerStatus.CONNECTED]

    def get_by_asset(self, asset_type: str) -> list[BrokerInfo]:
        """Get all connected brokers supporting a given asset type.

        Args:
            asset_type: One of "stock", "crypto", "options", "mutual_funds".

        Returns:
            List of BrokerInfo for connected brokers supporting the asset.
        """
        return [
            b for b in self._brokers.values()
            if b.status == BrokerStatus.CONNECTED and asset_type in b.supported_assets
        ]

    def get_best_for(
        self,
        asset_type: str,
        criteria: str = "cost",
    ) -> Optional[BrokerInfo]:
        """Get the best broker for an asset type using the given criteria.

        Criteria:
            - "cost": lowest estimated fee
            - "speed": lowest latency
            - "priority": lowest priority number (user-defined rank)

        Args:
            asset_type: Asset type to match.
            criteria: Scoring criteria.

        Returns:
            Best BrokerInfo or None if no brokers support the asset.
        """
        candidates = self.get_by_asset(asset_type)
        if not candidates:
            return None

        if criteria == "cost":
            return min(candidates, key=lambda b: b.fee_schedule.get("base_fee", 0.0))
        elif criteria == "speed":
            return min(candidates, key=lambda b: b.latency_ms)
        elif criteria == "priority":
            return min(candidates, key=lambda b: b.priority)
        else:
            # Default: sort by priority
            return min(candidates, key=lambda b: b.priority)

    def update_status(self, name: str, status: BrokerStatus, error: str = "") -> None:
        """Update the connection status of a broker."""
        if name in self._brokers:
            self._brokers[name].status = status
            self._brokers[name].error_message = error
            if status == BrokerStatus.CONNECTED:
                self._brokers[name].last_sync = datetime.now(timezone.utc)
            logger.info(f"Broker {name} status -> {status.value}")

    def status_summary(self) -> dict[str, Any]:
        """Get a summary of all broker statuses.

        Returns:
            Dictionary with total, connected, disconnected counts and per-broker details.
        """
        connected = [b for b in self._brokers.values() if b.status == BrokerStatus.CONNECTED]
        disconnected = [b for b in self._brokers.values() if b.status == BrokerStatus.DISCONNECTED]
        errored = [b for b in self._brokers.values() if b.status == BrokerStatus.ERROR]

        return {
            "total": len(self._brokers),
            "connected": len(connected),
            "disconnected": len(disconnected),
            "errored": len(errored),
            "brokers": {name: info.to_dict() for name, info in self._brokers.items()},
        }
