"""Technical factor category: Price-based technical indicators."""

import numpy as np
import pandas as pd

from src.factor_engine.factors.base import (
    FactorCategory,
    percentile_rank,
    safe_divide,
)


class TechnicalFactors(FactorCategory):
    """Technical factors: Price-based technical analysis indicators.

    Sub-factors:
    - RSI (14-day) - Relative Strength Index (mean-reversion signal)
    - MACD Signal - trend strength
    - Volume Trend - volume breakout indicator
    - Price vs 200 SMA - long-term trend
    - Price vs 50 SMA - medium-term trend
    - Bollinger Band %B - mean reversion position

    Higher technical scores indicate bullish positioning.
    """

    name = "technical"
    sub_factors = [
        "rsi_14",
        "macd_signal",
        "volume_trend",
        "price_vs_200sma",
        "price_vs_50sma",
        "bollinger_pct_b",
    ]

    # Sub-factor weights (sum to 1.0)
    weights = {
        "rsi_14": 0.15,
        "macd_signal": 0.20,
        "volume_trend": 0.10,
        "price_vs_200sma": 0.25,
        "price_vs_50sma": 0.20,
        "bollinger_pct_b": 0.10,
    }

    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.Series:
        """Compute technical factor score for all tickers."""
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
        """Compute individual technical sub-factor scores."""
        if prices.empty:
            return pd.DataFrame()

        tickers = prices.columns
        result = pd.DataFrame(index=tickers)

        # RSI (14-day)
        if len(prices) >= 15:
            rsi_values = self._compute_rsi(prices, period=14)
            # RSI near 50 is neutral; we score higher RSI as bullish
            # But extreme RSI (>70 or <30) can signal reversal
            # Use a modified scoring: 30-70 range mapped to 0.3-0.7, edges get 0.5
            rsi_scores = {}
            for ticker in tickers:
                if ticker in rsi_values:
                    rsi = rsi_values[ticker]
                    if pd.isna(rsi):
                        rsi_scores[ticker] = 0.5
                    elif rsi < 30:
                        # Oversold - potential bounce (moderate bullish)
                        rsi_scores[ticker] = 0.4
                    elif rsi > 70:
                        # Overbought - potential pullback (moderate bearish)
                        rsi_scores[ticker] = 0.6
                    else:
                        # Linear mapping: 30-70 → 0.3-0.7
                        rsi_scores[ticker] = 0.3 + (rsi - 30) / 40 * 0.4

            if rsi_scores:
                result["rsi_14"] = pd.Series(rsi_scores)

        # MACD Signal (positive MACD histogram = bullish)
        if len(prices) >= 35:
            macd_signals = self._compute_macd_signal(prices)
            if macd_signals:
                # Positive signal = bullish, rank across universe
                macd_series = pd.Series(macd_signals)
                result["macd_signal"] = percentile_rank(macd_series.reindex(tickers))

        # Volume Trend (20d avg / 60d avg) - requires volume data
        # Skip if no volume data available
        # For now, use price-based proxy (price volatility trend)
        if len(prices) >= 60:
            vol_trend = self._compute_volatility_trend(prices)
            if vol_trend:
                # Higher recent activity = bullish (momentum continuation)
                result["volume_trend"] = percentile_rank(
                    pd.Series(vol_trend).reindex(tickers)
                )

        # Price vs 200-day SMA (above = bullish)
        if len(prices) >= 200:
            sma_200 = prices.iloc[-200:].mean()
            current = prices.iloc[-1]
            pct_above_200 = safe_divide(current - sma_200, sma_200)
            result["price_vs_200sma"] = percentile_rank(pct_above_200)
        elif len(prices) >= 50:
            # Use available data for trend
            sma = prices.mean()
            current = prices.iloc[-1]
            pct_above = safe_divide(current - sma, sma)
            result["price_vs_200sma"] = percentile_rank(pct_above)

        # Price vs 50-day SMA
        if len(prices) >= 50:
            sma_50 = prices.iloc[-50:].mean()
            current = prices.iloc[-1]
            pct_above_50 = safe_divide(current - sma_50, sma_50)
            result["price_vs_50sma"] = percentile_rank(pct_above_50)

        # Bollinger Band %B
        if len(prices) >= 20:
            bb_pct = self._compute_bollinger_pct_b(prices, period=20)
            if bb_pct:
                # %B near 0.5 = neutral, >0.5 = upper half (bullish momentum)
                # Use raw percentile for cross-sectional comparison
                result["bollinger_pct_b"] = percentile_rank(
                    pd.Series(bb_pct).reindex(tickers)
                )

        return result

    def _compute_rsi(self, prices: pd.DataFrame, period: int = 14) -> dict:
        """Compute RSI for each ticker."""
        rsi_values = {}
        daily_returns = prices.pct_change()

        for ticker in prices.columns:
            returns = daily_returns[ticker].dropna()
            if len(returns) < period + 1:
                continue

            gains = returns.clip(lower=0)
            losses = (-returns).clip(lower=0)

            avg_gain = gains.iloc[-period:].mean()
            avg_loss = losses.iloc[-period:].mean()

            if avg_loss == 0:
                rsi_values[ticker] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_values[ticker] = 100.0 - (100.0 / (1.0 + rs))

        return rsi_values

    def _compute_macd_signal(self, prices: pd.DataFrame) -> dict:
        """Compute MACD histogram (MACD line - Signal line) for each ticker."""
        signals = {}

        for ticker in prices.columns:
            p = prices[ticker].dropna()
            if len(p) < 35:
                continue

            # EMA 12
            ema_12 = p.ewm(span=12, adjust=False).mean()
            # EMA 26
            ema_26 = p.ewm(span=26, adjust=False).mean()
            # MACD line
            macd_line = ema_12 - ema_26
            # Signal line (9-day EMA of MACD)
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            # Histogram
            histogram = macd_line - signal_line

            signals[ticker] = histogram.iloc[-1]

        return signals

    def _compute_volatility_trend(self, prices: pd.DataFrame) -> dict:
        """Compute short-term vs long-term volatility as volume proxy."""
        trends = {}
        daily_returns = prices.pct_change()

        for ticker in prices.columns:
            returns = daily_returns[ticker].dropna()
            if len(returns) < 60:
                continue

            vol_20 = returns.iloc[-20:].std()
            vol_60 = returns.iloc[-60:].std()

            if vol_60 > 0:
                trends[ticker] = vol_20 / vol_60
            else:
                trends[ticker] = 1.0

        return trends

    def _compute_bollinger_pct_b(self, prices: pd.DataFrame, period: int = 20) -> dict:
        """Compute Bollinger Band %B for each ticker."""
        pct_b = {}

        for ticker in prices.columns:
            p = prices[ticker].dropna()
            if len(p) < period:
                continue

            sma = p.iloc[-period:].mean()
            std = p.iloc[-period:].std()

            if std == 0:
                pct_b[ticker] = 0.5
            else:
                upper = sma + 2 * std
                lower = sma - 2 * std
                current = p.iloc[-1]
                # %B = (Price - Lower) / (Upper - Lower)
                band_width = upper - lower
                if band_width > 0:
                    pct_b[ticker] = (current - lower) / band_width
                else:
                    pct_b[ticker] = 0.5

        return pct_b
