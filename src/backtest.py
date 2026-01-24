"""Historical monthly-rebalance backtest engine."""

import numpy as np
import pandas as pd
import yfinance as yf

import config


def run_backtest(
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame,
    months: int = None,
    verbose: bool = False,
) -> dict:
    """Run monthly rebalance backtest over historical data.

    Uses only data available up to each rebalance date (no look-ahead bias).
    Returns dict with portfolio_returns, benchmark_returns, and metrics.
    """
    if months is None:
        months = config.BACKTEST_MONTHS

    # Get benchmark data
    benchmark_prices = prices.get(config.BENCHMARK_TICKER)
    if benchmark_prices is None:
        try:
            spy = yf.download(config.BENCHMARK_TICKER, period="2y", auto_adjust=True, progress=False)
            benchmark_prices = spy["Close"]
        except Exception:
            benchmark_prices = pd.Series(dtype=float)

    # Generate monthly rebalance dates
    monthly_idx = prices.resample("ME").last().index
    if len(monthly_idx) < 3:
        return {"error": "Insufficient data for backtest"}

    rebalance_dates = monthly_idx[-months:] if len(monthly_idx) >= months else monthly_idx

    portfolio_returns = []
    benchmark_returns = []

    for i in range(len(rebalance_dates) - 1):
        date_start = rebalance_dates[i]
        date_end = rebalance_dates[i + 1]

        # Data available up to rebalance date (no look-ahead)
        available_prices = prices.loc[:date_start]

        if len(available_prices) < 22:
            continue

        # Compute momentum from available data
        from src.data_fetcher import compute_price_returns
        from src.factor_model import compute_composite_scores

        returns_df = compute_price_returns(available_prices)
        fund_subset = fundamentals.reindex(returns_df.index).fillna(fundamentals.median(numeric_only=True))

        scores = compute_composite_scores(fund_subset, returns_df)

        # Select top stocks
        top_n = scores.nlargest(config.TOP_N_STOCKS, "composite")
        selected = top_n.index.tolist()

        # Equal-weight for backtest simplicity
        period_prices = prices.loc[date_start:date_end]
        if len(period_prices) < 2:
            continue

        # Portfolio return (equal-weighted)
        stock_returns = []
        for ticker in selected:
            if ticker in period_prices.columns:
                t_prices = period_prices[ticker].dropna()
                if len(t_prices) >= 2:
                    ret = t_prices.iloc[-1] / t_prices.iloc[0] - 1
                    stock_returns.append(ret)

        if stock_returns:
            port_ret = np.mean(stock_returns)
            portfolio_returns.append(port_ret)
        else:
            portfolio_returns.append(0.0)

        # Benchmark return
        if benchmark_prices is not None and not benchmark_prices.empty:
            bench_period = benchmark_prices.loc[date_start:date_end]
            if len(bench_period) >= 2:
                b_ret = bench_period.iloc[-1] / bench_period.iloc[0] - 1
                benchmark_returns.append(b_ret)
            else:
                benchmark_returns.append(0.0)
        else:
            benchmark_returns.append(0.0)

    # Compute metrics
    port_rets = np.array(portfolio_returns)
    bench_rets = np.array(benchmark_returns)

    metrics = _compute_metrics(port_rets, bench_rets)

    return {
        "portfolio_returns": port_rets,
        "benchmark_returns": bench_rets,
        "rebalance_dates": rebalance_dates,
        "metrics": metrics,
    }


def _compute_metrics(portfolio_returns: np.ndarray, benchmark_returns: np.ndarray) -> dict:
    """Compute backtest performance metrics."""
    if len(portfolio_returns) == 0:
        return {}

    # Cumulative returns
    port_cum = np.cumprod(1 + portfolio_returns)
    bench_cum = np.cumprod(1 + benchmark_returns) if len(benchmark_returns) > 0 else np.array([1.0])

    # CAGR
    n_months = len(portfolio_returns)
    port_total = port_cum[-1]
    port_cagr = (port_total ** (12 / n_months) - 1) if n_months > 0 else 0

    bench_total = bench_cum[-1] if len(bench_cum) > 0 else 1.0
    bench_cagr = (bench_total ** (12 / n_months) - 1) if n_months > 0 else 0

    # Monthly average
    avg_monthly = np.mean(portfolio_returns)

    # Sharpe ratio (annualized)
    monthly_rf = config.RISK_FREE_RATE / 12
    excess = portfolio_returns - monthly_rf
    sharpe = (np.mean(excess) / np.std(excess) * np.sqrt(12)) if np.std(excess) > 0 else 0

    # Max drawdown
    port_cum_series = np.cumprod(1 + portfolio_returns)
    running_max = np.maximum.accumulate(port_cum_series)
    drawdowns = port_cum_series / running_max - 1
    max_drawdown = np.min(drawdowns)

    # Win rate
    win_rate = np.mean(portfolio_returns > 0)

    return {
        "n_months": n_months,
        "portfolio_cagr": port_cagr,
        "benchmark_cagr": bench_cagr,
        "avg_monthly_return": avg_monthly,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "total_return": port_total - 1,
        "benchmark_total_return": bench_total - 1,
    }


def format_backtest_results(results: dict) -> str:
    """Format backtest metrics as readable text."""
    if "error" in results:
        return f"Backtest error: {results['error']}"

    m = results["metrics"]
    lines = [
        "=" * 50,
        "BACKTEST RESULTS",
        "=" * 50,
        f"Period:              {m['n_months']} months",
        f"Portfolio CAGR:      {m['portfolio_cagr']*100:.1f}%",
        f"Benchmark CAGR:      {m['benchmark_cagr']*100:.1f}%",
        f"Avg Monthly Return:  {m['avg_monthly_return']*100:.2f}%",
        f"Sharpe Ratio:        {m['sharpe_ratio']:.2f}",
        f"Max Drawdown:        {m['max_drawdown']*100:.1f}%",
        f"Win Rate:            {m['win_rate']*100:.0f}%",
        f"Total Return:        {m['total_return']*100:.1f}%",
        f"Benchmark Return:    {m['benchmark_total_return']*100:.1f}%",
        "=" * 50,
    ]
    return "\n".join(lines)
