"""Factor Engine v2.0 - Expanded multi-factor model with regime awareness.

This module provides 12+ factors across 6 categories:
- Value: Earnings yield, FCF yield, book-to-market, EV/EBITDA, dividend yield, forward P/E
- Momentum: 12-1m, 6-1m, 3m momentum, 52-week high proximity, earnings/revenue momentum
- Quality: ROE, ROA, ROIC, gross profit/assets, accruals, debt/equity, interest coverage
- Growth: Revenue growth, EPS growth, FCF growth, growth acceleration, R&D intensity
- Volatility: Realized vol, idiosyncratic vol, beta, downside beta, max drawdown
- Technical: RSI, MACD, volume trend, price vs SMA indicators, Bollinger bands
"""

from src.factors.base import Factor, FactorCategory
from src.factors.registry import FactorRegistry
from src.factors.value import ValueFactors
from src.factors.momentum import MomentumFactors
from src.factors.quality import QualityFactors
from src.factors.growth import GrowthFactors
from src.factors.volatility import VolatilityFactors
from src.factors.technical import TechnicalFactors

__all__ = [
    "Factor",
    "FactorCategory",
    "FactorRegistry",
    "ValueFactors",
    "MomentumFactors",
    "QualityFactors",
    "GrowthFactors",
    "VolatilityFactors",
    "TechnicalFactors",
]
