"""Scenario Builder.

Constructs custom stress scenarios with macro shocks,
sector rotations, and correlation regime changes.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import date

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class MacroShock:
    """A macroeconomic shock component."""
    variable: str = ""  # e.g., rates, inflation, growth, dollar
    magnitude: float = 0.0  # e.g., 0.02 for +2% rates
    direction: str = "up"  # up, down
    description: str = ""

    @property
    def signed_magnitude(self) -> float:
        return self.magnitude if self.direction == "up" else -self.magnitude


@dataclass
class SectorRotation:
    """Sector-specific shock in a scenario."""
    sector: str = ""
    impact_pct: float = 0.0
    rationale: str = ""

    @property
    def is_positive(self) -> bool:
        return self.impact_pct > 0


@dataclass
class CorrelationShift:
    """Change in correlation regime."""
    from_correlation: float = 0.0
    to_correlation: float = 0.0
    affected_pairs: list[tuple[str, str]] = field(default_factory=list)
    description: str = ""

    @property
    def is_contagion(self) -> bool:
        """Correlations increasing (contagion)."""
        return self.to_correlation > self.from_correlation


@dataclass
class CustomScenario:
    """A fully specified custom stress scenario."""
    name: str = ""
    description: str = ""
    scenario_type: str = "custom"  # custom, historical, hypothetical
    macro_shocks: list[MacroShock] = field(default_factory=list)
    sector_rotations: list[SectorRotation] = field(default_factory=list)
    factor_shocks: dict[str, float] = field(default_factory=dict)
    correlation_shift: Optional[CorrelationShift] = None
    market_shock: float = 0.0
    volatility_multiplier: float = 1.0
    created_date: Optional[date] = None

    @property
    def n_components(self) -> int:
        return (
            len(self.macro_shocks)
            + len(self.sector_rotations)
            + len(self.factor_shocks)
            + (1 if self.correlation_shift else 0)
        )

    @property
    def severity_score(self) -> float:
        """0-100 score based on shock magnitudes."""
        score = 0.0
        score += abs(self.market_shock) * 100
        score += sum(abs(r.impact_pct) for r in self.sector_rotations) * 50
        score += sum(abs(s) for s in self.factor_shocks.values()) * 50
        score += (self.volatility_multiplier - 1.0) * 20
        return min(100, round(score, 2))

    @property
    def is_severe(self) -> bool:
        return self.severity_score > 50


@dataclass
class ScenarioTemplate:
    """Pre-built scenario template."""
    name: str = ""
    category: str = ""  # recession, inflation, geopolitical, sector, etc.
    base_market_shock: float = 0.0
    macro_variables: list[str] = field(default_factory=list)
    affected_sectors: list[str] = field(default_factory=list)
    typical_duration_days: int = 30
    historical_examples: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pre-built templates
# ---------------------------------------------------------------------------
SCENARIO_TEMPLATES = {
    "recession": ScenarioTemplate(
        name="Recession",
        category="macro",
        base_market_shock=-0.25,
        macro_variables=["growth", "employment", "credit"],
        affected_sectors=["Consumer Discretionary", "Financials", "Industrials"],
        typical_duration_days=180,
        historical_examples=["GFC 2008", "COVID 2020"],
    ),
    "rate_shock": ScenarioTemplate(
        name="Rate Shock",
        category="monetary",
        base_market_shock=-0.12,
        macro_variables=["interest_rates", "inflation"],
        affected_sectors=["Real Estate", "Utilities", "Technology"],
        typical_duration_days=60,
        historical_examples=["2022 Tightening", "2018 Rate Hikes"],
    ),
    "inflation_spike": ScenarioTemplate(
        name="Inflation Spike",
        category="macro",
        base_market_shock=-0.10,
        macro_variables=["inflation", "interest_rates", "wages"],
        affected_sectors=["Consumer Discretionary", "Technology"],
        typical_duration_days=90,
        historical_examples=["2022 CPI Spike"],
    ),
    "tech_correction": ScenarioTemplate(
        name="Tech Correction",
        category="sector",
        base_market_shock=-0.15,
        macro_variables=["growth", "valuations"],
        affected_sectors=["Technology", "Communication Services"],
        typical_duration_days=45,
        historical_examples=["2022 Tech Selloff", "Dot-Com Bust"],
    ),
    "geopolitical": ScenarioTemplate(
        name="Geopolitical Crisis",
        category="event",
        base_market_shock=-0.08,
        macro_variables=["oil", "dollar", "volatility"],
        affected_sectors=["Energy", "Defense", "Travel"],
        typical_duration_days=30,
        historical_examples=["Russia-Ukraine", "Trade War"],
    ),
    "credit_crisis": ScenarioTemplate(
        name="Credit Crisis",
        category="financial",
        base_market_shock=-0.20,
        macro_variables=["credit_spreads", "liquidity", "defaults"],
        affected_sectors=["Financials", "Real Estate", "High Yield"],
        typical_duration_days=120,
        historical_examples=["GFC 2008", "2020 March"],
    ),
    "stagflation": ScenarioTemplate(
        name="Stagflation",
        category="macro",
        base_market_shock=-0.18,
        macro_variables=["inflation", "growth", "unemployment"],
        affected_sectors=["Consumer Discretionary", "Financials"],
        typical_duration_days=180,
        historical_examples=["1970s Stagflation"],
    ),
}


# ---------------------------------------------------------------------------
# Sector shock mappings by macro variable
# ---------------------------------------------------------------------------
MACRO_TO_SECTOR_MAP = {
    "interest_rates_up": {
        "Real Estate": -0.20,
        "Utilities": -0.15,
        "Technology": -0.12,
        "Financials": 0.05,
        "Consumer Discretionary": -0.08,
    },
    "interest_rates_down": {
        "Real Estate": 0.15,
        "Utilities": 0.12,
        "Technology": 0.10,
        "Financials": -0.05,
    },
    "inflation_up": {
        "Technology": -0.15,
        "Consumer Discretionary": -0.12,
        "Energy": 0.10,
        "Materials": 0.08,
        "Consumer Staples": -0.05,
    },
    "growth_down": {
        "Consumer Discretionary": -0.18,
        "Industrials": -0.15,
        "Technology": -0.12,
        "Financials": -0.10,
        "Consumer Staples": 0.03,
        "Utilities": 0.05,
        "Healthcare": 0.02,
    },
    "dollar_up": {
        "Technology": -0.10,
        "Materials": -0.12,
        "Consumer Staples": -0.08,
        "Industrials": -0.05,
    },
    "oil_up": {
        "Energy": 0.25,
        "Industrials": -0.08,
        "Consumer Discretionary": -0.10,
        "Transportation": -0.15,
    },
}


# ---------------------------------------------------------------------------
# Scenario Builder
# ---------------------------------------------------------------------------
class ScenarioBuilder:
    """Builds custom stress test scenarios.

    Combines macro shocks, sector impacts, factor exposures,
    and correlation changes into coherent stress scenarios.
    """

    def __init__(self) -> None:
        self.templates = dict(SCENARIO_TEMPLATES)
        self.macro_sector_map = dict(MACRO_TO_SECTOR_MAP)

    def from_template(
        self,
        template_name: str,
        severity_multiplier: float = 1.0,
        custom_name: Optional[str] = None,
    ) -> CustomScenario:
        """Build scenario from pre-defined template.

        Args:
            template_name: Name of template (recession, rate_shock, etc.).
            severity_multiplier: Scale shocks by this factor.
            custom_name: Optional custom name.

        Returns:
            CustomScenario based on template.
        """
        if template_name not in self.templates:
            return CustomScenario(
                name=template_name,
                description="Unknown template",
            )

        template = self.templates[template_name]

        # Build macro shocks
        macro_shocks = []
        for var in template.macro_variables:
            shock_mag = 0.02 * severity_multiplier  # Default 2%
            macro_shocks.append(MacroShock(
                variable=var,
                magnitude=shock_mag,
                direction="down" if "down" in var or template.base_market_shock < 0 else "up",
                description=f"{var} shock from {template_name}",
            ))

        # Build sector rotations
        sector_rotations = []
        for sector in template.affected_sectors:
            # Derive impact from template
            impact = template.base_market_shock * 1.2 * severity_multiplier
            sector_rotations.append(SectorRotation(
                sector=sector,
                impact_pct=round(impact, 4),
                rationale=f"Affected by {template_name}",
            ))

        return CustomScenario(
            name=custom_name or template.name,
            description=f"Based on {template.name} template",
            scenario_type="template",
            macro_shocks=macro_shocks,
            sector_rotations=sector_rotations,
            market_shock=round(template.base_market_shock * severity_multiplier, 4),
            volatility_multiplier=1.0 + abs(template.base_market_shock) * severity_multiplier,
            created_date=date.today(),
        )

    def from_macro_shocks(
        self,
        macro_shocks: list[MacroShock],
        name: str = "Custom Macro Scenario",
    ) -> CustomScenario:
        """Build scenario from macro shock specifications.

        Args:
            macro_shocks: List of macro shocks.
            name: Scenario name.

        Returns:
            CustomScenario with derived sector impacts.
        """
        # Derive sector impacts from macro shocks
        sector_impacts: dict[str, float] = {}

        for shock in macro_shocks:
            key = f"{shock.variable}_{shock.direction}"
            if key in self.macro_sector_map:
                for sector, impact in self.macro_sector_map[key].items():
                    scaled_impact = impact * (shock.magnitude / 0.02)  # Normalize to 2%
                    if sector in sector_impacts:
                        sector_impacts[sector] += scaled_impact
                    else:
                        sector_impacts[sector] = scaled_impact

        sector_rotations = [
            SectorRotation(
                sector=sector,
                impact_pct=round(impact, 4),
                rationale=f"Derived from macro shocks",
            )
            for sector, impact in sector_impacts.items()
        ]

        # Estimate market shock from sector impacts
        avg_impact = float(np.mean(list(sector_impacts.values()))) if sector_impacts else 0.0

        return CustomScenario(
            name=name,
            description=f"Built from {len(macro_shocks)} macro shocks",
            scenario_type="custom",
            macro_shocks=macro_shocks,
            sector_rotations=sector_rotations,
            market_shock=round(avg_impact, 4),
            created_date=date.today(),
        )

    def combine_scenarios(
        self,
        scenarios: list[CustomScenario],
        weights: Optional[list[float]] = None,
        name: str = "Combined Scenario",
    ) -> CustomScenario:
        """Combine multiple scenarios into one.

        Args:
            scenarios: List of scenarios to combine.
            weights: Optional weights (default: equal).
            name: Name for combined scenario.

        Returns:
            Combined CustomScenario.
        """
        if not scenarios:
            return CustomScenario(name=name)

        if weights is None:
            weights = [1.0 / len(scenarios)] * len(scenarios)

        # Aggregate macro shocks
        all_macro: dict[str, MacroShock] = {}
        for scn, w in zip(scenarios, weights):
            for shock in scn.macro_shocks:
                if shock.variable in all_macro:
                    existing = all_macro[shock.variable]
                    existing.magnitude += shock.magnitude * w
                else:
                    all_macro[shock.variable] = MacroShock(
                        variable=shock.variable,
                        magnitude=shock.magnitude * w,
                        direction=shock.direction,
                    )

        # Aggregate sector rotations
        sector_impacts: dict[str, float] = {}
        for scn, w in zip(scenarios, weights):
            for rot in scn.sector_rotations:
                if rot.sector in sector_impacts:
                    sector_impacts[rot.sector] += rot.impact_pct * w
                else:
                    sector_impacts[rot.sector] = rot.impact_pct * w

        sector_rotations = [
            SectorRotation(sector=s, impact_pct=round(i, 4))
            for s, i in sector_impacts.items()
        ]

        # Aggregate factor shocks
        factor_shocks: dict[str, float] = {}
        for scn, w in zip(scenarios, weights):
            for factor, shock in scn.factor_shocks.items():
                if factor in factor_shocks:
                    factor_shocks[factor] += shock * w
                else:
                    factor_shocks[factor] = shock * w

        # Weighted market shock
        market_shock = sum(s.market_shock * w for s, w in zip(scenarios, weights))

        # Max volatility multiplier
        vol_mult = max(s.volatility_multiplier for s in scenarios)

        return CustomScenario(
            name=name,
            description=f"Combined from {len(scenarios)} scenarios",
            scenario_type="combined",
            macro_shocks=list(all_macro.values()),
            sector_rotations=sector_rotations,
            factor_shocks={k: round(v, 4) for k, v in factor_shocks.items()},
            market_shock=round(market_shock, 4),
            volatility_multiplier=vol_mult,
            created_date=date.today(),
        )

    def add_correlation_shift(
        self,
        scenario: CustomScenario,
        from_corr: float,
        to_corr: float,
        description: str = "Correlation regime shift",
    ) -> CustomScenario:
        """Add correlation shift to scenario.

        Args:
            scenario: Base scenario.
            from_corr: Starting correlation.
            to_corr: Ending correlation.
            description: Description of shift.

        Returns:
            Scenario with correlation shift added.
        """
        scenario.correlation_shift = CorrelationShift(
            from_correlation=from_corr,
            to_correlation=to_corr,
            description=description,
        )
        return scenario

    def list_templates(self) -> list[dict]:
        """List available scenario templates.

        Returns:
            List of template summaries.
        """
        return [
            {
                "name": t.name,
                "category": t.category,
                "base_shock": t.base_market_shock,
                "duration_days": t.typical_duration_days,
                "examples": t.historical_examples,
            }
            for t in self.templates.values()
        ]

    def validate_scenario(
        self,
        scenario: CustomScenario,
    ) -> dict:
        """Validate scenario for consistency.

        Args:
            scenario: Scenario to validate.

        Returns:
            Dict with validation results.
        """
        issues = []

        # Check for contradictory shocks
        sector_signs = {r.sector: r.impact_pct > 0 for r in scenario.sector_rotations}
        if scenario.market_shock < -0.15:
            # Severe market decline
            positive_sectors = [s for s, pos in sector_signs.items() if pos]
            if len(positive_sectors) > len(sector_signs) / 2:
                issues.append(f"Many sectors positive despite severe market decline: {positive_sectors}")

        # Check volatility consistency
        if abs(scenario.market_shock) > 0.10 and scenario.volatility_multiplier < 1.2:
            issues.append("Large market shock but low volatility multiplier")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "severity_score": scenario.severity_score,
            "n_components": scenario.n_components,
        }
