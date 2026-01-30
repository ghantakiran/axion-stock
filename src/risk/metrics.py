"""Risk Metrics Engine.

Calculates portfolio-level and position-level risk metrics including:
- Beta, volatility, Sharpe, Sortino, Calmar ratios
- Drawdown metrics
- Concentration metrics
- Correlation analysis
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRiskMetrics:
    """Portfolio-level risk metrics."""

    # Performance ratios
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0

    # Risk measures
    portfolio_beta: float = 1.0
    portfolio_volatility: float = 0.0  # Annualized
    correlation_to_spy: float = 0.0
    tracking_error: float = 0.0
    active_share: float = 0.0

    # Drawdown
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    drawdown_duration_days: int = 0

    # VaR metrics (filled by VaR calculator)
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0

    # Returns
    daily_return: float = 0.0
    mtd_return: float = 0.0
    ytd_return: float = 0.0
    total_return: float = 0.0
    cagr: float = 0.0

    # Timestamp
    calculated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PositionRiskMetrics:
    """Position-level risk metrics."""

    symbol: str
    market_value: float
    weight: float  # % of portfolio

    # P&L
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    # Drawdown
    position_drawdown: float = 0.0  # Peak-to-current
    distance_to_stop: float = 0.0  # Current price vs stop

    # Time
    days_held: int = 0

    # Risk contribution
    risk_contribution: float = 0.0  # % of portfolio risk
    marginal_var: float = 0.0  # Portfolio VaR change if removed
    beta: float = 1.0
    beta_adjusted_exposure: float = 0.0  # Position value × beta
    volatility: float = 0.0  # Annualized

    # Entry tracking
    entry_price: float = 0.0
    current_price: float = 0.0
    high_since_entry: float = 0.0


@dataclass
class ConcentrationMetrics:
    """Portfolio concentration metrics."""

    # Position concentration
    largest_position_weight: float = 0.0
    largest_position_symbol: str = ""
    top5_weight: float = 0.0
    herfindahl_index: float = 0.0  # Concentration measure (0-1)

    # Sector concentration
    largest_sector_weight: float = 0.0
    largest_sector_name: str = ""
    sector_count: int = 0

    # Industry concentration
    largest_industry_weight: float = 0.0
    largest_industry_name: str = ""

    # Correlation clusters
    high_correlation_pairs: int = 0
    max_correlation_cluster_size: int = 0
    average_correlation: float = 0.0


class RiskMetricsCalculator:
    """Calculates risk metrics for portfolios and positions.

    Example:
        calculator = RiskMetricsCalculator()

        # Calculate portfolio metrics
        metrics = calculator.calculate_portfolio_metrics(
            positions=positions,
            returns=portfolio_returns,
            benchmark_returns=spy_returns,
            risk_free_rate=0.05,
        )

        # Calculate concentration
        concentration = calculator.calculate_concentration(
            positions=positions,
            sector_map=sector_map,
        )
    """

    # Risk-free rate (annualized)
    DEFAULT_RISK_FREE_RATE = 0.05  # 5%
    TRADING_DAYS_PER_YEAR = 252

    def __init__(self, risk_free_rate: Optional[float] = None):
        """Initialize calculator.

        Args:
            risk_free_rate: Annualized risk-free rate.
        """
        self.risk_free_rate = risk_free_rate or self.DEFAULT_RISK_FREE_RATE

    # =========================================================================
    # Portfolio Metrics
    # =========================================================================

    def calculate_portfolio_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        portfolio_value: float = 0.0,
    ) -> PortfolioRiskMetrics:
        """Calculate comprehensive portfolio risk metrics.

        Args:
            returns: Daily portfolio returns series.
            benchmark_returns: Daily benchmark (SPY) returns.
            portfolio_value: Current portfolio value.

        Returns:
            PortfolioRiskMetrics with all calculated metrics.
        """
        metrics = PortfolioRiskMetrics()

        if len(returns) < 2:
            return metrics

        # Clean data
        returns = returns.dropna()
        if benchmark_returns is not None:
            benchmark_returns = benchmark_returns.dropna()

        # Basic statistics
        mean_return = returns.mean()
        std_return = returns.std()

        # Annualized volatility
        metrics.portfolio_volatility = std_return * np.sqrt(self.TRADING_DAYS_PER_YEAR)

        # Daily risk-free rate
        daily_rf = self.risk_free_rate / self.TRADING_DAYS_PER_YEAR

        # Sharpe Ratio (annualized)
        if std_return > 0:
            excess_return = mean_return - daily_rf
            metrics.sharpe_ratio = (excess_return * self.TRADING_DAYS_PER_YEAR) / metrics.portfolio_volatility

        # Sortino Ratio (uses downside deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std()
            if downside_std > 0:
                downside_vol = downside_std * np.sqrt(self.TRADING_DAYS_PER_YEAR)
                excess_return_ann = (mean_return - daily_rf) * self.TRADING_DAYS_PER_YEAR
                metrics.sortino_ratio = excess_return_ann / downside_vol

        # Drawdown calculations
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max

        metrics.current_drawdown = drawdown.iloc[-1] if len(drawdown) > 0 else 0
        metrics.max_drawdown = drawdown.min()

        # Drawdown duration
        if metrics.current_drawdown < 0:
            # Find when the drawdown started
            peak_idx = cumulative[cumulative == running_max.iloc[-1]].index[-1]
            metrics.drawdown_duration_days = len(drawdown[peak_idx:])

        # Calmar Ratio (CAGR / Max Drawdown)
        total_days = len(returns)
        if total_days > 0:
            total_return = cumulative.iloc[-1] - 1
            metrics.total_return = total_return

            years = total_days / self.TRADING_DAYS_PER_YEAR
            if years > 0:
                metrics.cagr = (1 + total_return) ** (1 / years) - 1

            if abs(metrics.max_drawdown) > 0.001:
                metrics.calmar_ratio = metrics.cagr / abs(metrics.max_drawdown)

        # Returns breakdown
        metrics.daily_return = returns.iloc[-1] if len(returns) > 0 else 0

        # MTD return
        if len(returns) > 0:
            today = returns.index[-1]
            mtd_mask = returns.index >= pd.Timestamp(today.year, today.month, 1)
            mtd_returns = returns[mtd_mask]
            if len(mtd_returns) > 0:
                metrics.mtd_return = (1 + mtd_returns).prod() - 1

        # YTD return
        if len(returns) > 0:
            today = returns.index[-1]
            ytd_mask = returns.index >= pd.Timestamp(today.year, 1, 1)
            ytd_returns = returns[ytd_mask]
            if len(ytd_returns) > 0:
                metrics.ytd_return = (1 + ytd_returns).prod() - 1

        # Benchmark-relative metrics
        if benchmark_returns is not None and len(benchmark_returns) > 1:
            # Align returns
            aligned = pd.DataFrame({
                "portfolio": returns,
                "benchmark": benchmark_returns,
            }).dropna()

            if len(aligned) > 1:
                port_ret = aligned["portfolio"]
                bench_ret = aligned["benchmark"]

                # Beta
                cov_matrix = np.cov(port_ret, bench_ret)
                if cov_matrix[1, 1] > 0:
                    metrics.portfolio_beta = cov_matrix[0, 1] / cov_matrix[1, 1]

                # Correlation
                metrics.correlation_to_spy = port_ret.corr(bench_ret)

                # Tracking Error
                active_returns = port_ret - bench_ret
                metrics.tracking_error = active_returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

                # Information Ratio
                if metrics.tracking_error > 0:
                    active_return_ann = active_returns.mean() * self.TRADING_DAYS_PER_YEAR
                    metrics.information_ratio = active_return_ann / metrics.tracking_error

        metrics.calculated_at = datetime.now()
        return metrics

    def calculate_position_metrics(
        self,
        symbol: str,
        position_value: float,
        portfolio_value: float,
        returns: Optional[pd.Series] = None,
        benchmark_returns: Optional[pd.Series] = None,
        entry_price: float = 0.0,
        current_price: float = 0.0,
        high_since_entry: float = 0.0,
        entry_date: Optional[datetime] = None,
        stop_loss_pct: float = -0.15,
    ) -> PositionRiskMetrics:
        """Calculate risk metrics for a single position.

        Args:
            symbol: Stock symbol.
            position_value: Current market value.
            portfolio_value: Total portfolio value.
            returns: Daily returns for the position.
            benchmark_returns: Benchmark returns for beta calculation.
            entry_price: Entry price.
            current_price: Current price.
            high_since_entry: Highest price since entry.
            entry_date: Date position was opened.
            stop_loss_pct: Stop-loss threshold for distance calculation.

        Returns:
            PositionRiskMetrics for the position.
        """
        metrics = PositionRiskMetrics(
            symbol=symbol,
            market_value=position_value,
            weight=position_value / portfolio_value if portfolio_value > 0 else 0,
        )

        # P&L
        if entry_price > 0:
            metrics.entry_price = entry_price
            metrics.current_price = current_price
            metrics.unrealized_pnl_pct = (current_price - entry_price) / entry_price
            qty = position_value / current_price if current_price > 0 else 0
            metrics.unrealized_pnl = qty * (current_price - entry_price)

        # Drawdown from high
        if high_since_entry > 0:
            metrics.high_since_entry = high_since_entry
            metrics.position_drawdown = (current_price - high_since_entry) / high_since_entry

        # Distance to stop
        if entry_price > 0:
            stop_price = entry_price * (1 + stop_loss_pct)
            metrics.distance_to_stop = (current_price - stop_price) / current_price

        # Days held
        if entry_date:
            metrics.days_held = (datetime.now() - entry_date).days

        # Volatility and Beta from returns
        if returns is not None and len(returns) > 1:
            metrics.volatility = returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

            if benchmark_returns is not None and len(benchmark_returns) > 1:
                aligned = pd.DataFrame({
                    "position": returns,
                    "benchmark": benchmark_returns,
                }).dropna()

                if len(aligned) > 1:
                    cov_matrix = np.cov(aligned["position"], aligned["benchmark"])
                    if cov_matrix[1, 1] > 0:
                        metrics.beta = cov_matrix[0, 1] / cov_matrix[1, 1]

        # Beta-adjusted exposure
        metrics.beta_adjusted_exposure = position_value * metrics.beta

        return metrics

    # =========================================================================
    # Concentration Metrics
    # =========================================================================

    def calculate_concentration(
        self,
        positions: list[dict],  # [{symbol, market_value, sector?, industry?}]
        correlation_matrix: Optional[pd.DataFrame] = None,
    ) -> ConcentrationMetrics:
        """Calculate portfolio concentration metrics.

        Args:
            positions: List of position dicts with market_value, sector, industry.
            correlation_matrix: Optional correlation matrix for clustering.

        Returns:
            ConcentrationMetrics.
        """
        metrics = ConcentrationMetrics()

        if not positions:
            return metrics

        # Calculate total portfolio value
        total_value = sum(p.get("market_value", 0) for p in positions)
        if total_value == 0:
            return metrics

        # Calculate weights
        for pos in positions:
            pos["weight"] = pos.get("market_value", 0) / total_value

        # Sort by weight descending
        sorted_positions = sorted(positions, key=lambda x: x.get("weight", 0), reverse=True)

        # Largest position
        if sorted_positions:
            metrics.largest_position_weight = sorted_positions[0].get("weight", 0)
            metrics.largest_position_symbol = sorted_positions[0].get("symbol", "")

        # Top 5 concentration
        metrics.top5_weight = sum(p.get("weight", 0) for p in sorted_positions[:5])

        # Herfindahl Index (sum of squared weights)
        metrics.herfindahl_index = sum(p.get("weight", 0) ** 2 for p in positions)

        # Sector concentration
        sector_weights: dict[str, float] = {}
        for pos in positions:
            sector = pos.get("sector", "Unknown")
            sector_weights[sector] = sector_weights.get(sector, 0) + pos.get("weight", 0)

        metrics.sector_count = len(sector_weights)
        if sector_weights:
            max_sector = max(sector_weights.items(), key=lambda x: x[1])
            metrics.largest_sector_name = max_sector[0]
            metrics.largest_sector_weight = max_sector[1]

        # Industry concentration
        industry_weights: dict[str, float] = {}
        for pos in positions:
            industry = pos.get("industry", "Unknown")
            industry_weights[industry] = industry_weights.get(industry, 0) + pos.get("weight", 0)

        if industry_weights:
            max_industry = max(industry_weights.items(), key=lambda x: x[1])
            metrics.largest_industry_name = max_industry[0]
            metrics.largest_industry_weight = max_industry[1]

        # Correlation analysis
        if correlation_matrix is not None and len(correlation_matrix) > 1:
            symbols = [p.get("symbol") for p in positions if p.get("symbol") in correlation_matrix.columns]

            if len(symbols) > 1:
                corr_subset = correlation_matrix.loc[symbols, symbols]

                # Count high correlation pairs (>0.8)
                high_corr_threshold = 0.8
                mask = np.triu(np.ones_like(corr_subset, dtype=bool), k=1)
                upper_triangle = corr_subset.where(mask)
                high_corr_count = (upper_triangle > high_corr_threshold).sum().sum()
                metrics.high_correlation_pairs = int(high_corr_count)

                # Average correlation (excluding diagonal)
                corr_values = upper_triangle.values.flatten()
                corr_values = corr_values[~np.isnan(corr_values)]
                if len(corr_values) > 0:
                    metrics.average_correlation = float(np.mean(corr_values))

                # Find largest correlation cluster
                # Simple approach: count max number of positions correlated >0.8 with any one position
                max_cluster = 0
                for sym in symbols:
                    cluster_size = (corr_subset.loc[sym, :] > high_corr_threshold).sum()
                    max_cluster = max(max_cluster, cluster_size)
                metrics.max_correlation_cluster_size = max_cluster

        return metrics

    # =========================================================================
    # Standalone Helper Methods
    # =========================================================================

    def calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: Optional[float] = None,
    ) -> float:
        """Calculate Sharpe ratio.

        Args:
            returns: Daily returns series.
            risk_free_rate: Annualized risk-free rate (uses default if not provided).

        Returns:
            Annualized Sharpe ratio.
        """
        if len(returns) < 2:
            return 0.0

        rf = risk_free_rate if risk_free_rate is not None else self.risk_free_rate
        daily_rf = rf / self.TRADING_DAYS_PER_YEAR

        mean_return = returns.mean()
        std_return = returns.std()

        if std_return == 0:
            return 0.0

        excess_return = mean_return - daily_rf
        annualized_vol = std_return * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        return (excess_return * self.TRADING_DAYS_PER_YEAR) / annualized_vol

    def calculate_sortino_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: Optional[float] = None,
    ) -> float:
        """Calculate Sortino ratio.

        Args:
            returns: Daily returns series.
            risk_free_rate: Annualized risk-free rate.

        Returns:
            Annualized Sortino ratio.
        """
        if len(returns) < 2:
            return 0.0

        rf = risk_free_rate if risk_free_rate is not None else self.risk_free_rate
        daily_rf = rf / self.TRADING_DAYS_PER_YEAR

        mean_return = returns.mean()
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0:
            return float('inf') if mean_return > daily_rf else 0.0

        downside_std = downside_returns.std()
        if downside_std == 0:
            return 0.0

        downside_vol = downside_std * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        excess_return_ann = (mean_return - daily_rf) * self.TRADING_DAYS_PER_YEAR
        return excess_return_ann / downside_vol

    def calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown.

        Args:
            returns: Daily returns series.

        Returns:
            Maximum drawdown as negative float.
        """
        if len(returns) < 2:
            return 0.0

        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max

        return float(drawdown.min())

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def calculate_rolling_metrics(
        self,
        returns: pd.Series,
        window: int = 60,
    ) -> pd.DataFrame:
        """Calculate rolling risk metrics.

        Args:
            returns: Daily returns series.
            window: Rolling window size in days.

        Returns:
            DataFrame with rolling Sharpe, volatility, etc.
        """
        df = pd.DataFrame(index=returns.index)

        # Rolling volatility
        df["volatility"] = returns.rolling(window).std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

        # Rolling Sharpe
        daily_rf = self.risk_free_rate / self.TRADING_DAYS_PER_YEAR
        excess = returns - daily_rf
        df["sharpe"] = (
            excess.rolling(window).mean() * self.TRADING_DAYS_PER_YEAR
        ) / df["volatility"]

        # Rolling max drawdown
        cumulative = (1 + returns).cumprod()
        rolling_max = cumulative.rolling(window, min_periods=1).max()
        df["drawdown"] = (cumulative - rolling_max) / rolling_max

        return df

    def calculate_return_distribution(
        self,
        returns: pd.Series,
    ) -> dict:
        """Calculate return distribution statistics.

        Args:
            returns: Daily returns series.

        Returns:
            Dict with distribution statistics.
        """
        returns = returns.dropna()

        if len(returns) < 2:
            return {}

        return {
            "mean": float(returns.mean()),
            "median": float(returns.median()),
            "std": float(returns.std()),
            "skew": float(returns.skew()),
            "kurtosis": float(returns.kurtosis()),
            "min": float(returns.min()),
            "max": float(returns.max()),
            "percentile_5": float(np.percentile(returns, 5)),
            "percentile_25": float(np.percentile(returns, 25)),
            "percentile_75": float(np.percentile(returns, 75)),
            "percentile_95": float(np.percentile(returns, 95)),
            "positive_days_pct": float((returns > 0).mean()),
            "negative_days_pct": float((returns < 0).mean()),
        }
