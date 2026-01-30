"""Alpaca Brokerage Integration - Live and paper trading via Alpaca API.

Features:
- Commission-free stock trading
- Paper trading environment
- Fractional shares support
- Real-time streaming via WebSocket
- Full REST API coverage

Requires: alpaca-trade-api package
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from src.execution.interfaces import (
    BrokerInterface,
    BrokerError,
    InsufficientFundsError,
    OrderValidationError,
    MarketClosedError,
)
from src.execution.models import (
    AccountInfo,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    OrderTimeInForce,
    Position,
    Trade,
)

logger = logging.getLogger(__name__)


# Alpaca API URLs
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_URL = "https://api.alpaca.markets"
ALPACA_DATA_URL = "https://data.alpaca.markets"


class AlpacaBroker(BrokerInterface):
    """Alpaca brokerage integration for live and paper trading.
    
    Example:
        broker = AlpacaBroker(
            api_key="your-api-key",
            secret_key="your-secret-key",
            paper=True,  # Use paper trading
        )
        await broker.connect()
        
        # Get account info
        account = await broker.get_account()
        print(f"Buying power: ${account.buying_power:,.2f}")
        
        # Submit order
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            limit_price=150.00,
        )
        result = await broker.submit_order(order)
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper: bool = True,
    ):
        """Initialize Alpaca broker.
        
        Args:
            api_key: Alpaca API key.
            secret_key: Alpaca secret key.
            paper: Use paper trading if True, live trading if False.
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.base_url = ALPACA_PAPER_URL if paper else ALPACA_LIVE_URL
        
        self._api = None
        self._stream = None
        self._connected = False
        
        # Callbacks for streaming
        self._order_callbacks: list[Callable[[Order], None]] = []
        self._position_callbacks: list[Callable[[Position], None]] = []
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    async def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            # Import here to avoid requiring alpaca-trade-api for paper-only usage
            from alpaca.trading.client import TradingClient
            
            self._api = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper,
            )
            
            # Test connection by fetching account
            account = self._api.get_account()
            self._connected = True
            
            logger.info(
                "Connected to Alpaca %s trading. Account: %s, Equity: $%s",
                "paper" if self.paper else "live",
                account.account_number,
                account.equity,
            )
            return True
            
        except ImportError:
            logger.error(
                "alpaca-py package not installed. "
                "Install with: pip install alpaca-py"
            )
            return False
        except Exception as e:
            logger.error("Failed to connect to Alpaca: %s", e)
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Alpaca."""
        if self._stream:
            await self._stream.close()
            self._stream = None
        self._api = None
        self._connected = False
        logger.info("Disconnected from Alpaca")
    
    def is_connected(self) -> bool:
        """Check if connected to Alpaca."""
        return self._connected and self._api is not None
    
    def _ensure_connected(self) -> None:
        """Ensure we're connected, raise if not."""
        if not self.is_connected():
            raise BrokerError("Not connected to Alpaca. Call connect() first.")
    
    # =========================================================================
    # Account Information
    # =========================================================================
    
    async def get_account(self) -> AccountInfo:
        """Get current account information from Alpaca."""
        self._ensure_connected()
        
        try:
            account = self._api.get_account()
            
            return AccountInfo(
                account_id=account.account_number,
                buying_power=float(account.buying_power),
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                equity=float(account.equity),
                margin_used=float(account.initial_margin or 0),
                margin_available=float(account.regt_buying_power or account.buying_power),
                day_trades_remaining=account.daytrade_count if hasattr(account, 'daytrade_count') else 3,
                is_pattern_day_trader=account.pattern_day_trader,
                trading_blocked=account.trading_blocked,
                transfers_blocked=account.transfers_blocked,
                account_blocked=account.account_blocked,
            )
        except Exception as e:
            raise BrokerError(f"Failed to get account: {e}")
    
    async def get_positions(self) -> list[Position]:
        """Get all current positions from Alpaca."""
        self._ensure_connected()
        
        try:
            alpaca_positions = self._api.get_all_positions()
            
            positions = []
            for p in alpaca_positions:
                positions.append(Position(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                    side="long" if float(p.qty) > 0 else "short",
                ))
            
            return positions
        except Exception as e:
            raise BrokerError(f"Failed to get positions: {e}")
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        self._ensure_connected()
        
        try:
            p = self._api.get_open_position(symbol)
            return Position(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_entry_price=float(p.avg_entry_price),
                current_price=float(p.current_price),
                side="long" if float(p.qty) > 0 else "short",
            )
        except Exception:
            return None
    
    # =========================================================================
    # Order Management
    # =========================================================================
    
    async def submit_order(self, order: OrderRequest) -> Order:
        """Submit an order to Alpaca."""
        self._ensure_connected()
        
        try:
            from alpaca.trading.requests import (
                MarketOrderRequest,
                LimitOrderRequest,
                StopOrderRequest,
                StopLimitOrderRequest,
                TrailingStopOrderRequest,
            )
            from alpaca.trading.enums import (
                OrderSide as AlpacaOrderSide,
                TimeInForce,
            )
            
            # Map order side
            side = AlpacaOrderSide.BUY if order.side == OrderSide.BUY else AlpacaOrderSide.SELL
            
            # Map time in force
            tif_map = {
                OrderTimeInForce.DAY: TimeInForce.DAY,
                OrderTimeInForce.GTC: TimeInForce.GTC,
                OrderTimeInForce.IOC: TimeInForce.IOC,
                OrderTimeInForce.FOK: TimeInForce.FOK,
            }
            tif = tif_map.get(order.time_in_force, TimeInForce.DAY)
            
            # Create appropriate order request
            if order.order_type == OrderType.MARKET:
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=tif,
                )
            elif order.order_type == OrderType.LIMIT:
                request = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=tif,
                    limit_price=order.limit_price,
                )
            elif order.order_type == OrderType.STOP:
                request = StopOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=tif,
                    stop_price=order.stop_price,
                )
            elif order.order_type == OrderType.STOP_LIMIT:
                request = StopLimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=tif,
                    stop_price=order.stop_price,
                    limit_price=order.limit_price,
                )
            elif order.order_type == OrderType.TRAILING_STOP:
                request = TrailingStopOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=tif,
                    trail_percent=order.trail_percent,
                    trail_price=order.trail_price,
                )
            else:
                # Default to market
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=tif,
                )
            
            # Submit to Alpaca
            alpaca_order = self._api.submit_order(request)
            
            # Convert to our Order model
            return self._convert_alpaca_order(alpaca_order)
            
        except Exception as e:
            error_msg = str(e)
            if "insufficient" in error_msg.lower():
                raise InsufficientFundsError(f"Insufficient funds: {e}")
            elif "market" in error_msg.lower() and "closed" in error_msg.lower():
                raise MarketClosedError(f"Market closed: {e}")
            else:
                raise BrokerError(f"Order submission failed: {e}")
    
    def _convert_alpaca_order(self, alpaca_order) -> Order:
        """Convert Alpaca order to our Order model."""
        # Map status
        status_map = {
            "new": OrderStatus.SUBMITTED,
            "accepted": OrderStatus.ACCEPTED,
            "pending_new": OrderStatus.PENDING,
            "accepted_for_bidding": OrderStatus.ACCEPTED,
            "partially_filled": OrderStatus.PARTIAL_FILL,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.REJECTED,
            "pending_cancel": OrderStatus.SUBMITTED,
            "pending_replace": OrderStatus.SUBMITTED,
            "stopped": OrderStatus.FILLED,
            "suspended": OrderStatus.REJECTED,
            "calculated": OrderStatus.SUBMITTED,
        }
        
        status_str = str(alpaca_order.status).lower() if hasattr(alpaca_order.status, 'lower') else alpaca_order.status.value.lower()
        status = status_map.get(status_str, OrderStatus.SUBMITTED)
        
        # Map order type
        type_map = {
            "market": OrderType.MARKET,
            "limit": OrderType.LIMIT,
            "stop": OrderType.STOP,
            "stop_limit": OrderType.STOP_LIMIT,
            "trailing_stop": OrderType.TRAILING_STOP,
        }
        type_str = str(alpaca_order.order_type).lower() if hasattr(alpaca_order.order_type, 'lower') else alpaca_order.order_type.value.lower()
        order_type = type_map.get(type_str, OrderType.MARKET)
        
        # Map side
        side_str = str(alpaca_order.side).lower() if hasattr(alpaca_order.side, 'lower') else alpaca_order.side.value.lower()
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL
        
        return Order(
            id=str(alpaca_order.id),
            client_order_id=alpaca_order.client_order_id,
            symbol=alpaca_order.symbol,
            qty=float(alpaca_order.qty),
            filled_qty=float(alpaca_order.filled_qty or 0),
            side=side,
            order_type=order_type,
            status=status,
            limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
            stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
            filled_avg_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
            created_at=alpaca_order.created_at,
            submitted_at=alpaca_order.submitted_at,
            filled_at=alpaca_order.filled_at,
            broker="alpaca",
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        self._ensure_connected()
        
        try:
            self._api.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.warning("Failed to cancel order %s: %s", order_id, e)
            return False
    
    async def cancel_all_orders(self) -> int:
        """Cancel all pending orders."""
        self._ensure_connected()
        
        try:
            cancelled = self._api.cancel_orders()
            return len(cancelled) if cancelled else 0
        except Exception as e:
            logger.error("Failed to cancel all orders: %s", e)
            return 0
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        self._ensure_connected()
        
        try:
            alpaca_order = self._api.get_order_by_id(order_id)
            return self._convert_alpaca_order(alpaca_order)
        except Exception:
            return None
    
    async def get_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders with optional filtering."""
        self._ensure_connected()
        
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            
            # Map status filter
            if status == "open":
                query_status = QueryOrderStatus.OPEN
            elif status == "closed":
                query_status = QueryOrderStatus.CLOSED
            else:
                query_status = QueryOrderStatus.ALL
            
            request = GetOrdersRequest(
                status=query_status,
                limit=limit,
            )
            
            alpaca_orders = self._api.get_orders(request)
            return [self._convert_alpaca_order(o) for o in alpaca_orders]
            
        except Exception as e:
            raise BrokerError(f"Failed to get orders: {e}")
    
    # =========================================================================
    # Market Data
    # =========================================================================
    
    async def get_last_price(self, symbol: str) -> float:
        """Get last traded price for a symbol."""
        self._ensure_connected()
        
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestQuoteRequest
            
            data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
            )
            
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = data_client.get_stock_latest_quote(request)
            
            if symbol in quote:
                # Use midpoint of bid/ask
                bid = float(quote[symbol].bid_price)
                ask = float(quote[symbol].ask_price)
                return (bid + ask) / 2
            
            raise BrokerError(f"No quote data for {symbol}")
            
        except Exception as e:
            logger.warning("Failed to get price for %s: %s", symbol, e)
            # Fallback to getting from position if available
            position = await self.get_position(symbol)
            if position:
                return position.current_price
            raise BrokerError(f"Unable to get price for {symbol}: {e}")
    
    async def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        """Get last prices for multiple symbols."""
        self._ensure_connected()
        
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestQuoteRequest
            
            data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
            )
            
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = data_client.get_stock_latest_quote(request)
            
            prices = {}
            for symbol in symbols:
                if symbol in quotes:
                    bid = float(quotes[symbol].bid_price)
                    ask = float(quotes[symbol].ask_price)
                    prices[symbol] = (bid + ask) / 2
            
            return prices
            
        except Exception as e:
            logger.error("Failed to get prices: %s", e)
            # Fallback to individual calls
            prices = {}
            for symbol in symbols:
                try:
                    prices[symbol] = await self.get_last_price(symbol)
                except Exception:
                    pass
            return prices
    
    # =========================================================================
    # Streaming
    # =========================================================================
    
    async def stream_trade_updates(self, callback: Callable[[Order], None]) -> None:
        """Stream real-time trade/order updates."""
        self._order_callbacks.append(callback)
        
        if self._stream is None:
            await self._start_stream()
    
    async def _start_stream(self) -> None:
        """Start WebSocket stream for updates."""
        try:
            from alpaca.trading.stream import TradingStream
            
            self._stream = TradingStream(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper,
            )
            
            @self._stream.subscribe_trade_updates
            async def on_trade_update(data):
                order = self._convert_alpaca_order(data.order)
                for callback in self._order_callbacks:
                    try:
                        callback(order)
                    except Exception as e:
                        logger.error("Trade update callback error: %s", e)
            
            # Run stream in background
            asyncio.create_task(self._stream._run_forever())
            
        except Exception as e:
            logger.error("Failed to start trade stream: %s", e)
    
    # =========================================================================
    # Portfolio History
    # =========================================================================
    
    async def get_portfolio_history(
        self,
        period: str = "1M",
        timeframe: str = "1D",
    ) -> list[dict]:
        """Get historical portfolio values."""
        self._ensure_connected()
        
        try:
            history = self._api.get_portfolio_history(
                period=period,
                timeframe=timeframe,
            )
            
            result = []
            for i, timestamp in enumerate(history.timestamp):
                result.append({
                    "timestamp": datetime.fromtimestamp(timestamp),
                    "equity": history.equity[i],
                    "profit_loss": history.profit_loss[i] if history.profit_loss else 0,
                    "profit_loss_pct": history.profit_loss_pct[i] if history.profit_loss_pct else 0,
                })
            
            return result
            
        except Exception as e:
            raise BrokerError(f"Failed to get portfolio history: {e}")
