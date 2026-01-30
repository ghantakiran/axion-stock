"""Stress Testing Framework.

Implements historical and hypothetical stress tests to assess
portfolio resilience under adverse market conditions.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StressScenario:
    """Definition of a stress test scenario."""

    name: str
    description: str
    scenario_type: str  # 'historical' or 'hypothetical'

    # For historical scenarios
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # For hypothetical scenarios - factor shocks
    market_shock: float = 0.0  # e.g., -0.20 for 20% market decline
    sector_shocks: dict[str, float] = field(default_factory=dict)  # e.g., {"Technology": -0.30}
    factor_shocks: dict[str, float] = field(default_factory=dict)  # e.g., {"momentum": -0.15}
    interest_rate_shock_bps: float = 0.0  # e.g., 200 for +2%
    volatility_shock: float = 0.0  # e.g., 2.0 for VIX doubling


@dataclass
class StressTestResult:
    """Result of a stress test."""

    scenario_name: str
    portfolio_impact_pct: float  # Estimated portfolio return
    portfolio_impact_dollars: float  # Dollar P&L
    var_impact: float  # How VaR would change

    # Position-level impacts
    position_impacts: dict[str, float] = field(default_factory=dict)

    # Sector impacts
    sector_impacts: dict[str, float] = field(default_factory=dict)

    # Additional context
    worst_positions: list[tuple[str, float]] = field(default_factory=list)  # (symbol, impact)
    best_positions: list[tuple[str, float]] = field(default_factory=list)

    # Derived metrics
    surviving_portfolio_value: float = 0.0  # Value after stress event
    worst_position_symbol: str = ""
    worst_position_impact_pct: float = 0.0

    # Metadata
    calculated_at: datetime = field(default_factory=datetime.now)


# Pre-defined historical scenarios
HISTORICAL_SCENARIOS = [
    StressScenario(
        name="COVID Crash",
        description="Pandemic shock (Feb-Mar 2020)",
        scenario_type="historical",
        start_date=date(2020, 2, 19),
        end_date=date(2020, 3, 23),
    ),
    StressScenario(
        name="2022 Bear Market",
        description="Rate hike cycle (Jan-Oct 2022)",
        scenario_type="historical",
        start_date=date(2022, 1, 3),
        end_date=date(2022, 10, 12),
    ),
    StressScenario(
        name="Volmageddon",
        description="VIX spike event (Feb 2018)",
        scenario_type="historical",
        start_date=date(2018, 2, 2),
        end_date=date(2018, 2, 8),
    ),
    StressScenario(
        name="Trade War",
        description="US-China tariff escalation (May-Dec 2018)",
        scenario_type="historical",
        start_date=date(2018, 5, 1),
        end_date=date(2018, 12, 24),
    ),
    StressScenario(
        name="GFC",
        description="Global Financial Crisis (Sep 2008-Mar 2009)",
        scenario_type="historical",
        start_date=date(2008, 9, 15),
        end_date=date(2009, 3, 9),
    ),
    StressScenario(
        name="Dot-Com Bust",
        description="Tech bubble collapse (Mar 2000-Oct 2002)",
        scenario_type="historical",
        start_date=date(2000, 3, 10),
        end_date=date(2002, 10, 9),
    ),
    StressScenario(
        name="Flash Crash",
        description="May 6, 2010 liquidity vacuum",
        scenario_type="historical",
        start_date=date(2010, 5, 6),
        end_date=date(2010, 5, 7),
    ),
    StressScenario(
        name="2011 Downgrade",
        description="US debt downgrade (Aug 2011)",
        scenario_type="historical",
        start_date=date(2011, 8, 1),
        end_date=date(2011, 8, 10),
    ),
]

# Pre-defined hypothetical scenarios
HYPOTHETICAL_SCENARIOS = [
    StressScenario(
        name="Rate Shock +200bps",
        description="Interest rates rise 2%",
        scenario_type="hypothetical",
        interest_rate_shock_bps=200,
        market_shock=-0.10,
        sector_shocks={
            "Real Estate": -0.20,
            "Utilities": -0.15,
            "Technology": -0.15,
        },
        factor_shocks={
            "growth": -0.20,
            "momentum": -0.10,
        },
    ),
    StressScenario(
        name="Oil Spike +50%",
        description="Energy up, consumer/transport down",
        scenario_type="hypothetical",
        market_shock=-0.05,
        sector_shocks={
            "Energy": 0.30,
            "Consumer Discretionary": -0.15,
            "Industrials": -0.12,
            "Transportation": -0.20,
        },
    ),
    StressScenario(
        name="Tech Correction -30%",
        description="Tech/growth factor crash",
        scenario_type="hypothetical",
        market_shock=-0.15,
        sector_shocks={
            "Technology": -0.30,
            "Communication Services": -0.25,
            "Consumer Discretionary": -0.15,
        },
        factor_shocks={
            "growth": -0.30,
            "momentum": -0.20,
        },
    ),
    StressScenario(
        name="Credit Crisis",
        description="High yield spreads widen, flight to quality",
        scenario_type="hypothetical",
        market_shock=-0.20,
        sector_shocks={
            "Financials": -0.30,
            "Real Estate": -0.25,
        },
        factor_shocks={
            "value": -0.15,
            "quality": 0.05,
        },
    ),
    StressScenario(
        name="Dollar Surge +15%",
        description="USD strength hits multinationals",
        scenario_type="hypothetical",
        market_shock=-0.08,
        sector_shocks={
            "Technology": -0.12,
            "Consumer Staples": -0.10,
            "Materials": -0.15,
        },
    ),
    StressScenario(
        name="Inflation Spike +3%",
        description="CPI acceleration, Fed response",
        scenario_type="hypothetical",
        interest_rate_shock_bps=150,
        market_shock=-0.12,
        sector_shocks={
            "Technology": -0.18,
            "Utilities": -0.12,
            "Consumer Discretionary": -0.15,
            "Energy": 0.10,
            "Materials": 0.05,
        },
        factor_shocks={
            "growth": -0.15,
            "value": 0.05,
        },
    ),
]


class StressTestEngine:
    """Run stress tests on portfolios.

    Example:
        engine = StressTestEngine(historical_data=price_data)

        # Run all historical stress tests
        results = engine.run_historical_tests(
            positions=positions,
            portfolio_value=100_000,
        )

        # Run hypothetical scenarios
        results = engine.run_hypothetical_tests(
            positions=positions,
            portfolio_value=100_000,
            sector_map=sector_map,
        )
    """

    def __init__(
        self,
        historical_data: Optional[pd.DataFrame] = None,
        benchmark_data: Optional[pd.Series] = None,
    ):
        """Initialize stress test engine.

        Args:
            historical_data: DataFrame with historical prices (columns = symbols).
            benchmark_data: Benchmark (SPY) prices for historical scenarios.
        """
        self.historical_data = historical_data
        self.benchmark_data = benchmark_data

        # Pre-compute returns if data provided
        self.historical_returns = None
        self.benchmark_returns = None

        if historical_data is not None:
            self.historical_returns = historical_data.pct_change().dropna()

        if benchmark_data is not None:
            self.benchmark_returns = benchmark_data.pct_change().dropna()

    # =========================================================================
    # Historical Stress Tests
    # =========================================================================

    def run_historical_test(
        self,
        scenario: StressScenario,
        positions: list[dict],  # [{symbol, market_value, weight}]
        portfolio_value: float,
    ) -> StressTestResult:
        """Run a single historical stress test.

        Args:
            scenario: Historical stress scenario.
            positions: Current portfolio positions.
            portfolio_value: Current portfolio value.

        Returns:
            StressTestResult with estimated impact.
        """
        result = StressTestResult(
            scenario_name=scenario.name,
            portfolio_impact_pct=0.0,
            portfolio_impact_dollars=0.0,
            var_impact=0.0,
        )

        if scenario.scenario_type != "historical":
            logger.warning(f"Scenario {scenario.name} is not historical")
            return result

        if self.historical_returns is None:
            logger.warning("No historical data available for stress test")
            return result

        if scenario.start_date is None or scenario.end_date is None:
            return result

        # Get returns during stress period
        start = pd.Timestamp(scenario.start_date)
        end = pd.Timestamp(scenario.end_date)

        mask = (self.historical_returns.index >= start) & (self.historical_returns.index <= end)
        stress_returns = self.historical_returns[mask]

        if len(stress_returns) == 0:
            logger.warning(f"No data for period {scenario.start_date} to {scenario.end_date}")
            return result

        # Calculate cumulative return for each position
        position_impacts = {}
        portfolio_return = 0.0

        for pos in positions:
            symbol = pos.get("symbol", "")
            weight = pos.get("weight", 0)

            if symbol in stress_returns.columns:
                cum_return = (1 + stress_returns[symbol]).prod() - 1
                position_impacts[symbol] = cum_return
                portfolio_return += weight * cum_return
            else:
                # Use benchmark return as proxy
                if self.benchmark_returns is not None:
                    bench_mask = (self.benchmark_returns.index >= start) & (self.benchmark_returns.index <= end)
                    bench_stress = self.benchmark_returns[bench_mask]
                    if len(bench_stress) > 0:
                        cum_return = (1 + bench_stress).prod() - 1
                        position_impacts[symbol] = cum_return
                        portfolio_return += weight * cum_return

        result.portfolio_impact_pct = portfolio_return
        result.portfolio_impact_dollars = portfolio_return * portfolio_value
        result.position_impacts = position_impacts
        result.surviving_portfolio_value = portfolio_value * (1 + portfolio_return)

        # Find worst and best positions
        sorted_impacts = sorted(position_impacts.items(), key=lambda x: x[1])
        result.worst_positions = sorted_impacts[:5]
        result.best_positions = sorted_impacts[-5:][::-1]

        # Set worst position info
        if sorted_impacts:
            result.worst_position_symbol = sorted_impacts[0][0]
            result.worst_position_impact_pct = sorted_impacts[0][1]

        return result

    def run_historical_tests(
        self,
        positions: list[dict],
        portfolio_value: float,
        scenarios: Optional[list[StressScenario]] = None,
    ) -> list[StressTestResult]:
        """Run all historical stress tests.

        Args:
            positions: Current portfolio positions.
            portfolio_value: Current portfolio value.
            scenarios: List of scenarios (uses defaults if not provided).

        Returns:
            List of StressTestResult.
        """
        if scenarios is None:
            scenarios = HISTORICAL_SCENARIOS

        results = []
        for scenario in scenarios:
            result = self.run_historical_test(scenario, positions, portfolio_value)
            results.append(result)

        return results

    # =========================================================================
    # Hypothetical Stress Tests
    # =========================================================================

    def run_hypothetical_test(
        self,
        scenario: StressScenario,
        positions: list[dict],  # [{symbol, market_value, weight, sector?, factor_scores?}]
        portfolio_value: float,
        sector_map: Optional[dict[str, str]] = None,
        factor_scores: Optional[dict[str, dict]] = None,  # {symbol: {value, momentum, ...}}
    ) -> StressTestResult:
        """Run a single hypothetical stress test.

        Args:
            scenario: Hypothetical stress scenario.
            positions: Current portfolio positions with sector info.
            portfolio_value: Current portfolio value.
            sector_map: Mapping of symbol to sector.
            factor_scores: Factor scores by symbol.

        Returns:
            StressTestResult with estimated impact.
        """
        result = StressTestResult(
            scenario_name=scenario.name,
            portfolio_impact_pct=0.0,
            portfolio_impact_dollars=0.0,
            var_impact=0.0,
        )

        if scenario.scenario_type != "hypothetical":
            logger.warning(f"Scenario {scenario.name} is not hypothetical")
            return result

        # Apply sector if not in position
        if sector_map:
            for pos in positions:
                if "sector" not in pos:
                    pos["sector"] = sector_map.get(pos.get("symbol", ""), "Unknown")

        position_impacts = {}
        sector_impacts: dict[str, float] = {}
        portfolio_return = 0.0

        for pos in positions:
            symbol = pos.get("symbol", "")
            weight = pos.get("weight", 0)
            sector = pos.get("sector", "Unknown")

            # Start with market-wide shock
            position_return = scenario.market_shock

            # Add sector-specific shock
            if sector in scenario.sector_shocks:
                sector_shock = scenario.sector_shocks[sector]
                position_return += sector_shock

            # Add factor-based shocks
            if factor_scores and symbol in factor_scores:
                scores = factor_scores[symbol]
                for factor, shock in scenario.factor_shocks.items():
                    if factor in scores:
                        # Weight shock by factor exposure
                        factor_exposure = scores[factor]
                        position_return += shock * factor_exposure

            position_impacts[symbol] = position_return
            portfolio_return += weight * position_return

            # Track sector impacts
            if sector not in sector_impacts:
                sector_impacts[sector] = 0
            sector_impacts[sector] += weight * position_return

        result.portfolio_impact_pct = portfolio_return
        result.portfolio_impact_dollars = portfolio_return * portfolio_value
        result.position_impacts = position_impacts
        result.sector_impacts = sector_impacts
        result.surviving_portfolio_value = portfolio_value * (1 + portfolio_return)

        # Find worst and best positions
        sorted_impacts = sorted(position_impacts.items(), key=lambda x: x[1])
        result.worst_positions = sorted_impacts[:5]
        result.best_positions = sorted_impacts[-5:][::-1]

        # Set worst position info
        if sorted_impacts:
            result.worst_position_symbol = sorted_impacts[0][0]
            result.worst_position_impact_pct = sorted_impacts[0][1]

        return result

    def run_hypothetical_tests(
        self,
        positions: list[dict],
        portfolio_value: float,
        sector_map: Optional[dict[str, str]] = None,
        factor_scores: Optional[dict[str, dict]] = None,
        scenarios: Optional[list[StressScenario]] = None,
    ) -> list[StressTestResult]:
        """Run all hypothetical stress tests.

        Args:
            positions: Current portfolio positions.
            portfolio_value: Current portfolio value.
            sector_map: Symbol to sector mapping.
            factor_scores: Factor scores by symbol.
            scenarios: List of scenarios (uses defaults if not provided).

        Returns:
            List of StressTestResult.
        """
        if scenarios is None:
            scenarios = HYPOTHETICAL_SCENARIOS

        results = []
        for scenario in scenarios:
            result = self.run_hypothetical_test(
                scenario, positions, portfolio_value, sector_map, factor_scores
            )
            results.append(result)

        return results

    # =========================================================================
    # Custom Stress Tests
    # =========================================================================

    def run_custom_shock(
        self,
        positions: list[dict],
        portfolio_value: float,
        market_shock: float = 0.0,
        custom_shocks: Optional[dict[str, float]] = None,  # {symbol: shock}
    ) -> StressTestResult:
        """Run a custom stress test with user-defined shocks.

        Args:
            positions: Current portfolio positions.
            portfolio_value: Current portfolio value.
            market_shock: Market-wide shock to apply.
            custom_shocks: Position-specific shocks.

        Returns:
            StressTestResult.
        """
        custom_shocks = custom_shocks or {}

        result = StressTestResult(
            scenario_name="Custom Shock",
            portfolio_impact_pct=0.0,
            portfolio_impact_dollars=0.0,
            var_impact=0.0,
        )

        position_impacts = {}
        portfolio_return = 0.0

        for pos in positions:
            symbol = pos.get("symbol", "")
            weight = pos.get("weight", 0)

            # Apply custom shock or market shock
            if symbol in custom_shocks:
                position_return = custom_shocks[symbol]
            else:
                position_return = market_shock

            position_impacts[symbol] = position_return
            portfolio_return += weight * position_return

        result.portfolio_impact_pct = portfolio_return
        result.portfolio_impact_dollars = portfolio_return * portfolio_value
        result.position_impacts = position_impacts

        return result

    # =========================================================================
    # Reverse Stress Test
    # =========================================================================

    def reverse_stress_test(
        self,
        positions: list[dict],
        portfolio_value: float,
        target_loss: float,  # e.g., -0.20 for 20% loss
        sector_map: Optional[dict[str, str]] = None,
    ) -> dict:
        """Find what market conditions would cause a specific loss level.

        This is a reverse stress test - given a loss target, find the
        market conditions that would produce it.

        Args:
            positions: Current portfolio positions.
            portfolio_value: Current portfolio value.
            target_loss: Target portfolio loss (negative).
            sector_map: Symbol to sector mapping.

        Returns:
            Dict with scenario that would cause target loss.
        """
        if sector_map:
            for pos in positions:
                if "sector" not in pos:
                    pos["sector"] = sector_map.get(pos.get("symbol", ""), "Unknown")

        # Calculate portfolio beta to market
        total_weight = sum(p.get("weight", 0) for p in positions)
        avg_beta = sum(p.get("beta", 1.0) * p.get("weight", 0) for p in positions) / total_weight if total_weight > 0 else 1.0

        # Simple estimation: market decline needed
        market_decline_needed = target_loss / avg_beta if avg_beta != 0 else target_loss

        # Calculate sector exposures
        sector_exposures: dict[str, float] = {}
        for pos in positions:
            sector = pos.get("sector", "Unknown")
            weight = pos.get("weight", 0)
            sector_exposures[sector] = sector_exposures.get(sector, 0) + weight

        # Find largest sector
        largest_sector = max(sector_exposures.items(), key=lambda x: x[1]) if sector_exposures else ("Unknown", 0)

        return {
            "target_loss": target_loss,
            "market_decline_needed": market_decline_needed,
            "portfolio_beta": avg_beta,
            "largest_sector_exposure": largest_sector[0],
            "largest_sector_weight": largest_sector[1],
            "analysis": f"A {abs(market_decline_needed):.1%} market decline would cause approximately "
                       f"a {abs(target_loss):.1%} portfolio loss given current beta of {avg_beta:.2f}. "
                       f"The portfolio is most exposed to {largest_sector[0]} ({largest_sector[1]:.1%}).",
        }
