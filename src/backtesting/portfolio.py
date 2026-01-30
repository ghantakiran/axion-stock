"""Simulated Portfolio Management.

Tracks positions, cash, equity, and performance during backtesting.
"""

import logging
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

from src.backtesting.models import (
    Position, Fill, Trade, PortfolioSnapshot, BarData,
    OrderSide, MarketEvent,
)

logger = logging.getLogger(__name__)


class SimulatedPortfolio:
    """Simulated portfolio for backtesting.

    Tracks positions, cash, executions, and computes performance metrics.
    """

    def __init__(self, initial_capital: float = 100_000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, Position] = {}

        # Historical tracking
        self.snapshots: list[PortfolioSnapshot] = []
        self.trades: list[Trade] = []
        self.all_fills: list[Fill] = []

        # Entry tracking for trade P&L
        self._entry_fills: dict[str, list[Fill]] = {}  # symbol -> fills

        # Peak tracking for drawdown
        self._peak_equity = initial_capital

        # Current market data
        self._current_prices: dict[str, float] = {}

    @property
    def positions_value(self) -> float:
        """Total market value of positions."""
        return sum(pos.market_value for pos in self.positions.values())

    @property
    def equity(self) -> float:
        """Total portfolio equity."""
        return self.cash + self.positions_value

    @property
    def drawdown(self) -> float:
        """Current drawdown from peak."""
        if self._peak_equity <= 0:
            return 0.0
        return (self.equity - self._peak_equity) / self._peak_equity

    def update_market_data(self, event: MarketEvent):
        """Update position prices from market data.

        Args:
            event: Market event with bar data.
        """
        for symbol, bar in event.bars.items():
            self._current_prices[symbol] = bar.close

            if symbol in self.positions:
                self.positions[symbol].current_price = bar.close

    def process_fill(self, fill: Fill):
        """Process an order fill.

        Args:
            fill: Fill to process.
        """
        self.all_fills.append(fill)
        symbol = fill.symbol

        # Deduct/add cash
        if fill.side == OrderSide.BUY:
            total_cost = fill.notional + fill.total_cost
            self.cash -= total_cost
        else:
            total_proceeds = fill.notional - fill.total_cost
            self.cash += total_proceeds

        # Update position
        if fill.side == OrderSide.BUY:
            self._process_buy(fill)
        else:
            self._process_sell(fill)

    def _process_buy(self, fill: Fill):
        """Process a buy fill."""
        symbol = fill.symbol

        if symbol in self.positions:
            # Add to existing position
            pos = self.positions[symbol]
            total_qty = pos.qty + fill.qty
            total_cost = pos.avg_cost * pos.qty + fill.price * fill.qty
            pos.avg_cost = total_cost / total_qty
            pos.qty = total_qty
            pos.current_price = fill.price
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                qty=fill.qty,
                avg_cost=fill.price,
                current_price=fill.price,
            )

        # Track entry for trade calculation
        if symbol not in self._entry_fills:
            self._entry_fills[symbol] = []
        self._entry_fills[symbol].append(fill)

    def _process_sell(self, fill: Fill):
        """Process a sell fill."""
        symbol = fill.symbol

        if symbol not in self.positions:
            logger.warning(f"Sell fill for non-existent position: {symbol}")
            return

        pos = self.positions[symbol]
        sell_qty = fill.qty

        # Calculate realized P&L using FIFO
        realized_pnl = 0.0
        entry_price = pos.avg_cost

        if symbol in self._entry_fills:
            entries = self._entry_fills[symbol]
            remaining_sell = sell_qty

            while remaining_sell > 0 and entries:
                entry_fill = entries[0]
                matched_qty = min(remaining_sell, entry_fill.qty)

                # P&L for this lot
                pnl = (fill.price - entry_fill.price) * matched_qty
                realized_pnl += pnl
                entry_price = entry_fill.price

                remaining_sell -= matched_qty
                entry_fill.qty -= matched_qty

                if entry_fill.qty == 0:
                    entries.pop(0)

        # Determine entry date from remaining entries or fall back to fill timestamp
        remaining_entries = self._entry_fills.get(symbol, [])
        entry_ts = remaining_entries[0].timestamp if remaining_entries else fill.timestamp

        # Record trade
        trade = Trade(
            symbol=symbol,
            entry_date=entry_ts,
            exit_date=fill.timestamp,
            side=OrderSide.BUY,  # Original side was buy
            entry_price=entry_price,
            exit_price=fill.price,
            qty=sell_qty,
            pnl=realized_pnl,
            pnl_pct=(fill.price - entry_price) / entry_price if entry_price > 0 else 0,
            hold_days=(fill.timestamp - entry_ts).days,
        )
        self.trades.append(trade)

        # Update position
        pos.qty -= sell_qty

        if pos.qty == 0:
            del self.positions[symbol]
            if symbol in self._entry_fills:
                del self._entry_fills[symbol]
        elif pos.qty < 0:
            logger.warning(f"Negative position for {symbol}: {pos.qty}")

    def record_snapshot(self, timestamp: datetime):
        """Record current portfolio state.

        Args:
            timestamp: Snapshot timestamp.
        """
        # Update peak for drawdown
        if self.equity > self._peak_equity:
            self._peak_equity = self.equity

        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            equity=self.equity,
            cash=self.cash,
            positions_value=self.positions_value,
            n_positions=len(self.positions),
            drawdown=self.drawdown,
            peak_equity=self._peak_equity,
        )
        self.snapshots.append(snapshot)

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        return self.positions.get(symbol)

    def get_position_weight(self, symbol: str) -> float:
        """Get position weight in portfolio."""
        if symbol not in self.positions or self.equity <= 0:
            return 0.0
        return self.positions[symbol].market_value / self.equity

    def get_all_weights(self) -> dict[str, float]:
        """Get all position weights."""
        if self.equity <= 0:
            return {}
        return {
            sym: pos.market_value / self.equity
            for sym, pos in self.positions.items()
        }

    def get_sector_exposure(self, sector: str) -> float:
        """Get total exposure to a sector."""
        total = sum(
            pos.market_value
            for pos in self.positions.values()
            if pos.sector == sector
        )
        return total / self.equity if self.equity > 0 else 0

    def get_equity_curve(self) -> pd.Series:
        """Get equity curve from snapshots."""
        if not self.snapshots:
            return pd.Series(dtype=float)

        return pd.Series(
            [s.equity for s in self.snapshots],
            index=[s.timestamp for s in self.snapshots],
        )

    def get_drawdown_curve(self) -> pd.Series:
        """Get drawdown curve from snapshots."""
        if not self.snapshots:
            return pd.Series(dtype=float)

        return pd.Series(
            [s.drawdown for s in self.snapshots],
            index=[s.timestamp for s in self.snapshots],
        )

    def get_returns(self) -> pd.Series:
        """Get daily returns from equity curve."""
        equity = self.get_equity_curve()
        if len(equity) < 2:
            return pd.Series(dtype=float)
        return equity.pct_change().dropna()

    def get_total_costs(self) -> dict[str, float]:
        """Get total execution costs."""
        commission = sum(f.commission for f in self.all_fills)
        slippage = sum(f.slippage for f in self.all_fills)
        fees = sum(f.fees for f in self.all_fills)

        return {
            "commission": commission,
            "slippage": slippage,
            "fees": fees,
            "total": commission + slippage + fees,
        }

    def get_turnover(self) -> float:
        """Calculate total turnover (total volume / avg equity)."""
        if not self.snapshots:
            return 0.0

        total_volume = sum(f.notional for f in self.all_fills)
        avg_equity = np.mean([s.equity for s in self.snapshots])

        return total_volume / avg_equity if avg_equity > 0 else 0

    def reset(self):
        """Reset portfolio to initial state."""
        self.cash = self.initial_capital
        self.positions = {}
        self.snapshots = []
        self.trades = []
        self.all_fills = []
        self._entry_fills = {}
        self._peak_equity = self.initial_capital
        self._current_prices = {}
