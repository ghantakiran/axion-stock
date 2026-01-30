"""Regime Detection Module - Market regime classification for adaptive factor weights.

Classifies the market into one of four regimes:
- Bull: Rising prices, low VIX, positive breadth → Favor Momentum, Growth
- Bear: Falling prices, high VIX, negative breadth → Favor Quality, Low-Vol, Value
- Sideways: Range-bound, moderate VIX → Favor Value, Dividend, Quality
- Crisis: VIX >35, correlation spike, rapid decline → Minimum-Variance, Cash
"""

from src.regime.detector import RegimeDetector, MarketRegime
from src.regime.weights import AdaptiveWeights, REGIME_WEIGHTS

__all__ = [
    "RegimeDetector",
    "MarketRegime",
    "AdaptiveWeights",
    "REGIME_WEIGHTS",
]
