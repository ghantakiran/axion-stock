"""Market Scenario Stress Testing.

Apply market scenarios to portfolios for stress testing.
"""

from copy import deepcopy
from typing import Optional
import logging

from src.scenarios.config import (
    ScenarioType,
    SECTOR_BETAS,
    DEFAULT_MARKET_CRASH,
    DEFAULT_BEAR_MARKET,
    DEFAULT_BLACK_SWAN,
)
from src.scenarios.models import (
    Portfolio,
    MarketScenario,
    ScenarioResult,
    PositionImpact,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Predefined Scenarios
# =============================================================================

PREDEFINED_SCENARIOS = {
    ScenarioType.MARKET_CRASH: MarketScenario(
        name="Market Crash (-20%)",
        description="A significant market correction of 20%",
        scenario_type=ScenarioType.MARKET_CRASH,
        market_change_pct=-0.20,
        sector_impacts={
            "Technology": -0.25,
            "Consumer Cyclical": -0.25,
            "Financial": -0.22,
            "Energy": -0.20,
            "Industrial": -0.20,
            "Basic Materials": -0.18,
            "Communication Services": -0.18,
            "Healthcare": -0.15,
            "Real Estate": -0.15,
            "Consumer Defensive": -0.12,
            "Utilities": -0.10,
        },
        is_predefined=True,
    ),
    ScenarioType.BEAR_MARKET: MarketScenario(
        name="Bear Market (-35%)",
        description="Extended bear market with 35% decline",
        scenario_type=ScenarioType.BEAR_MARKET,
        market_change_pct=-0.35,
        sector_impacts={
            "Technology": -0.45,
            "Consumer Cyclical": -0.42,
            "Financial": -0.40,
            "Energy": -0.35,
            "Industrial": -0.35,
            "Basic Materials": -0.32,
            "Communication Services": -0.32,
            "Real Estate": -0.30,
            "Healthcare": -0.25,
            "Consumer Defensive": -0.20,
            "Utilities": -0.18,
        },
        is_predefined=True,
    ),
    ScenarioType.BULL_MARKET: MarketScenario(
        name="Bull Market (+25%)",
        description="Strong bull market rally",
        scenario_type=ScenarioType.BULL_MARKET,
        market_change_pct=0.25,
        sector_impacts={
            "Technology": 0.35,
            "Consumer Cyclical": 0.30,
            "Financial": 0.28,
            "Industrial": 0.25,
            "Basic Materials": 0.25,
            "Communication Services": 0.22,
            "Energy": 0.20,
            "Real Estate": 0.20,
            "Healthcare": 0.18,
            "Consumer Defensive": 0.15,
            "Utilities": 0.12,
        },
        is_predefined=True,
    ),
    ScenarioType.SECTOR_ROTATION: MarketScenario(
        name="Sector Rotation (Tech to Value)",
        description="Rotation from growth/tech to value sectors",
        scenario_type=ScenarioType.SECTOR_ROTATION,
        market_change_pct=0.0,
        sector_impacts={
            "Technology": -0.15,
            "Communication Services": -0.12,
            "Consumer Cyclical": -0.08,
            "Financial": 0.10,
            "Energy": 0.12,
            "Industrial": 0.08,
            "Basic Materials": 0.08,
            "Healthcare": 0.05,
            "Utilities": 0.06,
            "Consumer Defensive": 0.05,
            "Real Estate": 0.03,
        },
        is_predefined=True,
    ),
    ScenarioType.RATE_SPIKE: MarketScenario(
        name="Interest Rate Spike",
        description="Sharp increase in interest rates",
        scenario_type=ScenarioType.RATE_SPIKE,
        market_change_pct=-0.10,
        sector_impacts={
            "Real Estate": -0.20,
            "Utilities": -0.15,
            "Technology": -0.15,
            "Consumer Cyclical": -0.12,
            "Communication Services": -0.10,
            "Healthcare": -0.08,
            "Consumer Defensive": -0.05,
            "Industrial": -0.05,
            "Financial": 0.08,
            "Energy": 0.0,
            "Basic Materials": -0.05,
        },
        is_predefined=True,
    ),
    ScenarioType.RECESSION: MarketScenario(
        name="Recession",
        description="Economic recession scenario",
        scenario_type=ScenarioType.RECESSION,
        market_change_pct=-0.25,
        sector_impacts={
            "Consumer Cyclical": -0.40,
            "Industrial": -0.35,
            "Financial": -0.35,
            "Technology": -0.30,
            "Basic Materials": -0.30,
            "Energy": -0.28,
            "Communication Services": -0.25,
            "Real Estate": -0.22,
            "Healthcare": -0.15,
            "Consumer Defensive": -0.10,
            "Utilities": -0.08,
        },
        is_predefined=True,
    ),
    ScenarioType.INFLATION: MarketScenario(
        name="Inflation Surge",
        description="High inflation environment",
        scenario_type=ScenarioType.INFLATION,
        market_change_pct=-0.08,
        sector_impacts={
            "Technology": -0.18,
            "Consumer Cyclical": -0.15,
            "Real Estate": -0.12,
            "Communication Services": -0.10,
            "Financial": -0.05,
            "Healthcare": -0.05,
            "Consumer Defensive": -0.03,
            "Industrial": 0.0,
            "Basic Materials": 0.10,
            "Energy": 0.15,
            "Utilities": 0.05,
        },
        is_predefined=True,
    ),
    ScenarioType.BLACK_SWAN: MarketScenario(
        name="Black Swan Event (-50%)",
        description="Extreme market event",
        scenario_type=ScenarioType.BLACK_SWAN,
        market_change_pct=-0.50,
        sector_impacts={
            "Technology": -0.60,
            "Consumer Cyclical": -0.58,
            "Financial": -0.55,
            "Energy": -0.50,
            "Industrial": -0.50,
            "Basic Materials": -0.48,
            "Communication Services": -0.48,
            "Real Estate": -0.45,
            "Healthcare": -0.40,
            "Consumer Defensive": -0.35,
            "Utilities": -0.30,
        },
        is_predefined=True,
    ),
}


class ScenarioAnalyzer:
    """Applies market scenarios to portfolios.
    
    Stress test portfolios against various market conditions.
    
    Example:
        analyzer = ScenarioAnalyzer()
        
        # Apply a crash scenario
        result = analyzer.apply_scenario(
            portfolio,
            ScenarioType.MARKET_CRASH
        )
        print(f"Portfolio would lose: ${abs(result.value_change):,.2f}")
    """
    
    def __init__(self):
        self._scenarios = PREDEFINED_SCENARIOS.copy()
    
    def get_scenario(self, scenario_type: ScenarioType) -> Optional[MarketScenario]:
        """Get a predefined scenario."""
        return self._scenarios.get(scenario_type)
    
    def get_all_scenarios(self) -> list[MarketScenario]:
        """Get all predefined scenarios."""
        return list(self._scenarios.values())
    
    def add_custom_scenario(self, scenario: MarketScenario) -> None:
        """Add a custom scenario."""
        self._scenarios[scenario.scenario_type] = scenario
    
    def apply_scenario(
        self,
        portfolio: Portfolio,
        scenario: MarketScenario | ScenarioType,
    ) -> ScenarioResult:
        """Apply a scenario to a portfolio.
        
        Args:
            portfolio: Portfolio to stress test.
            scenario: Scenario to apply (type or object).
            
        Returns:
            ScenarioResult with impact analysis.
        """
        # Get scenario object
        if isinstance(scenario, ScenarioType):
            scenario_obj = self._scenarios.get(scenario)
            if not scenario_obj:
                raise ValueError(f"Unknown scenario type: {scenario}")
        else:
            scenario_obj = scenario
        
        result = ScenarioResult(
            scenario=scenario_obj,
            portfolio=portfolio,
            starting_value=portfolio.total_value,
        )
        
        # Apply scenario to each position
        position_impacts = []
        total_ending_value = portfolio.cash  # Cash unchanged
        
        for holding in portfolio.holdings:
            # Determine change for this position
            change_pct = self._get_position_change(holding, scenario_obj)
            
            starting = holding.market_value
            ending = starting * (1 + change_pct)
            change = ending - starting
            
            impact = PositionImpact(
                symbol=holding.symbol,
                starting_value=starting,
                ending_value=ending,
                change=change,
                change_pct=change_pct * 100,
                sector=holding.sector,
            )
            position_impacts.append(impact)
            total_ending_value += ending
        
        # Sort by impact
        position_impacts.sort(key=lambda x: x.change)
        
        result.position_impacts = position_impacts
        result.ending_value = total_ending_value
        result.value_change = total_ending_value - result.starting_value
        result.pct_change = (result.value_change / result.starting_value * 100
                            if result.starting_value > 0 else 0)
        
        # Analysis
        result.positions_down = sum(1 for p in position_impacts if p.change < 0)
        result.positions_up = sum(1 for p in position_impacts if p.change > 0)
        result.max_loss = min(p.change for p in position_impacts) if position_impacts else 0
        
        result.worst_performers = [p.symbol for p in position_impacts[:3]]
        result.best_performers = [p.symbol for p in position_impacts[-3:]]
        result.best_performers.reverse()
        
        return result
    
    def _get_position_change(
        self,
        holding,
        scenario: MarketScenario,
    ) -> float:
        """Get the change percentage for a position."""
        # Check for symbol override
        if holding.symbol in scenario.symbol_overrides:
            return scenario.symbol_overrides[holding.symbol]
        
        # Check for sector-specific impact
        if holding.sector in scenario.sector_impacts:
            return scenario.sector_impacts[holding.sector]
        
        # Use market-wide change with beta adjustment
        beta = SECTOR_BETAS.get(holding.sector, 1.0)
        return scenario.market_change_pct * beta
    
    def run_all_scenarios(
        self,
        portfolio: Portfolio,
    ) -> list[ScenarioResult]:
        """Run all predefined scenarios on a portfolio.
        
        Args:
            portfolio: Portfolio to stress test.
            
        Returns:
            List of ScenarioResults.
        """
        results = []
        for scenario in self._scenarios.values():
            result = self.apply_scenario(portfolio, scenario)
            results.append(result)
        return results
    
    def create_custom_scenario(
        self,
        name: str,
        market_change: float,
        sector_impacts: Optional[dict[str, float]] = None,
        symbol_overrides: Optional[dict[str, float]] = None,
    ) -> MarketScenario:
        """Create a custom scenario.
        
        Args:
            name: Scenario name.
            market_change: Market-wide change (e.g., -0.20 for -20%).
            sector_impacts: Sector-specific changes.
            symbol_overrides: Symbol-specific changes.
            
        Returns:
            Custom MarketScenario.
        """
        return MarketScenario(
            name=name,
            description=f"Custom scenario: {name}",
            scenario_type=ScenarioType.CUSTOM,
            market_change_pct=market_change,
            sector_impacts=sector_impacts or {},
            symbol_overrides=symbol_overrides or {},
            is_predefined=False,
        )
