"""Professional Backtesting Engine.

Event-driven backtesting framework with realistic execution modeling,
risk management, and comprehensive performance analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Protocol, Iterator
import numpy as np
import pandas as pd

from src.backtesting.config import (
    BacktestConfig, DEFAULT_BACKTEST, RebalanceFrequency,
)
from src.backtesting.models import (
    BarData, MarketEvent, Signal, Order, Fill, BacktestResult,
    BacktestMetrics, OrderSide, OrderType,
)
from src.backtesting.execution import SimulatedBroker, CostModel
from src.backtesting.portfolio import SimulatedPortfolio

logger = logging.getLogger(__name__)


class Strategy(Protocol):
    """Strategy interface for backtesting."""

    def on_bar(self, event: MarketEvent, portfolio: SimulatedPortfolio) -> list[Signal]:
        """Generate signals on new bar data.

        Args:
            event: Market event with bar data.
            portfolio: Current portfolio state.

        Returns:
            List of trading signals.
        """
        ...

    def on_fill(self, fill: Fill):
        """Called when an order is filled (optional)."""
        ...


class BacktestRiskManager:
    """Risk manager for backtesting.

    Validates signals against risk rules before execution.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self._trading_halted = False
        self._halt_reason = ""

    def validate(
        self,
        signals: list[Signal],
        portfolio: SimulatedPortfolio,
    ) -> list[Signal]:
        """Validate signals against risk rules.

        Args:
            signals: Proposed signals.
            portfolio: Current portfolio state.

        Returns:
            Approved signals.
        """
        if self._trading_halted:
            logger.warning(f"Trading halted: {self._halt_reason}")
            return []

        # Check drawdown halt
        if portfolio.drawdown <= self.config.risk_rules.max_drawdown_halt:
            self._trading_halted = True
            self._halt_reason = f"Max drawdown {portfolio.drawdown:.1%} exceeded"
            logger.warning(self._halt_reason)
            return []

        approved = []
        for signal in signals:
            if self._validate_signal(signal, portfolio):
                approved.append(signal)

        return approved

    def _validate_signal(
        self,
        signal: Signal,
        portfolio: SimulatedPortfolio,
    ) -> bool:
        """Validate a single signal."""
        # Check position limit
        if signal.target_weight is not None:
            if signal.target_weight > self.config.risk_rules.max_position_pct:
                logger.debug(
                    f"Signal rejected: {signal.symbol} weight {signal.target_weight:.1%} "
                    f"> max {self.config.risk_rules.max_position_pct:.0%}"
                )
                return False

        # Check stop-loss (existing positions)
        pos = portfolio.get_position(signal.symbol)
        if pos and pos.unrealized_pnl_pct <= self.config.risk_rules.position_stop_loss:
            if signal.side == OrderSide.BUY:
                logger.debug(f"Signal rejected: {signal.symbol} in stop-loss")
                return False

        return True

    def check_stop_losses(self, portfolio: SimulatedPortfolio) -> list[Signal]:
        """Generate stop-loss signals for positions.

        Args:
            portfolio: Current portfolio.

        Returns:
            Stop-loss sell signals.
        """
        signals = []
        for symbol, pos in portfolio.positions.items():
            if pos.unrealized_pnl_pct <= self.config.risk_rules.position_stop_loss:
                signals.append(Signal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    side=OrderSide.SELL,
                    target_weight=0.0,
                    reason=f"Stop-loss at {pos.unrealized_pnl_pct:.1%}",
                ))
        return signals


