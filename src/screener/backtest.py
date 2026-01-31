"""Screen Backtesting.

Backtest screening strategies on historical data.
"""

from datetime import date, timedelta
from typing import Optional
import logging
import math

from src.screener.config import (
    BacktestConfig,
    DEFAULT_BACKTEST_CONFIG,
    RebalanceFrequency,
)
from src.screener.models import (
    Screen,
    ScreenBacktestConfig,
    ScreenBacktestResult,
)
from src.screener.engine import ScreenerEngine

logger = logging.getLogger(__name__)


class ScreenBacktester:
    """Backtests screening strategies.
    
    Simulates running a screen historically and measures
    portfolio performance.
    
    Example:
        backtester = ScreenBacktester()
        result = backtester.run(screen, historical_data, config)
    """
    
    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        engine: Optional[ScreenerEngine] = None,
    ):
        self.config = config or DEFAULT_BACKTEST_CONFIG
        self.engine = engine or ScreenerEngine()
    
    def run(
        self,
        screen: Screen,
        historical_data: dict[date, dict[str, dict]],
        backtest_config: Optional[ScreenBacktestConfig] = None,
    ) -> ScreenBacktestResult:
        """Run a backtest on a screen.
        
        Args:
            screen: Screen to backtest.
            historical_data: Dict of date -> symbol -> metrics.
            backtest_config: Backtest configuration.
            
        Returns:
            ScreenBacktestResult with performance metrics.
        """
        config = backtest_config or ScreenBacktestConfig(screen_id=screen.screen_id)
        
        # Get date range
        dates = sorted(historical_data.keys())
        if config.start_date:
            dates = [d for d in dates if d >= config.start_date]
        if config.end_date:
            dates = [d for d in dates if d <= config.end_date]
        
        if len(dates) < 2:
            logger.warning("Insufficient data for backtest")
            return ScreenBacktestResult(
                screen_id=screen.screen_id,
                screen_name=screen.name,
                config=config,
            )
        
        # Determine rebalance dates
        rebalance_dates = self._get_rebalance_dates(dates, config.rebalance_frequency)
        
        # Run backtest
        equity_curve = [1.0]  # Start with $1
        benchmark_curve = [1.0]
        holdings_history = []
        current_holdings = {}
        
        for i, current_date in enumerate(dates[:-1]):
            next_date = dates[i + 1]
            
            # Rebalance if needed
            if current_date in rebalance_dates:
                # Run screen
                stock_data = historical_data[current_date]
                result = self.engine.run_screen(screen, stock_data)
                
                # Select top N matches
                new_holdings = {}
                for match in result.stocks[:config.max_positions]:
                    if config.equal_weight:
                        weight = 1.0 / min(len(result.stocks), config.max_positions)
                    else:
                        weight = 1.0 / config.max_positions
                    new_holdings[match.symbol] = {
                        "weight": weight,
                        "price": match.price,
                    }
                
                current_holdings = new_holdings
                holdings_history.append({
                    "date": current_date,
                    "holdings": list(current_holdings.keys()),
                })
            
            # Calculate return
            period_return = self._calculate_period_return(
                current_holdings,
                historical_data.get(current_date, {}),
                historical_data.get(next_date, {}),
            )
            
            # Apply transaction costs on rebalance
            if current_date in rebalance_dates:
                period_return -= config.transaction_cost_bps / 10000
            
            equity_curve.append(equity_curve[-1] * (1 + period_return))
            
            # Benchmark return (simplified)
            benchmark_return = self._calculate_benchmark_return(
                config.benchmark,
                historical_data.get(current_date, {}),
                historical_data.get(next_date, {}),
            )
            benchmark_curve.append(benchmark_curve[-1] * (1 + benchmark_return))
        
        # Calculate metrics
        returns = self._calculate_returns(equity_curve)
        benchmark_returns = self._calculate_returns(benchmark_curve)
        
        total_return = equity_curve[-1] / equity_curve[0] - 1
        benchmark_total = benchmark_curve[-1] / benchmark_curve[0] - 1
        
        years = len(dates) / 252  # Approximate trading days
        annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        volatility = self._calculate_volatility(returns)
        sharpe = self._calculate_sharpe(returns, 0.04)  # Assume 4% risk-free
        sortino = self._calculate_sortino(returns, 0.04)
        max_dd = self._calculate_max_drawdown(equity_curve)
        
        return ScreenBacktestResult(
            screen_id=screen.screen_id,
            screen_name=screen.name,
            config=config,
            total_return=total_return * 100,
            annualized_return=annualized * 100,
            benchmark_return=benchmark_total * 100,
            alpha=(annualized - (benchmark_total / years if years > 0 else 0)) * 100,
            volatility=volatility * 100,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd * 100,
            equity_curve=equity_curve,
            benchmark_curve=benchmark_curve,
            dates=dates,
            holdings_history=holdings_history,
        )
    
    def _get_rebalance_dates(
        self,
        dates: list[date],
        frequency: RebalanceFrequency,
    ) -> set[date]:
        """Get dates when rebalancing should occur."""
        if not dates:
            return set()
        
        rebalance_dates = {dates[0]}  # Always rebalance on first day
        
        if frequency == RebalanceFrequency.DAILY:
            return set(dates)
        
        for i, d in enumerate(dates):
            if frequency == RebalanceFrequency.WEEKLY:
                # Rebalance on Mondays
                if d.weekday() == 0:
                    rebalance_dates.add(d)
            
            elif frequency == RebalanceFrequency.MONTHLY:
                # Rebalance on first day of month
                if i == 0 or d.month != dates[i - 1].month:
                    rebalance_dates.add(d)
            
            elif frequency == RebalanceFrequency.QUARTERLY:
                # Rebalance on first day of quarter
                if i == 0 or (d.month in [1, 4, 7, 10] and d.month != dates[i - 1].month):
                    rebalance_dates.add(d)
        
        return rebalance_dates
    
    def _calculate_period_return(
        self,
        holdings: dict[str, dict],
        current_data: dict[str, dict],
        next_data: dict[str, dict],
    ) -> float:
        """Calculate portfolio return for a period."""
        if not holdings:
            return 0.0
        
        total_return = 0.0
        total_weight = 0.0
        
        for symbol, position in holdings.items():
            weight = position.get("weight", 0)
            
            current_price = current_data.get(symbol, {}).get("price", 0)
            next_price = next_data.get(symbol, {}).get("price", 0)
            
            if current_price > 0 and next_price > 0:
                stock_return = (next_price - current_price) / current_price
                total_return += weight * stock_return
                total_weight += weight
        
        if total_weight > 0:
            return total_return / total_weight * total_weight
        return 0.0
    
    def _calculate_benchmark_return(
        self,
        benchmark: str,
        current_data: dict[str, dict],
        next_data: dict[str, dict],
    ) -> float:
        """Calculate benchmark return for a period."""
        current_price = current_data.get(benchmark, {}).get("price", 0)
        next_price = next_data.get(benchmark, {}).get("price", 0)
        
        if current_price > 0 and next_price > 0:
            return (next_price - current_price) / current_price
        return 0.0
    
    def _calculate_returns(self, equity_curve: list[float]) -> list[float]:
        """Calculate period returns from equity curve."""
        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i - 1] > 0:
                returns.append(equity_curve[i] / equity_curve[i - 1] - 1)
        return returns
    
    def _calculate_volatility(self, returns: list[float]) -> float:
        """Calculate annualized volatility."""
        if len(returns) < 2:
            return 0.0
        
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        
        return daily_vol * math.sqrt(252)
    
    def _calculate_sharpe(self, returns: list[float], risk_free: float) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns) * 252  # Annualized
        vol = self._calculate_volatility(returns)
        
        if vol > 0:
            return (mean_return - risk_free) / vol
        return 0.0
    
    def _calculate_sortino(self, returns: list[float], risk_free: float) -> float:
        """Calculate Sortino ratio."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns) * 252
        
        # Downside deviation
        negative_returns = [r for r in returns if r < 0]
        if not negative_returns:
            return float('inf') if mean_return > risk_free else 0.0
        
        downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
        downside_vol = math.sqrt(downside_variance) * math.sqrt(252)
        
        if downside_vol > 0:
            return (mean_return - risk_free) / downside_vol
        return 0.0
    
    def _calculate_max_drawdown(self, equity_curve: list[float]) -> float:
        """Calculate maximum drawdown."""
        if len(equity_curve) < 2:
            return 0.0
        
        peak = equity_curve[0]
        max_dd = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
        
        return max_dd
