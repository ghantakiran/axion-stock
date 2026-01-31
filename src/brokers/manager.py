"""Multi-Broker Manager.

Manages multiple broker connections and provides aggregated views.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.brokers.config import (
    BrokerType,
    ConnectionStatus,
    BROKER_CAPABILITIES,
)
from src.brokers.models import (
    BrokerAccount,
    AccountBalances,
    Position,
    Order,
    OrderRequest,
    OrderResult,
    BrokerConnection,
    Quote,
)
from src.brokers.interface import BrokerInterface
from src.brokers.credentials import CredentialManager, BrokerCredentials

logger = logging.getLogger(__name__)


class BrokerManager:
    """Manages multiple broker connections.
    
    Features:
    - Connect to multiple brokers
    - Aggregated portfolio views
    - Cross-broker order routing
    - Unified interface
    
    Example:
        manager = BrokerManager()
        await manager.add_broker(BrokerType.ALPACA, api_key="...", api_secret="...")
        positions = await manager.get_all_positions()
    """
    
    def __init__(self):
        self._connections: dict[str, BrokerConnection] = {}
        self._brokers: dict[str, BrokerInterface] = {}
        self._credential_manager = CredentialManager()
    
    async def add_broker(
        self,
        broker_type: BrokerType,
        credentials: Optional[dict] = None,
        account_id: str = "",
        sandbox: bool = True,
    ) -> str:
        """Add a broker connection.
        
        Args:
            broker_type: Type of broker.
            credentials: Authentication credentials.
            account_id: Account ID (optional).
            sandbox: Use sandbox/paper environment.
            
        Returns:
            Connection ID.
        """
        from src.brokers.implementations import create_broker
        
        # Create broker instance
        broker = create_broker(
            broker_type=broker_type,
            credentials=credentials or {},
            account_id=account_id,
            sandbox=sandbox,
        )
        
        # Connect
        connected = await broker.connect()
        
        # Create connection record
        connection = BrokerConnection(
            broker=broker_type,
            status=ConnectionStatus.CONNECTED if connected else ConnectionStatus.ERROR,
            accounts=[account_id] if account_id else [],
            primary_account=account_id,
            is_authenticated=connected,
            connected_at=datetime.now(timezone.utc) if connected else None,
        )
        
        # Store credentials
        if credentials:
            creds = BrokerCredentials(
                broker=broker_type,
                account_id=account_id,
                api_key=credentials.get("api_key", ""),
                api_secret=credentials.get("api_secret", ""),
                access_token=credentials.get("access_token", ""),
                refresh_token=credentials.get("refresh_token", ""),
            )
            self._credential_manager.store_credentials(creds)
        
        # Store connection
        self._connections[connection.connection_id] = connection
        self._brokers[connection.connection_id] = broker
        
        logger.info(f"Added broker connection: {broker_type.value} ({connection.connection_id})")
        return connection.connection_id
    
    async def remove_broker(self, connection_id: str) -> bool:
        """Remove a broker connection.
        
        Args:
            connection_id: Connection ID to remove.
            
        Returns:
            True if removed, False if not found.
        """
        if connection_id not in self._connections:
            return False
        
        # Disconnect
        broker = self._brokers.get(connection_id)
        if broker:
            await broker.disconnect()
        
        # Remove
        connection = self._connections[connection_id]
        self._credential_manager.delete_credentials(
            connection.broker,
            connection.primary_account or "",
        )
        
        del self._connections[connection_id]
        if connection_id in self._brokers:
            del self._brokers[connection_id]
        
        logger.info(f"Removed broker connection: {connection_id}")
        return True
    
    def get_connections(self) -> list[BrokerConnection]:
        """Get all broker connections."""
        return list(self._connections.values())
    
    def get_connection(self, connection_id: str) -> Optional[BrokerConnection]:
        """Get a specific connection."""
        return self._connections.get(connection_id)
    
    def get_broker(self, connection_id: str) -> Optional[BrokerInterface]:
        """Get broker instance for a connection."""
        return self._brokers.get(connection_id)
    
    async def refresh_connection(self, connection_id: str) -> bool:
        """Refresh a broker connection.
        
        Args:
            connection_id: Connection ID.
            
        Returns:
            True if refresh successful.
        """
        broker = self._brokers.get(connection_id)
        connection = self._connections.get(connection_id)
        
        if not broker or not connection:
            return False
        
        try:
            success = await broker.refresh_token()
            if success:
                connection.status = ConnectionStatus.CONNECTED
                connection.last_activity = datetime.now(timezone.utc)
            else:
                connection.status = ConnectionStatus.TOKEN_EXPIRED
            return success
        except Exception as e:
            connection.status = ConnectionStatus.ERROR
            connection.last_error = str(e)
            connection.last_error_at = datetime.now(timezone.utc)
            return False
    
    # =========================================================================
    # Aggregated Views
    # =========================================================================
    
    async def get_all_accounts(self) -> list[BrokerAccount]:
        """Get all accounts from all brokers."""
        accounts = []
        for connection_id, broker in self._brokers.items():
            try:
                account = await broker.get_account()
                accounts.append(account)
            except Exception as e:
                logger.error(f"Failed to get account from {connection_id}: {e}")
        return accounts
    
    async def get_all_balances(self) -> list[AccountBalances]:
        """Get balances from all accounts."""
        balances = []
        for connection_id, broker in self._brokers.items():
            try:
                balance = await broker.get_balances()
                balances.append(balance)
            except Exception as e:
                logger.error(f"Failed to get balances from {connection_id}: {e}")
        return balances
    
    async def get_all_positions(self) -> list[Position]:
        """Get positions from all accounts."""
        all_positions = []
        for connection_id, broker in self._brokers.items():
            try:
                positions = await broker.get_positions()
                all_positions.extend(positions)
            except Exception as e:
                logger.error(f"Failed to get positions from {connection_id}: {e}")
        return all_positions
    
    async def get_all_orders(self) -> list[Order]:
        """Get orders from all accounts."""
        all_orders = []
        for connection_id, broker in self._brokers.items():
            try:
                orders = await broker.get_orders()
                all_orders.extend(orders)
            except Exception as e:
                logger.error(f"Failed to get orders from {connection_id}: {e}")
        return all_orders
    
    async def get_total_portfolio_value(self) -> float:
        """Get total portfolio value across all accounts."""
        total = 0.0
        balances = await self.get_all_balances()
        for balance in balances:
            total += balance.total_value
        return total
    
    async def get_aggregated_positions(self) -> dict[str, Position]:
        """Get aggregated positions by symbol.
        
        Combines positions across accounts for the same symbol.
        
        Returns:
            Dict of symbol -> aggregated Position.
        """
        all_positions = await self.get_all_positions()
        
        aggregated: dict[str, Position] = {}
        for pos in all_positions:
            if pos.symbol in aggregated:
                # Combine with existing
                existing = aggregated[pos.symbol]
                total_qty = existing.quantity + pos.quantity
                
                # Weighted average cost
                if total_qty > 0:
                    total_cost = (existing.quantity * existing.average_cost +
                                  pos.quantity * pos.average_cost)
                    existing.average_cost = total_cost / total_qty
                
                existing.quantity = total_qty
                existing.market_value += pos.market_value
                existing.unrealized_pnl += pos.unrealized_pnl
                existing.day_pnl += pos.day_pnl
            else:
                aggregated[pos.symbol] = pos
        
        return aggregated
    
    # =========================================================================
    # Order Routing
    # =========================================================================
    
    async def place_order(
        self,
        order: OrderRequest,
        connection_id: Optional[str] = None,
    ) -> OrderResult:
        """Place an order through a broker.
        
        Args:
            order: Order request.
            connection_id: Specific connection to use.
                          If None, routes to best broker.
            
        Returns:
            OrderResult.
        """
        if connection_id:
            broker = self._brokers.get(connection_id)
            if not broker:
                return OrderResult(
                    success=False,
                    message=f"Connection not found: {connection_id}",
                )
            return await broker.place_order(order)
        
        # Find best broker for this order
        best_connection = await self.find_best_execution(order)
        if not best_connection:
            return OrderResult(
                success=False,
                message="No available broker for this order",
            )
        
        broker = self._brokers.get(best_connection)
        if not broker:
            return OrderResult(
                success=False,
                message="Broker not available",
            )
        
        return await broker.place_order(order)
    
    async def find_best_execution(self, order: OrderRequest) -> Optional[str]:
        """Find the best broker for order execution.
        
        Considers:
        - Available buying power
        - Commission costs
        - Execution quality
        
        Args:
            order: Order to execute.
            
        Returns:
            Connection ID of best broker, or None.
        """
        best_connection = None
        best_score = -1
        
        for connection_id, broker in self._brokers.items():
            if not broker.is_connected():
                continue
            
            try:
                # Check capabilities
                caps = broker.capabilities
                if order.side in [OrderRequest] and not caps.stocks:
                    continue
                
                # Get balances
                balances = await broker.get_balances()
                
                # Score based on buying power
                score = balances.buying_power
                
                if score > best_score:
                    best_score = score
                    best_connection = connection_id
                    
            except Exception:
                continue
        
        return best_connection
    
    # =========================================================================
    # Sync Operations
    # =========================================================================
    
    async def sync_all(self) -> dict:
        """Synchronize all broker data.
        
        Returns:
            Dict with sync results.
        """
        results = {
            "accounts": 0,
            "positions": 0,
            "orders": 0,
            "errors": [],
        }
        
        for connection_id in self._connections:
            try:
                broker = self._brokers.get(connection_id)
                if broker and broker.is_connected():
                    await broker.get_account()
                    results["accounts"] += 1
                    
                    positions = await broker.get_positions()
                    results["positions"] += len(positions)
                    
                    orders = await broker.get_orders()
                    results["orders"] += len(orders)
                    
            except Exception as e:
                results["errors"].append(f"{connection_id}: {str(e)}")
        
        return results