class HistoricalDataHandler:
    """Handles historical data for backtesting.

    Streams bars in chronological order for event-driven processing.
    """

    def __init__(self, config: BacktestConfig, data: Optional[pd.DataFrame] = None):
        self.config = config
        self._data = data
        self._current_idx = 0
        self._symbols: list[str] = []

    def load_data(self, data: pd.DataFrame):
        """Load historical price data.

        Args:
            data: DataFrame with DatetimeIndex and symbol columns.
                  Each column should contain closing prices.
        """
        self._data = data
        self._symbols = list(data.columns)
        self._current_idx = 0

    def stream_bars(self) -> Iterator[MarketEvent]:
        """Stream market events chronologically.

        Yields:
            MarketEvent for each bar/timestamp.
        """
        if self._data is None or self._data.empty:
            return

        # Filter to date range
        start = pd.Timestamp(self.config.start_date)
        end = pd.Timestamp(self.config.end_date)
        data = self._data.loc[start:end]

        for timestamp, row in data.iterrows():
            bars = {}
            for symbol in self._symbols:
                price = row.get(symbol)
                if pd.notna(price) and price > 0:
                    # Create bar from price (for daily data, OHLC = close)
                    bars[symbol] = BarData(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=price,
                        high=price,
                        low=price,
                        close=price,
                        volume=1_000_000,  # Default volume
                    )

            if bars:
                yield MarketEvent(timestamp=timestamp, bars=bars)

    def stream_ohlcv_bars(
        self,
        ohlcv_data: dict[str, pd.DataFrame],
    ) -> Iterator[MarketEvent]:
        """Stream OHLCV data for multiple symbols.

        Args:
            ohlcv_data: Dict of symbol -> DataFrame with OHLCV columns.

        Yields:
            MarketEvent for each timestamp.
        """
        # Collect all timestamps
        all_timestamps = set()
        for df in ohlcv_data.values():
            all_timestamps.update(df.index)

        # Sort and filter
        timestamps = sorted(all_timestamps)
        start = pd.Timestamp(self.config.start_date)
        end = pd.Timestamp(self.config.end_date)
        timestamps = [t for t in timestamps if start <= t <= end]

        for timestamp in timestamps:
            bars = {}
            for symbol, df in ohlcv_data.items():
                if timestamp in df.index:
                    row = df.loc[timestamp]
                    bars[symbol] = BarData(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=row.get("Open", row.get("open", row.get("Close", 0))),
                        high=row.get("High", row.get("high", row.get("Close", 0))),
                        low=row.get("Low", row.get("low", row.get("Close", 0))),
                        close=row.get("Close", row.get("close", 0)),
                        volume=int(row.get("Volume", row.get("volume", 1_000_000))),
                    )

            if bars:
                yield MarketEvent(timestamp=timestamp, bars=bars)


