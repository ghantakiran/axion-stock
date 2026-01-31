"""Paper Trading Session Manager.

Manages paper trading session lifecycle, order execution,
position tracking, and snapshot recording.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from src.paper_trading.config import (
    SessionConfig,
    SessionStatus,
    StrategyType,
    RebalanceSchedule,
    DEFAULT_SESSION_CONFIG,
)
from src.paper_trading.models import (
    PaperSession,
    SessionTrade,
    PortfolioPosition,
    SessionSnapshot,
    _new_id,
    _utc_now,
)
from src.paper_trading.data_feed import DataFeed
from src.paper_trading.performance import PerformanceTracker

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages paper trading sessions.

    Handles session creation, order execution, position management,
    strategy automation, and snapshot recording.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, PaperSession] = {}
        self._feeds: dict[str, DataFeed] = {}
        self._performance = PerformanceTracker()

    def create_session(
        self,
        name: str,
        config: Optional[SessionConfig] = None,
    ) -> PaperSession:
        """Create a new paper trading session.

        Args:
            name: Session name.
            config: Session configuration.

        Returns:
            Created PaperSession.
        """
        config = config or DEFAULT_SESSION_CONFIG

        session = PaperSession(
            name=name,
            strategy_type=config.strategy.strategy_type,
            initial_capital=config.initial_capital,
            symbols=list(config.symbols),
            benchmark=config.benchmark,
        )

        # Initialize data feed
        feed = DataFeed(config.data_feed)
        feed.initialize(config.symbols)

        self._sessions[session.session_id] = session
        self._feeds[session.session_id] = feed

        logger.info(f"Session created: {name} ({session.session_id})")
        return session

    def start_session(self, session_id: str) -> bool:
        """Start a session.

        Args:
            session_id: Session identifier.

        Returns:
            True if started successfully.
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.start()
        logger.info(f"Session started: {session.name}")
        return True

    def pause_session(self, session_id: str) -> bool:
        """Pause a running session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.pause()
        return True

    def resume_session(self, session_id: str) -> bool:
        """Resume a paused session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.resume()
        return True

    def stop_session(self, session_id: str) -> bool:
        """Stop (complete) a session and compute final metrics."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.complete()
        session.metrics = self._performance.compute(session)
        logger.info(
            f"Session completed: {session.name}, "
            f"return={session.total_return:.2%}"
        )
        return True

    def get_session(self, session_id: str) -> Optional[PaperSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self, status: Optional[SessionStatus] = None) -> list[PaperSession]:
        """List all sessions, optionally filtered by status."""
        sessions = list(self._sessions.values())
        if status is not None:
            sessions = [s for s in sessions if s.status == status]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._feeds.pop(session_id, None)
            return True
        return False

    # =========================================================================
    # Order Execution
    # =========================================================================

    def execute_buy(
        self,
        session_id: str,
        symbol: str,
        qty: int,
        reason: str = "manual",
    ) -> Optional[SessionTrade]:
        """Execute a buy order in a session.

        Args:
            session_id: Session identifier.
            symbol: Symbol to buy.
            qty: Number of shares.
            reason: Trade reason.

        Returns:
            SessionTrade if executed, None otherwise.
        """
        session = self._sessions.get(session_id)
        feed = self._feeds.get(session_id)
        if not session or not feed or session.status != SessionStatus.RUNNING:
            return None

        price = feed.get_price(symbol)
        if price <= 0:
            return None

        notional = qty * price
        slippage = notional * 0.0002  # 2 bps
        total_cost = notional + slippage

        if total_cost > session.cash:
            logger.warning(f"Insufficient cash for buy: need {total_cost:.2f}, have {session.cash:.2f}")
            return None

        # Deduct cash
        session.cash -= total_cost

        # Update position
        if symbol in session.positions:
            pos = session.positions[symbol]
            old_cost = pos.qty * pos.avg_cost
            new_cost = qty * price
            pos.qty += qty
            pos.avg_cost = (old_cost + new_cost) / pos.qty
            pos.current_price = price
        else:
            session.positions[symbol] = PortfolioPosition(
                symbol=symbol,
                qty=qty,
                avg_cost=price,
                current_price=price,
            )

        # Record trade
        trade = SessionTrade(
            session_id=session_id,
            symbol=symbol,
            side="buy",
            qty=qty,
            price=price,
            notional=notional,
            slippage=slippage,
            reason=reason,
        )
        session.trades.append(trade)

        return trade

    def execute_sell(
        self,
        session_id: str,
        symbol: str,
        qty: int,
        reason: str = "manual",
    ) -> Optional[SessionTrade]:
        """Execute a sell order in a session.

        Args:
            session_id: Session identifier.
            symbol: Symbol to sell.
            qty: Number of shares.
            reason: Trade reason.

        Returns:
            SessionTrade if executed, None otherwise.
        """
        session = self._sessions.get(session_id)
        feed = self._feeds.get(session_id)
        if not session or not feed or session.status != SessionStatus.RUNNING:
            return None

        pos = session.positions.get(symbol)
        if not pos or pos.qty < qty:
            logger.warning(f"Insufficient shares for sell: {symbol}")
            return None

        price = feed.get_price(symbol)
        if price <= 0:
            return None

        notional = qty * price
        slippage = notional * 0.0002  # 2 bps

        # Compute realized P&L
        pnl = (price - pos.avg_cost) * qty - slippage
        pnl_pct = (price / pos.avg_cost - 1) if pos.avg_cost > 0 else 0.0

        # Add cash
        session.cash += notional - slippage

        # Update position
        pos.qty -= qty
        pos.current_price = price
        if pos.qty == 0:
            del session.positions[symbol]

        # Record trade
        trade = SessionTrade(
            session_id=session_id,
            symbol=symbol,
            side="sell",
            qty=qty,
            price=price,
            notional=notional,
            slippage=slippage,
            pnl=pnl,
            pnl_pct=pnl_pct,
            reason=reason,
        )
        session.trades.append(trade)

        return trade

    # =========================================================================
    # Market Data & Snapshots
    # =========================================================================

    def advance_feed(self, session_id: str) -> dict[str, float]:
        """Advance the data feed by one tick and update positions.

        Args:
            session_id: Session identifier.

        Returns:
            Updated prices.
        """
        session = self._sessions.get(session_id)
        feed = self._feeds.get(session_id)
        if not session or not feed or session.status != SessionStatus.RUNNING:
            return {}

        prices = feed.next_tick()

        # Update position prices
        for symbol, pos in session.positions.items():
            if symbol in prices:
                pos.current_price = prices[symbol]

        # Update peak equity
        if session.equity > session.peak_equity:
            session.peak_equity = session.equity

        return prices

    def record_snapshot(self, session_id: str) -> Optional[SessionSnapshot]:
        """Record current portfolio state.

        Args:
            session_id: Session identifier.

        Returns:
            SessionSnapshot if recorded.
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Compute daily return
        daily_return = 0.0
        if session.snapshots:
            prev_equity = session.snapshots[-1].equity
            if prev_equity > 0:
                daily_return = (session.equity - prev_equity) / prev_equity

        snapshot = SessionSnapshot(
            session_id=session_id,
            equity=session.equity,
            cash=session.cash,
            positions_value=session.positions_value,
            n_positions=len(session.positions),
            drawdown=session.drawdown,
            peak_equity=session.peak_equity,
            daily_return=daily_return,
        )
        session.snapshots.append(snapshot)

        return snapshot

    # =========================================================================
    # Strategy Automation
    # =========================================================================

    def run_equal_weight_rebalance(self, session_id: str) -> list[SessionTrade]:
        """Run equal-weight rebalance for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of trades executed.
        """
        session = self._sessions.get(session_id)
        feed = self._feeds.get(session_id)
        if not session or not feed or session.status != SessionStatus.RUNNING:
            return []

        trades = []
        target_weight = 1.0 / len(session.symbols) if session.symbols else 0
        equity = session.equity

        # First: sell excess positions
        for symbol in list(session.positions.keys()):
            pos = session.positions.get(symbol)
            if not pos:
                continue

            price = feed.get_price(symbol)
            if price <= 0:
                continue

            current_weight = pos.market_value / equity if equity > 0 else 0
            target_value = equity * target_weight
            current_value = pos.market_value

            if symbol not in session.symbols:
                # Sell positions not in universe
                trade = self.execute_sell(session_id, symbol, pos.qty, "rebalance")
                if trade:
                    trades.append(trade)
            elif current_value > target_value * 1.03:
                # Sell excess
                sell_value = current_value - target_value
                sell_qty = max(1, int(sell_value / price))
                sell_qty = min(sell_qty, pos.qty)
                trade = self.execute_sell(session_id, symbol, sell_qty, "rebalance")
                if trade:
                    trades.append(trade)

        # Then: buy underweight positions
        for symbol in session.symbols:
            price = feed.get_price(symbol)
            if price <= 0:
                continue

            pos = session.positions.get(symbol)
            current_value = pos.market_value if pos else 0
            target_value = session.equity * target_weight

            if current_value < target_value * 0.97:
                buy_value = target_value - current_value
                buy_qty = max(1, int(buy_value / price))

                if buy_qty * price <= session.cash * 0.98:  # Cash buffer
                    trade = self.execute_buy(session_id, symbol, buy_qty, "rebalance")
                    if trade:
                        trades.append(trade)

        return trades

    # =========================================================================
    # Performance
    # =========================================================================

    def get_metrics(self, session_id: str) -> Optional[dict]:
        """Get current performance metrics for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        metrics = self._performance.compute(session)
        return metrics.to_dict()

    def compare_sessions(self, session_ids: list[str]) -> Optional[dict]:
        """Compare multiple sessions."""
        sessions = {}
        for sid in session_ids:
            session = self._sessions.get(sid)
            if session:
                sessions[session.name] = session

        if len(sessions) < 2:
            return None

        comparison = self._performance.compare_sessions(sessions)
        return {
            "sessions": comparison.sessions,
            "metrics_table": comparison.metrics_table,
            "winner_by_metric": comparison.winner_by_metric,
            "ranking": comparison.ranking,
        }
