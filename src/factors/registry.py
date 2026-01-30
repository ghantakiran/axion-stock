"""Factor Registry - Central registry of all factors and their calculators."""

from typing import Optional

import pandas as pd

from src.factors.base import FactorCategory, FactorCalculator


class FactorRegistry:
    """Registry of all factor categories and their calculators.
    
    Provides a unified interface for computing all factors across the universe.
    """
    
    def __init__(self):
        self._categories: dict[str, FactorCategory] = {}
        self._calculators: dict[str, FactorCalculator] = {}
        self._initialized = False
    
    def register(self, name: str, category: FactorCategory, calculator: FactorCalculator) -> None:
        """Register a factor category and its calculator.
        
        Args:
            name: Category name (e.g., 'value', 'momentum')
            category: FactorCategory definition
            calculator: FactorCalculator implementation
        """
        self._categories[name] = category
        self._calculators[name] = calculator
        calculator.category = category
    
    @property
    def categories(self) -> list[str]:
        """List of registered category names."""
        return list(self._categories.keys())
    
    def get_category(self, name: str) -> Optional[FactorCategory]:
        """Get a category by name."""
        return self._categories.get(name)
    
    def get_calculator(self, name: str) -> Optional[FactorCalculator]:
        """Get a calculator by category name."""
        return self._calculators.get(name)
    
    def compute_category(
        self,
        category_name: str,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Compute all factors in a single category.
        
        Args:
            category_name: Name of the category to compute
            prices: Price DataFrame (dates x tickers)
            fundamentals: Fundamentals DataFrame (tickers x fields)
            market_data: Optional market-level data
            
        Returns:
            DataFrame with tickers as index, factor scores as columns
        """
        calculator = self._calculators.get(category_name)
        if calculator is None:
            raise ValueError(f"Unknown category: {category_name}")
        
        return calculator.compute(prices, fundamentals, market_data)
    
    def compute_all(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
    ) -> dict[str, pd.DataFrame]:
        """Compute all factors across all categories.
        
        Args:
            prices: Price DataFrame (dates x tickers)
            fundamentals: Fundamentals DataFrame (tickers x fields)
            market_data: Optional market-level data
            
        Returns:
            Dict mapping category names to DataFrames of factor scores
        """
        results = {}
        for name in self._categories:
            results[name] = self.compute_category(name, prices, fundamentals, market_data)
        return results
    
    def get_default_weights(self) -> dict[str, float]:
        """Get default category weights from registered categories."""
        return {name: cat.default_weight for name, cat in self._categories.items()}
    
    def list_factors(self) -> dict[str, list[str]]:
        """List all factors by category."""
        return {
            name: [f.name for f in cat.factors]
            for name, cat in self._categories.items()
        }
    
    def total_factor_count(self) -> int:
        """Total number of individual factors across all categories."""
        return sum(len(cat.factors) for cat in self._categories.values())


def create_default_registry() -> FactorRegistry:
    """Create and populate the default factor registry with all v2 factors.
    
    Returns:
        Fully populated FactorRegistry
    """
    from src.factors.value import ValueFactors
    from src.factors.momentum import MomentumFactors
    from src.factors.quality import QualityFactors
    from src.factors.growth import GrowthFactors
    from src.factors.volatility import VolatilityFactors
    from src.factors.technical import TechnicalFactors
    
    registry = FactorRegistry()
    
    # Register all factor categories
    value = ValueFactors()
    registry.register("value", value.category, value)
    
    momentum = MomentumFactors()
    registry.register("momentum", momentum.category, momentum)
    
    quality = QualityFactors()
    registry.register("quality", quality.category, quality)
    
    growth = GrowthFactors()
    registry.register("growth", growth.category, growth)
    
    volatility = VolatilityFactors()
    registry.register("volatility", volatility.category, volatility)
    
    technical = TechnicalFactors()
    registry.register("technical", technical.category, technical)
    
    registry._initialized = True
    return registry