class BacktestEngine:
    """Professional event-driven backtesting engine.

    Example:
        config = BacktestConfig(
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100_000,
        )
        engine = BacktestEngine(config)
        engine.load_data(price_data)
        result = engine.run(my_strategy)
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or DEFAULT_BACKTEST

        # Components
        self.data_handler = HistoricalDataHandler(self.config)
        self.broker = SimulatedBroker(
            self.config.execution,
            self.config.cost_model,
            self.config.seed,
        )
        self.portfolio = SimulatedPortfolio(self.config.initial_capital)
        self.risk_manager = BacktestRiskManager(self.config)

        # Benchmark data
        self._benchmark_prices: Optional[pd.Series] = None

        # Rebalance tracking
        self._last_rebalance: Optional[datetime] = None

    def load_data(self, price_data: pd.DataFrame, benchmark: Optional[pd.Series] = None):
        """Load price data for backtesting.

        Args:
            price_data: DataFrame with DatetimeIndex, columns are symbols.
            benchmark: Optional benchmark price series.
        """
        self.data_handler.load_data(price_data)
        self._benchmark_prices = benchmark

    def run(self, strategy: Strategy) -> BacktestResult:
        """Run backtest with given strategy.

        Args:
            strategy: Strategy implementing on_bar method.

        Returns:
            BacktestResult with all performance data.
        """
        logger.info(
            f"Starting backtest: {self.config.start_date} to {self.config.end_date}"
        )

        # Reset state
        self.portfolio.reset()
        self._last_rebalance = None

        # Main event loop
        for event in self.data_handler.stream_bars():
            self._process_event(event, strategy)

        # Compile results
        result = self._compile_results()

        logger.info(
            f"Backtest complete: {result.metrics.total_return:.1%} return, "
            f"Sharpe {result.metrics.sharpe_ratio:.2f}"
        )

        return result

    def _process_event(self, event: MarketEvent, strategy: Strategy):
        """Process a single market event.

        Args:
            event: Market event with bar data.
            strategy: Strategy instance.
        """
        # 1. Update market data in portfolio
        self.portfolio.update_market_data(event)

        # 2. Process pending orders
        for symbol, bar in event.bars.items():
            fills = self.broker.process_bar(bar)
            for fill in fills:
                self.portfolio.process_fill(fill)
                if hasattr(strategy, 'on_fill'):
                    strategy.on_fill(fill)

        # 3. Check stop-losses
        stop_signals = self.risk_manager.check_stop_losses(self.portfolio)
        for signal in stop_signals:
            self._execute_signal(signal, event)

        # 4. Check if it's rebalance time
        if self._should_rebalance(event.timestamp):
            # Generate strategy signals
            signals = strategy.on_bar(event, self.portfolio)

            # Risk validation
            approved_signals = self.risk_manager.validate(signals, self.portfolio)

            # Execute approved signals
            for signal in approved_signals:
                self._execute_signal(signal, event)

            self._last_rebalance = event.timestamp

        # 5. Record portfolio snapshot
        self.portfolio.record_snapshot(event.timestamp)

    def _should_rebalance(self, timestamp: datetime) -> bool:
        """Check if it's time to rebalance."""
        if self._last_rebalance is None:
            return True

        freq = self.config.rebalance_frequency
        days_since = (timestamp - self._last_rebalance).days

        if freq == RebalanceFrequency.DAILY:
            return days_since >= 1
        elif freq == RebalanceFrequency.WEEKLY:
            return days_since >= 7
        elif freq == RebalanceFrequency.MONTHLY:
            return days_since >= 28 or timestamp.month != self._last_rebalance.month
        elif freq == RebalanceFrequency.QUARTERLY:
            return days_since >= 90
        elif freq == RebalanceFrequency.YEARLY:
            return days_since >= 365

        return False

    def _execute_signal(self, signal: Signal, event: MarketEvent):
        """Convert signal to order and submit.

        Args:
            signal: Trading signal.
            event: Current market event.
        """
        bar = event.get_bar(signal.symbol)
        if not bar:
            return

        # Calculate order quantity
        if signal.target_weight is not None:
            # Weight-based signal
            current_weight = self.portfolio.get_position_weight(signal.symbol)
            target_value = self.portfolio.equity * signal.target_weight
            current_value = self.portfolio.equity * current_weight

            delta_value = target_value - current_value
            qty = int(abs(delta_value) / bar.close)

            if delta_value > 0:
                side = OrderSide.BUY
            elif delta_value < 0:
                side = OrderSide.SELL
            else:
                return  # No change needed
        elif signal.target_shares is not None:
            # Share-based signal
            pos = self.portfolio.get_position(signal.symbol)
            current_shares = pos.qty if pos else 0
            delta = signal.target_shares - current_shares

            if delta > 0:
                side = OrderSide.BUY
                qty = delta
            elif delta < 0:
                side = OrderSide.SELL
                qty = abs(delta)
            else:
                return
        else:
            # Direct signal
            side = signal.side
            qty = 100  # Default lot size

        if qty <= 0:
            return

        # Create and submit order
        order = Order(
            order_id=self.broker.executor.generate_order_id(),
            symbol=signal.symbol,
            side=side,
            qty=qty,
            order_type=signal.order_type,
            limit_price=signal.limit_price,
            stop_price=signal.stop_price,
            created_at=event.timestamp,
        )

        self.broker.submit_order(order)

    def _compile_results(self) -> BacktestResult:
        """Compile backtest results and metrics."""
        # Get equity and returns
        equity_curve = self.portfolio.get_equity_curve()
        drawdown_curve = self.portfolio.get_drawdown_curve()
        returns = self.portfolio.get_returns()

        # Benchmark returns
        benchmark_curve = pd.Series(dtype=float)
        benchmark_returns = pd.Series(dtype=float)
        if self._benchmark_prices is not None:
            benchmark_curve = self._benchmark_prices.reindex(equity_curve.index).ffill()
            benchmark_returns = benchmark_curve.pct_change().dropna()

        # Monthly returns
        monthly_returns = pd.Series(dtype=float)
        if len(returns) > 0:
            monthly_returns = (1 + returns).resample('ME').prod() - 1

        # Calculate metrics
        metrics = self._calculate_metrics(
            returns, benchmark_returns, equity_curve, drawdown_curve
        )

        return BacktestResult(
            config=self.config.__dict__,
            metrics=metrics,
            equity_curve=equity_curve,
            benchmark_curve=benchmark_curve,
            drawdown_curve=drawdown_curve,
            trades=self.portfolio.trades,
            snapshots=self.portfolio.snapshots,
            monthly_returns=monthly_returns,
            daily_returns=returns,
        )

    def _calculate_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series,
        equity_curve: pd.Series,
        drawdown_curve: pd.Series,
    ) -> BacktestMetrics:
        """Calculate comprehensive performance metrics."""
        metrics = BacktestMetrics()

        if len(returns) < 2:
            return metrics

        # Total return
        metrics.total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1

        # CAGR
        n_days = (equity_curve.index[-1] - equity_curve.index[0]).days
        n_years = n_days / 365.25
        if n_years > 0:
            metrics.cagr = (1 + metrics.total_return) ** (1 / n_years) - 1

        # Benchmark metrics
        if len(benchmark_returns) > 0:
            metrics.benchmark_return = (1 + benchmark_returns).prod() - 1
            if n_years > 0:
                metrics.benchmark_cagr = (1 + metrics.benchmark_return) ** (1 / n_years) - 1
            metrics.alpha = metrics.cagr - metrics.benchmark_cagr

        # Risk metrics
        metrics.volatility = returns.std() * np.sqrt(252)
        downside = returns[returns < 0]
        if len(downside) > 0:
            metrics.downside_volatility = downside.std() * np.sqrt(252)

        # Drawdown
        metrics.max_drawdown = drawdown_curve.min()
        metrics.avg_drawdown = drawdown_curve[drawdown_curve < 0].mean() if (drawdown_curve < 0).any() else 0

        # Risk-adjusted returns
        rf_daily = 0.05 / 252  # 5% annual risk-free rate
        excess_returns = returns - rf_daily

        if metrics.volatility > 0:
            metrics.sharpe_ratio = (excess_returns.mean() * 252) / metrics.volatility

        if metrics.downside_volatility > 0:
            metrics.sortino_ratio = (excess_returns.mean() * 252) / metrics.downside_volatility

        if abs(metrics.max_drawdown) > 0.001:
            metrics.calmar_ratio = metrics.cagr / abs(metrics.max_drawdown)

        # Information ratio
        if len(benchmark_returns) > 0:
            active_returns = returns - benchmark_returns.reindex(returns.index).fillna(0)
            tracking_error = active_returns.std() * np.sqrt(252)
            if tracking_error > 0:
                metrics.information_ratio = (active_returns.mean() * 252) / tracking_error

        # Trade metrics
        trades = self.portfolio.trades
        metrics.total_trades = len(trades)

        if trades:
            pnls = [t.pnl for t in trades]
            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p <= 0]

            metrics.winning_trades = len(winners)
            metrics.losing_trades = len(losers)
            metrics.win_rate = len(winners) / len(trades) if trades else 0

            metrics.avg_win = np.mean(winners) if winners else 0
            metrics.avg_loss = np.mean(losers) if losers else 0
            metrics.avg_trade_pnl = np.mean(pnls)

            gross_profit = sum(winners)
            gross_loss = abs(sum(losers))
            metrics.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

            metrics.avg_hold_days = np.mean([t.hold_days for t in trades])

        # Costs
        costs = self.portfolio.get_total_costs()
        metrics.total_commission = costs["commission"]
        metrics.total_slippage = costs["slippage"]
        metrics.total_fees = costs["fees"]
        metrics.total_costs = costs["total"]
        metrics.turnover = self.portfolio.get_turnover()

        # Monthly stats
        if len(returns) > 20:
            monthly = (1 + returns).resample('ME').prod() - 1
            metrics.best_month = monthly.max()
            metrics.worst_month = monthly.min()
            metrics.positive_months = (monthly > 0).sum()
            metrics.negative_months = (monthly <= 0).sum()

        return metrics
