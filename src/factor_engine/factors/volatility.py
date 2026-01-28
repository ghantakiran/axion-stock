"""Volatility factor category: Risk and stability metrics from price data."""

import numpy as np
import pandas as pd

from src.factor_engine.factors.base import (
    FactorCategory,
    percentile_rank,
    invert_rank,
    safe_divide,
)


class VolatilityFactors(FactorCategory):
    """Volatility factors: Risk-based metrics computed from price history.

    Sub-factors:
    - Realized Volatility (60d) - standard deviation of returns
    - Beta - systematic risk relative to market
    - Downside Beta - beta using only negative market days
    - Max Drawdown (6m) - peak-to-trough decline
    - Idiosyncratic Volatility - residual vol after removing market effect

    Lower volatility = higher score (low-vol anomaly).
    """

    name = "volatility"
    sub_factors = [
        "realized_vol_60d",
        "beta",
        "downside_beta",
        "max_drawdown_6m",
        "idiosyncratic_vol",
    ]

    # Sub-factor weights (sum to 1.0)
    weights = {
        "realized_vol_60d": 0.30,
        "beta": 0.20,
        "downside_beta": 0.20,
        "max_drawdown_6m": 0.20,
        "idiosyncratic_vol": 0.10,
    }

    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.Series:
        """Compute volatility factor score for all tickers."""
        sub_scores = self.compute_sub_factors(prices, fundamentals, returns)

        if sub_scores.empty:
            return pd.Series(0.5, index=prices.columns if not prices.empty else [])

        # Weighted average of available sub-factors
        tickers = sub_scores.index
        score = pd.Series(0.0, index=tickers)
        total_weight = pd.Series(0.0, index=tickers)

        for factor, weight in self.weights.items():
            if factor in sub_scores.columns:
                col = sub_scores[factor]
                valid_mask = col.notna()
                score = score.add(weight * col.fillna(0), fill_value=0)
                total_weight = total_weight.add(
                    weight * valid_mask.astype(float), fill_value=0
                )

        # Normalize by actual weights used
        score = safe_divide(score, total_weight.replace(0, 1))
        return score.fillna(0.5)

    def compute_sub_factors(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """Compute individual volatility sub-factor scores."""
        if prices.empty:
            return pd.DataFrame()

        # Calculate daily returns
        daily_returns = prices.pct_change().dropna()
        if daily_returns.empty:
            return pd.DataFrame()

        tickers = prices.columns
        result = pd.DataFrame(index=tickers)

        # Realized Volatility (60-day) - lower is better
        if len(daily_returns) >= 60:
            vol_60d = daily_returns.iloc[-60:].std() * np.sqrt(252)  # Annualized
            result["realized_vol_60d"] = invert_rank(vol_60d)
        elif len(daily_returns) >= 20:
            vol = daily_returns.std() * np.sqrt(252)
            result["realized_vol_60d"] = invert_rank(vol)

        # Beta relative to market (using SPY or first column as market proxy)
        # For simplicity, use equal-weighted market return
        market_returns = daily_returns.mean(axis=1)

        if len(daily_returns) >= 60:
            window = daily_returns.iloc[-60:]
            market_window = market_returns.iloc[-60:]
            market_var = market_window.var()

            if market_var > 0:
                betas = {}
                downside_betas = {}

                for ticker in tickers:
                    if ticker in window.columns:
                        stock_returns = window[ticker].dropna()
                        aligned_market = market_window.loc[stock_returns.index]

                        if len(stock_returns) > 10:
                            # Beta = Cov(stock, market) / Var(market)
                            cov = stock_returns.cov(aligned_market)
                            beta = cov / market_var if market_var > 0 else 1.0
                            betas[ticker] = beta

                            # Downside beta: only negative market days
                            neg_mask = aligned_market < 0
                            if neg_mask.sum() > 5:
                                neg_market = aligned_market[neg_mask]
                                neg_stock = stock_returns.loc[neg_market.index]
                                neg_var = neg_market.var()
                                if neg_var > 0:
                                    neg_cov = neg_stock.cov(neg_market)
                                    downside_betas[ticker] = neg_cov / neg_var

                if betas:
                    beta_series = pd.Series(betas)
                    # Lower beta is better (inverted)
                    result["beta"] = invert_rank(beta_series.reindex(tickers))

                if downside_betas:
                    db_series = pd.Series(downside_betas)
                    # Lower downside beta is better (inverted)
                    result["downside_beta"] = invert_rank(db_series.reindex(tickers))

        # Max Drawdown (6 months / ~126 trading days) - lower is better
        lookback = min(126, len(prices))
        if lookback >= 20:
            price_window = prices.iloc[-lookback:]
            drawdowns = {}

            for ticker in tickers:
                if ticker in price_window.columns:
                    p = price_window[ticker].dropna()
                    if len(p) > 0:
                        running_max = p.expanding().max()
                        dd = (p - running_max) / running_max
                        max_dd = dd.min()  # Most negative = worst drawdown
                        drawdowns[ticker] = abs(max_dd)  # Convert to positive

            if drawdowns:
                dd_series = pd.Series(drawdowns)
                # Lower drawdown is better (inverted)
                result["max_drawdown_6m"] = invert_rank(dd_series.reindex(tickers))

        # Idiosyncratic Volatility - residual vol after removing market effect
        if len(daily_returns) >= 60 and "beta" in result.columns:
            idio_vols = {}
            window = daily_returns.iloc[-60:]
            market_window = market_returns.iloc[-60:]

            for ticker in tickers:
                if ticker in window.columns and ticker in result.index:
                    beta = result.loc[ticker, "beta"] if "beta" in result.columns else 0.5
                    # Convert inverted rank back to approximate beta
                    # This is an approximation; ideally store raw beta
                    stock_returns = window[ticker].dropna()
                    aligned_market = market_window.loc[stock_returns.index]

                    if len(stock_returns) > 10:
                        # Residual = stock return - beta * market return
                        # Using simple residual volatility
                        residual = stock_returns - aligned_market
                        idio_vol = residual.std() * np.sqrt(252)
                        idio_vols[ticker] = idio_vol

            if idio_vols:
                idio_series = pd.Series(idio_vols)
                # Lower idiosyncratic vol is better (inverted)
                result["idiosyncratic_vol"] = invert_rank(idio_series.reindex(tickers))

        return result
