"""Alpaca broker integration for live and paper trading.

Provides order execution via Alpaca's REST API with support for
both paper and live trading accounts.
"""

import asyncio
from datetime import datetime
from typing import Callable, Optional
from uuid import UUID

from src.execution.brokers.base import BaseBroker
from src.execution.models import (
    AccountInfo,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    TimeInForce,
)


class AlpacaBroker(BaseBroker):
    """Alpaca broker for live and paper trading.

    Uses alpaca-py SDK for REST API access. Supports paper trading
    (default) and live trading with appropriate credentials.
    """

    # Map our order types to Alpaca's
    ORDER_TYPE_MAP = {
        OrderType.MARKET: "market",
        OrderType.LIMIT: "limit",
        OrderType.STOP: "stop",
        OrderType.STOP_LIMIT: "stop_limit",
        OrderType.TRAILING_STOP: "trailing_stop",
        OrderType.MOC: "market",  # MOC handled via time_in_force
    }

    # Map our TIF to Alpaca's
    TIF_MAP = {
        TimeInForce.DAY: "day",
        TimeInForce.GTC: "gtc",
        TimeInForce.IOC: "ioc",
        TimeInForce.FOK: "fok",
        TimeInForce.OPG: "opg",
        TimeInForce.CLS: "cls",
    }

    # Map Alpaca status to ours
    STATUS_MAP = {
        "new": OrderStatus.SUBMITTED,
        "accepted": OrderStatus.ACCEPTED,
        "pending_new": OrderStatus.PENDING,
        "partially_filled": OrderStatus.PARTIAL,
        "filled": OrderStatus.FILLED,
        "done_for_day": OrderStatus.EXPIRED,
        "canceled": OrderStatus.CANCELLED,
        "expired": OrderStatus.EXPIRED,
        "replaced": OrderStatus.CANCELLED,
        "pending_cancel": OrderStatus.ACCEPTED,
        "pending_replace": OrderStatus.ACCEPTED,
        "stopped": OrderStatus.ACCEPTED,
        "rejected": OrderStatus.REJECTED,
        "suspended": OrderStatus.REJECTED,
        "calculated": OrderStatus.ACCEPTED,
        "held": OrderStatus.ACCEPTED,
    }

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
            paper: If True, use paper trading (default).
        """
        super().__init__()
        self._api_key = api_key
        self._secret_key = secret_key
        self._paper = paper
        self._trading_client = None
        self._data_client = None

    @property
    def is_paper(self) -> bool:
        return self._paper

    async def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient

            self._trading_client = TradingClient(
                api_key=self._api_key,
                secret_key=self._secret_key,
                paper=self._paper,
            )

            self._data_client = StockHistoricalDataClient(
                api_key=self._api_key,
                secret_key=self._secret_key,
            )

            # Test connection by getting account
            self._trading_client.get_account()
            self._connected = True
            return True

        except ImportError:
            raise RuntimeError(
                "alpaca-py not installed. Run: pip install alpaca-py"
            )
        except Exception as e:
            self._connected = False
            raise RuntimeError(f"Failed to connect to Alpaca: {e}")

    async def disconnect(self) -> None:
        """Disconnect from Alpaca."""
        self._trading_client = None
        self._data_client = None
        self._connected = False

    async def get_account(self) -> AccountInfo:
        """Get Alpaca account information."""
        self._ensure_connected()

        acct = self._trading_client.get_account()

        return AccountInfo(
            equity=float(acct.equity),
            cash=float(acct.cash),
            buying_power=float(acct.buying_power),
            portfolio_value=float(acct.portfolio_value),
            margin_used=float(acct.initial_margin or 0),
            day_trades_remaining=acct.daytrade_count,
            pattern_day_trader=acct.pattern_day_trader,
            trading_blocked=acct.trading_blocked,
            account_blocked=acct.account_blocked,
        )

    async def get_positions(self) -> list[Position]:
        """Get all Alpaca positions."""
        self._ensure_connected()

        positions = self._trading_client.get_all_positions()

        return [
            Position(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_entry_price=float(p.avg_entry_price),
                current_price=float(p.current_price),
                side="long" if float(p.qty) > 0 else "short",
            )
            for p in positions
        ]

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        self._ensure_connected()

        try:
            p = self._trading_client.get_open_position(symbol)
            return Position(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_entry_price=float(p.avg_entry_price),
                current_price=float(p.current_price),
                side="long" if float(p.qty) > 0 else "short",
            )
        except Exception:
            return None

    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get Alpaca orders."""
        self._ensure_connected()

        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        # Map our status to Alpaca query status
        query_status = None
        if status == OrderStatus.FILLED:
            query_status = QueryOrderStatus.CLOSED
        elif status in (OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.PARTIAL):
            query_status = QueryOrderStatus.OPEN
        # None = all orders

        request = GetOrdersRequest(
            status=query_status,
            limit=limit,
        )

        orders = self._trading_client.get_orders(request)

        return [self._convert_alpaca_order(o) for o in orders]

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get a specific Alpaca order."""
        self._ensure_connected()

        try:
            o = self._trading_client.get_order_by_id(order_id)
            return self._convert_alpaca_order(o)
        except Exception:
            return None

    async def submit_order(self, request: OrderRequest) -> Order:
        """Submit order to Alpaca."""
        self._ensure_connected()
        self._validate_order_request(request)

        from alpaca.trading.requests import (
            MarketOrderRequest,
            LimitOrderRequest,
            StopOrderRequest,
            StopLimitOrderRequest,
            TrailingStopOrderRequest,
        )
        from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce as AlpacaTIF

        # Convert side
        side = AlpacaSide.BUY if request.side == OrderSide.BUY else AlpacaSide.SELL

        # Convert time in force
        tif = AlpacaTIF(self.TIF_MAP.get(request.time_in_force, "day"))

        # Handle MOC specially
        if request.order_type == OrderType.MOC:
            tif = AlpacaTIF.CLS

        # Build appropriate order request
        if request.order_type == OrderType.MARKET:
            alpaca_request = MarketOrderRequest(
                symbol=request.symbol,
                qty=request.qty,
                side=side,
                time_in_force=tif,
                extended_hours=request.extended_hours,
                client_order_id=request.client_order_id,
            )
        elif request.order_type == OrderType.LIMIT:
            alpaca_request = LimitOrderRequest(
                symbol=request.symbol,
                qty=request.qty,
                side=side,
                time_in_force=tif,
                limit_price=request.limit_price,
                extended_hours=request.extended_hours,
                client_order_id=request.client_order_id,
            )
        elif request.order_type == OrderType.STOP:
            alpaca_request = StopOrderRequest(
                symbol=request.symbol,
                qty=request.qty,
                side=side,
                time_in_force=tif,
                stop_price=request.stop_price,
                extended_hours=request.extended_hours,
                client_order_id=request.client_order_id,
            )
        elif request.order_type == OrderType.STOP_LIMIT:
            alpaca_request = StopLimitOrderRequest(
                symbol=request.symbol,
                qty=request.qty,
                side=side,
                time_in_force=tif,
                limit_price=request.limit_price,
                stop_price=request.stop_price,
                extended_hours=request.extended_hours,
                client_order_id=request.client_order_id,
            )
        elif request.order_type == OrderType.TRAILING_STOP:
            alpaca_request = TrailingStopOrderRequest(
                symbol=request.symbol,
                qty=request.qty,
                side=side,
                time_in_force=tif,
                trail_percent=1.0,  # Default 1% trail
                extended_hours=request.extended_hours,
                client_order_id=request.client_order_id,
            )
        elif request.order_type == OrderType.MOC:
            alpaca_request = MarketOrderRequest(
                symbol=request.symbol,
                qty=request.qty,
                side=side,
                time_in_force=AlpacaTIF.CLS,
                client_order_id=request.client_order_id,
            )
        else:
            raise ValueError(f"Unsupported order type: {request.order_type}")

        # Submit to Alpaca
        alpaca_order = self._trading_client.submit_order(alpaca_request)

        return self._convert_alpaca_order(alpaca_order)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an Alpaca order."""
        self._ensure_connected()

        try:
            self._trading_client.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False

    async def cancel_all_orders(self) -> int:
        """Cancel all open Alpaca orders."""
        self._ensure_connected()

        try:
            cancelled = self._trading_client.cancel_orders()
            return len(cancelled) if cancelled else 0
        except Exception:
            return 0

    async def get_quote(self, symbol: str) -> dict:
        """Get current quote from Alpaca."""
        self._ensure_connected()

        from alpaca.data.requests import StockLatestQuoteRequest

        request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
        quotes = self._data_client.get_stock_latest_quote(request)

        if symbol in quotes:
            q = quotes[symbol]
            return {
                "bid": float(q.bid_price),
                "ask": float(q.ask_price),
                "last": (float(q.bid_price) + float(q.ask_price)) / 2,
                "volume": 0,  # Not in quote, use trade data
            }

        return {"bid": 0, "ask": 0, "last": 0, "volume": 0}

    async def stream_trade_updates(
        self,
        callback: Callable[[Order], None],
    ) -> None:
        """Stream real-time order updates via WebSocket.

        Note: This is a simplified implementation. In production,
        you would want to run this in a background task.
        """
        from alpaca.trading.stream import TradingStream

        stream = TradingStream(
            api_key=self._api_key,
            secret_key=self._secret_key,
            paper=self._paper,
        )

        @stream.on_trade_update
        async def on_trade_update(data):
            order = self._convert_alpaca_order(data.order)
            callback(order)

        # Run in background
        await stream._run_forever()

    def _ensure_connected(self) -> None:
        """Ensure we're connected to Alpaca."""
        if not self._connected or self._trading_client is None:
            raise RuntimeError("Not connected to Alpaca. Call connect() first.")

    def _convert_alpaca_order(self, alpaca_order) -> Order:
        """Convert Alpaca order to our Order model."""
        # Map order type
        order_type = OrderType.MARKET
        for our_type, alpaca_type in self.ORDER_TYPE_MAP.items():
            if alpaca_order.type == alpaca_type:
                order_type = our_type
                break

        # Map status
        status = self.STATUS_MAP.get(
            alpaca_order.status,
            OrderStatus.SUBMITTED,
        )

        # Map side
        side = OrderSide.BUY if alpaca_order.side == "buy" else OrderSide.SELL

        # Map time in force
        tif = TimeInForce.DAY
        for our_tif, alpaca_tif in self.TIF_MAP.items():
            if alpaca_order.time_in_force == alpaca_tif:
                tif = our_tif
                break

        return Order(
            id=UUID(str(alpaca_order.id)),
            symbol=alpaca_order.symbol,
            qty=float(alpaca_order.qty),
            side=side,
            order_type=order_type,
            status=status,
            limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
            stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
            time_in_force=tif,
            filled_qty=float(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0.0,
            filled_avg_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
            submitted_at=alpaca_order.submitted_at,
            filled_at=alpaca_order.filled_at,
            cancelled_at=alpaca_order.canceled_at,
            created_at=alpaca_order.created_at or datetime.utcnow(),
            client_order_id=alpaca_order.client_order_id,
            broker_order_id=str(alpaca_order.id),
        )
