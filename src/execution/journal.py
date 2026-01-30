"""Trade Journal Service - Persist trades and orders to database.

Provides:
- Order persistence with full audit trail
- Trade execution logging with context
- Portfolio snapshot management
- Performance analytics
"""

import json
import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.db.models import (
    TradeOrder,
    TradeExecution,
    PortfolioSnapshot,
    OrderSideType,
    OrderStatusType,
    OrderTypeEnum,
    MarketRegimeType,
)
from src.execution.models import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Trade,
    AccountInfo,
)

logger = logging.getLogger(__name__)


class TradeJournal:
    """Persists trades and orders to database for journaling and analytics.

    Example:
        journal = TradeJournal(db_session)

        # Log an order
        await journal.log_order(order, regime="bull")

        # Log an execution
        await journal.log_trade(trade, portfolio_value=100000)

        # Take portfolio snapshot
        await journal.take_snapshot(account, positions)
    """

    def __init__(self, session: Session):
        """Initialize journal with database session.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self.session = session

    # =========================================================================
    # Order Logging
    # =========================================================================

    def log_order(
        self,
        order: Order,
        regime: Optional[str] = None,
    ) -> TradeOrder:
        """Log an order to the database.

        Args:
            order: Order to log.
            regime: Current market regime (bull/bear/sideways/crisis).

        Returns:
            Created TradeOrder database record.
        """
        # Map enums
        side = OrderSideType.BUY if order.side == OrderSide.BUY else OrderSideType.SELL

        status_map = {
            OrderStatus.PENDING: OrderStatusType.PENDING,
            OrderStatus.SUBMITTED: OrderStatusType.SUBMITTED,
            OrderStatus.ACCEPTED: OrderStatusType.ACCEPTED,
            OrderStatus.PARTIAL_FILL: OrderStatusType.PARTIAL_FILL,
            OrderStatus.FILLED: OrderStatusType.FILLED,
            OrderStatus.CANCELLED: OrderStatusType.CANCELLED,
            OrderStatus.REJECTED: OrderStatusType.REJECTED,
            OrderStatus.EXPIRED: OrderStatusType.EXPIRED,
        }
        status = status_map.get(order.status, OrderStatusType.PENDING)

        type_map = {
            OrderType.MARKET: OrderTypeEnum.MARKET,
            OrderType.LIMIT: OrderTypeEnum.LIMIT,
            OrderType.STOP: OrderTypeEnum.STOP,
            OrderType.STOP_LIMIT: OrderTypeEnum.STOP_LIMIT,
            OrderType.TRAILING_STOP: OrderTypeEnum.TRAILING_STOP,
        }
        order_type = type_map.get(order.order_type, OrderTypeEnum.MARKET)

        regime_enum = None
        if regime:
            regime_map = {
                "bull": MarketRegimeType.BULL,
                "bear": MarketRegimeType.BEAR,
                "sideways": MarketRegimeType.SIDEWAYS,
                "crisis": MarketRegimeType.CRISIS,
            }
            regime_enum = regime_map.get(regime.lower())

        db_order = TradeOrder(
            order_id=order.id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=side,
            order_type=order_type,
            quantity=order.qty,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            filled_quantity=order.filled_qty,
            filled_avg_price=order.filled_avg_price,
            status=status,
            commission=order.commission,
            slippage=order.slippage,
            trigger=order.trigger,
            broker=order.broker,
            regime_at_order=regime_enum,
            submitted_at=order.submitted_at,
            filled_at=order.filled_at,
            cancelled_at=order.cancelled_at,
            notes=order.notes,
        )

        self.session.add(db_order)
        self.session.commit()

        logger.info(
            "Logged order: %s %s %.4f %s @ %s (status: %s)",
            order.side.value,
            order.qty,
            order.symbol,
            order.order_type.value,
            order.filled_avg_price or order.limit_price or "market",
            order.status.value,
        )

        return db_order

    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_qty: Optional[float] = None,
        filled_price: Optional[float] = None,
    ) -> Optional[TradeOrder]:
        """Update an existing order's status.

        Args:
            order_id: Order ID to update.
            status: New status.
            filled_qty: Updated filled quantity.
            filled_price: Updated filled price.

        Returns:
            Updated TradeOrder or None if not found.
        """
        db_order = self.session.query(TradeOrder).filter(
            TradeOrder.order_id == order_id
        ).first()

        if not db_order:
            logger.warning("Order %s not found for update", order_id)
            return None

        status_map = {
            OrderStatus.PENDING: OrderStatusType.PENDING,
            OrderStatus.SUBMITTED: OrderStatusType.SUBMITTED,
            OrderStatus.ACCEPTED: OrderStatusType.ACCEPTED,
            OrderStatus.PARTIAL_FILL: OrderStatusType.PARTIAL_FILL,
            OrderStatus.FILLED: OrderStatusType.FILLED,
            OrderStatus.CANCELLED: OrderStatusType.CANCELLED,
            OrderStatus.REJECTED: OrderStatusType.REJECTED,
            OrderStatus.EXPIRED: OrderStatusType.EXPIRED,
        }

        db_order.status = status_map.get(status, OrderStatusType.PENDING)

        if filled_qty is not None:
            db_order.filled_quantity = filled_qty

        if filled_price is not None:
            db_order.filled_avg_price = filled_price

        if status == OrderStatus.FILLED:
            db_order.filled_at = datetime.now()
        elif status == OrderStatus.CANCELLED:
            db_order.cancelled_at = datetime.now()

        self.session.commit()
        return db_order

    # =========================================================================
    # Trade Logging
    # =========================================================================

    def log_trade(
        self,
        trade: Trade,
        factor_scores: Optional[dict] = None,
        regime: Optional[str] = None,
        portfolio_value: Optional[float] = None,
    ) -> TradeExecution:
        """Log a trade execution to the database.

        Args:
            trade: Trade to log.
            factor_scores: Factor scores at time of trade.
            regime: Market regime at time of trade.
            portfolio_value: Portfolio value at time of trade.

        Returns:
            Created TradeExecution database record.
        """
        side = OrderSideType.BUY if trade.side == OrderSide.BUY else OrderSideType.SELL

        regime_enum = None
        if regime:
            regime_map = {
                "bull": MarketRegimeType.BULL,
                "bear": MarketRegimeType.BEAR,
                "sideways": MarketRegimeType.SIDEWAYS,
                "crisis": MarketRegimeType.CRISIS,
            }
            regime_enum = regime_map.get(regime.lower())

        db_trade = TradeExecution(
            execution_id=trade.id,
            order_id=trade.order_id,
            symbol=trade.symbol,
            side=side,
            quantity=trade.quantity,
            price=trade.price,
            commission=trade.commission,
            slippage=trade.slippage,
            factor_scores=json.dumps(factor_scores) if factor_scores else None,
            regime_at_trade=regime_enum,
            portfolio_value_at_trade=portfolio_value,
            executed_at=trade.timestamp,
            notes=trade.notes,
        )

        self.session.add(db_trade)
        self.session.commit()

        logger.info(
            "Logged trade: %s %.4f %s @ $%.2f",
            trade.side.value,
            trade.quantity,
            trade.symbol,
            trade.price,
        )

        return db_trade

    # =========================================================================
    # Portfolio Snapshots
    # =========================================================================

    def take_snapshot(
        self,
        account: AccountInfo,
        positions: list[Position],
        regime: Optional[str] = None,
        metrics: Optional[dict] = None,
    ) -> PortfolioSnapshot:
        """Take a daily portfolio snapshot.

        Args:
            account: Current account info.
            positions: List of current positions.
            regime: Current market regime.
            metrics: Optional performance metrics dict.

        Returns:
            Created PortfolioSnapshot database record.
        """
        today = date.today()

        # Check if snapshot exists for today
        existing = self.session.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.snapshot_date == today
        ).first()

        if existing:
            # Update existing snapshot
            snapshot = existing
        else:
            snapshot = PortfolioSnapshot(snapshot_date=today)

        # Calculate daily P&L from previous snapshot
        prev_snapshot = self.session.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.snapshot_date < today
        ).order_by(PortfolioSnapshot.snapshot_date.desc()).first()

        daily_pnl = 0
        daily_return = 0
        cumulative_return = 0

        if prev_snapshot:
            daily_pnl = account.equity - prev_snapshot.equity
            daily_return = daily_pnl / prev_snapshot.equity if prev_snapshot.equity > 0 else 0

            # Get first snapshot for cumulative return
            first_snapshot = self.session.query(PortfolioSnapshot).order_by(
                PortfolioSnapshot.snapshot_date
            ).first()
            if first_snapshot:
                cumulative_return = (account.equity - first_snapshot.equity) / first_snapshot.equity

        # Serialize positions
        positions_json = json.dumps([
            {
                "symbol": p.symbol,
                "qty": p.qty,
                "avg_entry": p.avg_entry_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "pnl_pct": p.unrealized_pnl_pct,
            }
            for p in positions
        ])

        regime_enum = None
        if regime:
            regime_map = {
                "bull": MarketRegimeType.BULL,
                "bear": MarketRegimeType.BEAR,
                "sideways": MarketRegimeType.SIDEWAYS,
                "crisis": MarketRegimeType.CRISIS,
            }
            regime_enum = regime_map.get(regime.lower())

        snapshot.cash = account.cash
        snapshot.portfolio_value = account.portfolio_value
        snapshot.equity = account.equity
        snapshot.daily_pnl = daily_pnl
        snapshot.daily_return_pct = daily_return
        snapshot.cumulative_return_pct = cumulative_return
        snapshot.positions = positions_json
        snapshot.regime = regime_enum
        snapshot.num_positions = len(positions)

        # Add optional metrics
        if metrics:
            snapshot.portfolio_beta = metrics.get("beta")
            snapshot.portfolio_volatility = metrics.get("volatility")
            snapshot.sharpe_ratio = metrics.get("sharpe")
            snapshot.max_drawdown = metrics.get("max_drawdown")

        if not existing:
            self.session.add(snapshot)

        self.session.commit()

        logger.info(
            "Portfolio snapshot: equity=$%.2f, daily_return=%.2f%%, positions=%d",
            account.equity,
            daily_return * 100,
            len(positions),
        )

        return snapshot

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> list[TradeOrder]:
        """Query orders from database.

        Args:
            symbol: Filter by symbol.
            status: Filter by status.
            start_date: Filter orders after this date.
            end_date: Filter orders before this date.
            limit: Maximum number of results.

        Returns:
            List of TradeOrder records.
        """
        query = self.session.query(TradeOrder)

        if symbol:
            query = query.filter(TradeOrder.symbol == symbol.upper())

        if status:
            status_map = {
                "pending": OrderStatusType.PENDING,
                "filled": OrderStatusType.FILLED,
                "cancelled": OrderStatusType.CANCELLED,
            }
            if status.lower() in status_map:
                query = query.filter(TradeOrder.status == status_map[status.lower()])

        if start_date:
            query = query.filter(TradeOrder.created_at >= start_date)

        if end_date:
            query = query.filter(TradeOrder.created_at <= end_date)

        return query.order_by(TradeOrder.created_at.desc()).limit(limit).all()

    def get_trades(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> list[TradeExecution]:
        """Query trade executions from database.

        Args:
            symbol: Filter by symbol.
            start_date: Filter trades after this date.
            end_date: Filter trades before this date.
            limit: Maximum number of results.

        Returns:
            List of TradeExecution records.
        """
        query = self.session.query(TradeExecution)

        if symbol:
            query = query.filter(TradeExecution.symbol == symbol.upper())

        if start_date:
            query = query.filter(TradeExecution.executed_at >= start_date)

        if end_date:
            query = query.filter(TradeExecution.executed_at <= end_date)

        return query.order_by(TradeExecution.executed_at.desc()).limit(limit).all()

    def get_snapshots(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[PortfolioSnapshot]:
        """Query portfolio snapshots.

        Args:
            start_date: Filter snapshots after this date.
            end_date: Filter snapshots before this date.

        Returns:
            List of PortfolioSnapshot records.
        """
        query = self.session.query(PortfolioSnapshot)

        if start_date:
            query = query.filter(PortfolioSnapshot.snapshot_date >= start_date)

        if end_date:
            query = query.filter(PortfolioSnapshot.snapshot_date <= end_date)

        return query.order_by(PortfolioSnapshot.snapshot_date).all()

    # =========================================================================
    # Analytics
    # =========================================================================

    def get_trade_summary(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Calculate trade summary statistics.

        Args:
            start_date: Analysis start date.
            end_date: Analysis end date.

        Returns:
            Dict with trade statistics.
        """
        trades = self.get_trades(start_date=start_date, end_date=end_date, limit=10000)

        if not trades:
            return {
                "total_trades": 0,
                "total_volume": 0,
                "total_commission": 0,
                "total_slippage": 0,
            }

        buys = [t for t in trades if t.side == OrderSideType.BUY]
        sells = [t for t in trades if t.side == OrderSideType.SELL]

        total_volume = sum(t.quantity * t.price for t in trades)
        total_commission = sum(t.commission or 0 for t in trades)
        total_slippage = sum(t.slippage or 0 for t in trades)

        return {
            "total_trades": len(trades),
            "buy_trades": len(buys),
            "sell_trades": len(sells),
            "total_volume": total_volume,
            "total_commission": total_commission,
            "total_slippage": total_slippage,
            "avg_slippage_bps": (total_slippage / total_volume * 10000) if total_volume > 0 else 0,
        }

    def get_performance_metrics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Calculate portfolio performance metrics from snapshots.

        Args:
            start_date: Analysis start date.
            end_date: Analysis end date.

        Returns:
            Dict with performance metrics.
        """
        snapshots = self.get_snapshots(start_date=start_date, end_date=end_date)

        if len(snapshots) < 2:
            return {
                "total_return": 0,
                "daily_returns": [],
                "sharpe_ratio": 0,
                "max_drawdown": 0,
            }

        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1].equity
            curr = snapshots[i].equity
            daily_returns.append((curr - prev) / prev if prev > 0 else 0)

        # Total return
        start_equity = snapshots[0].equity
        end_equity = snapshots[-1].equity
        total_return = (end_equity - start_equity) / start_equity if start_equity > 0 else 0

        # Sharpe ratio (annualized, assuming 252 trading days)
        import numpy as np
        if len(daily_returns) > 1:
            avg_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            sharpe = (avg_return * 252) / (std_return * np.sqrt(252)) if std_return > 0 else 0
        else:
            sharpe = 0

        # Max drawdown
        equity_curve = [s.equity for s in snapshots]
        peak = equity_curve[0]
        max_drawdown = 0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        return {
            "total_return": total_return,
            "annualized_return": total_return * 252 / len(snapshots) if snapshots else 0,
            "daily_returns": daily_returns,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "num_snapshots": len(snapshots),
        }
