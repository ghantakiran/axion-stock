"""High-level backtest runner for bot strategies.

Wraps BacktestEngine with OHLCV data support and enriched results
including signal attribution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd

from src.backtesting.config import (
    BacktestConfig,
    CostModelConfig,
    RebalanceFrequency,
)
from src.backtesting.engine import BacktestEngine, HistoricalDataHandler
from src.backtesting.models import BacktestResult, WalkForwardResult
from src.backtesting.optimization import WalkForwardOptimizer
from src.bot_backtesting.attribution import AttributionReport, SignalAttributor
from src.bot_backtesting.strategy import EMACloudStrategy, StrategyConfig
from src.ema_signals.detector import SignalType

logger = logging.getLogger(__name__)


@dataclass
class BotBacktestConfig:
    """Configuration for a bot strategy backtest."""

    start_date: date = field(default_factory=lambda: date(2020, 1, 1))
    end_date: date = field(default_factory=lambda: date(2024, 12, 31))
    initial_capital: float = 100_000.0
    tickers: list[str] = field(
        default_factory=lambda: [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
            "META", "TSLA", "JPM", "V", "JNJ",
            "WMT", "PG", "MA", "UNH", "HD",
            "DIS", "PYPL", "NFLX", "ADBE", "CRM",
        ]
    )
    min_conviction: int = 50
    enabled_signal_types: list[SignalType] = field(
        default_factory=lambda: list(SignalType)
    )
    max_positions: int = 10
    max_position_weight: float = 0.15
    timeframe: str = "1d"
    cloud_config: Optional[dict] = None
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.DAILY
    cost_model: CostModelConfig = field(default_factory=CostModelConfig)


@dataclass
class EnrichedBacktestResult:
    """Backtest result enriched with signal attribution."""

    result: BacktestResult
    attribution: AttributionReport
    strategy_config: StrategyConfig
    tickers: list[str] = field(default_factory=list)

    @property
    def metrics(self):
        return self.result.metrics

    @property
    def trades(self):
        return self.result.trades

    @property
    def equity_curve(self):
        return self.result.equity_curve


class BotBacktestRunner:
    """Run backtests with EMA Cloud strategies on OHLCV data.

    Key difference from standard BacktestEngine.run(): this runner
    uses stream_ohlcv_bars() instead of stream_bars() so that
    the EMA Cloud strategy receives real OHLCV data (not just closes).
    """

    def run(
        self,
        config: BotBacktestConfig,
        ohlcv_data: dict[str, pd.DataFrame],
        benchmark: Optional[pd.Series] = None,
    ) -> EnrichedBacktestResult:
        """Run a bot strategy backtest.

        Args:
            config: Backtest configuration.
            ohlcv_data: Dict of symbol -> OHLCV DataFrame.
            benchmark: Optional benchmark price series.

        Returns:
            EnrichedBacktestResult with attribution.
        """
        # Build BacktestConfig
        bt_config = BacktestConfig(
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            cost_model=config.cost_model,
            rebalance_frequency=config.rebalance_frequency,
        )

        # Create engine
        engine = BacktestEngine(bt_config)
        engine._benchmark_prices = benchmark

        # Build strategy kwargs
        strategy_kwargs = {
            "min_conviction": config.min_conviction,
            "enabled_signal_types": config.enabled_signal_types,
            "max_positions": config.max_positions,
            "max_position_weight": config.max_position_weight,
            "timeframe": config.timeframe,
        }
        if config.cloud_config:
            strategy_kwargs.update(config.cloud_config)

        strategy = EMACloudStrategy(**strategy_kwargs)

        # Run with OHLCV data
        result = self._run_with_ohlcv(engine, strategy, ohlcv_data)

        # Build attribution
        attributor = SignalAttributor()
        attribution = attributor.compute(
            strategy.get_signal_log(), result.trades
        )

        return EnrichedBacktestResult(
            result=result,
            attribution=attribution,
            strategy_config=strategy.config,
            tickers=list(ohlcv_data.keys()),
        )

    def run_walk_forward(
        self,
        config: BotBacktestConfig,
        ohlcv_data: dict[str, pd.DataFrame],
        param_grid: dict[str, list],
        benchmark: Optional[pd.Series] = None,
    ) -> WalkForwardResult:
        """Run walk-forward optimization with EMA Cloud strategy.

        Uses the existing WalkForwardOptimizer with EMACloudStrategy
        class + param grid. Note: walk-forward uses close-only data
        (stream_bars), which is acceptable for parameter optimization.

        Args:
            config: Base backtest configuration.
            ohlcv_data: OHLCV data for multiple symbols.
            param_grid: Parameter grid for optimization.
            benchmark: Optional benchmark prices.

        Returns:
            WalkForwardResult from the optimizer.
        """
        # Build close-only price data for walk-forward
        price_data = self._build_close_only(ohlcv_data)

        bt_config = BacktestConfig(
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            cost_model=config.cost_model,
            rebalance_frequency=config.rebalance_frequency,
        )

        optimizer = WalkForwardOptimizer(backtest_config=bt_config)
        return optimizer.run(
            strategy_class=EMACloudStrategy,
            param_grid=param_grid,
            price_data=price_data,
            benchmark=benchmark,
        )

    def _run_with_ohlcv(
        self,
        engine: BacktestEngine,
        strategy: EMACloudStrategy,
        ohlcv_data: dict[str, pd.DataFrame],
    ) -> BacktestResult:
        """Custom event loop using stream_ohlcv_bars.

        Bypasses engine.run() which uses close-only stream_bars().
        Instead, directly calls _process_event() in a loop over
        OHLCV bar events.
        """
        # Reset portfolio
        engine.portfolio.reset()
        engine._last_rebalance = None

        # Stream OHLCV bars through the data handler
        for event in engine.data_handler.stream_ohlcv_bars(ohlcv_data):
            engine._process_event(event, strategy)

        # Compile results
        return engine._compile_results()

    def _build_close_only(
        self, ohlcv_data: dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """Build a close-only DataFrame from OHLCV data.

        Required by WalkForwardOptimizer which expects a
        DataFrame with symbol columns containing close prices.
        """
        close_series = {}
        for symbol, df in ohlcv_data.items():
            close_col = "Close" if "Close" in df.columns else "close"
            if close_col in df.columns:
                close_series[symbol] = df[close_col]

        if not close_series:
            return pd.DataFrame()

        return pd.DataFrame(close_series).sort_index()
