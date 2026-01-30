"""Trading API Routes.

Endpoints for order management and trade history.
"""

import logging
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.models import (
    CreateOrderRequest,
    OrderResponse,
    OrderStatusEnum,
    TradeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["Trading"])

# In-memory store for demo
_orders: dict[str, OrderResponse] = {}


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(request: CreateOrderRequest) -> OrderResponse:
    """Submit a new order."""
    order_id = secrets.token_hex(8)

    order = OrderResponse(
        order_id=order_id,
        client_order_id=request.client_order_id,
        symbol=request.symbol.upper(),
        side=request.side,
        qty=request.qty,
        order_type=request.order_type,
        limit_price=request.limit_price,
        stop_price=request.stop_price,
        status=OrderStatusEnum.PENDING,
    )

    _orders[order_id] = order
    logger.info(f"Order created: {order_id} {request.side.value} {request.qty} {request.symbol}")

    return order


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str) -> OrderResponse:
    """Get order by ID."""
    order = _orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
    return order


@router.delete("/{order_id}", response_model=OrderResponse)
async def cancel_order(order_id: str) -> OrderResponse:
    """Cancel an order."""
    order = _orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")

    if order.status not in [OrderStatusEnum.PENDING, OrderStatusEnum.PARTIALLY_FILLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status: {order.status.value}",
        )

    order.status = OrderStatusEnum.CANCELLED
    return order


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: Optional[str] = Query(default=None),
    symbol: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[OrderResponse]:
    """List orders with optional filters."""
    orders = list(_orders.values())

    if status:
        orders = [o for o in orders if o.status.value == status]
    if symbol:
        orders = [o for o in orders if o.symbol == symbol.upper()]

    return orders[:limit]


@router.get("/trades/history", response_model=list[TradeResponse])
async def get_trade_history(
    symbol: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[TradeResponse]:
    """Get trade history."""
    return []
