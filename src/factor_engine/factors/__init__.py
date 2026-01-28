"""Factor categories registry."""

from src.factor_engine.factors.base import FactorCategory
from src.factor_engine.factors.value import ValueFactors
from src.factor_engine.factors.momentum import MomentumFactors
from src.factor_engine.factors.quality import QualityFactors
from src.factor_engine.factors.growth import GrowthFactors
from src.factor_engine.factors.volatility import VolatilityFactors
from src.factor_engine.factors.technical import TechnicalFactors


class FactorRegistry:
    """Registry of all factor categories."""

    def __init__(self):
        self.categories = {
            "value": ValueFactors(),
            "momentum": MomentumFactors(),
            "quality": QualityFactors(),
            "growth": GrowthFactors(),
            "volatility": VolatilityFactors(),
            "technical": TechnicalFactors(),
        }

    def get(self, name: str) -> FactorCategory:
        return self.categories[name]

    def all(self) -> dict[str, FactorCategory]:
        return self.categories

    @property
    def names(self) -> list[str]:
        return list(self.categories.keys())


__all__ = [
    "FactorCategory",
    "FactorRegistry",
    "ValueFactors",
    "MomentumFactors",
    "QualityFactors",
    "GrowthFactors",
    "VolatilityFactors",
    "TechnicalFactors",
]
