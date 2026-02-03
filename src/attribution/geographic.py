"""Geographic Attribution.

Country and region-level performance attribution decomposing
active return into geographic allocation and selection effects.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.attribution.config import AttributionConfig, DEFAULT_ATTRIBUTION_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class CountryAttribution:
    """Attribution for a single country."""
    country: str = ""
    region: str = ""
    portfolio_weight: float = 0.0
    benchmark_weight: float = 0.0
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0
    currency_effect: float = 0.0

    @property
    def total_effect(self) -> float:
        return (self.allocation_effect + self.selection_effect
                + self.interaction_effect + self.currency_effect)

    @property
    def active_weight(self) -> float:
        return self.portfolio_weight - self.benchmark_weight

    @property
    def active_return(self) -> float:
        return self.portfolio_return - self.benchmark_return


@dataclass
class RegionAttribution:
    """Attribution aggregated to region level."""
    region: str = ""
    portfolio_weight: float = 0.0
    benchmark_weight: float = 0.0
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0
    currency_effect: float = 0.0
    countries: list[CountryAttribution] = field(default_factory=list)

    @property
    def total_effect(self) -> float:
        return (self.allocation_effect + self.selection_effect
                + self.interaction_effect + self.currency_effect)

    @property
    def n_countries(self) -> int:
        return len(self.countries)


@dataclass
class GeographicAttribution:
    """Complete geographic attribution result."""
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0
    total_allocation: float = 0.0
    total_selection: float = 0.0
    total_interaction: float = 0.0
    total_currency: float = 0.0
    countries: list[CountryAttribution] = field(default_factory=list)
    regions: list[RegionAttribution] = field(default_factory=list)

    @property
    def n_countries(self) -> int:
        return len(self.countries)

    @property
    def n_regions(self) -> int:
        return len(self.regions)

    @property
    def attribution_sum(self) -> float:
        return (self.total_allocation + self.total_selection
                + self.total_interaction + self.total_currency)


# ---------------------------------------------------------------------------
# Geographic Analyzer
# ---------------------------------------------------------------------------
class GeographicAnalyzer:
    """Country and region-level performance attribution."""

    # Default region mapping
    DEFAULT_REGIONS = {
        "US": "North America", "CA": "North America",
        "GB": "Europe", "DE": "Europe", "FR": "Europe",
        "CH": "Europe", "NL": "Europe", "SE": "Europe",
        "IT": "Europe", "ES": "Europe", "NO": "Europe",
        "JP": "Asia Pacific", "CN": "Asia Pacific",
        "HK": "Asia Pacific", "KR": "Asia Pacific",
        "AU": "Asia Pacific", "IN": "Asia Pacific",
        "SG": "Asia Pacific", "TW": "Asia Pacific",
        "BR": "Latin America", "MX": "Latin America",
        "ZA": "Emerging Markets", "RU": "Emerging Markets",
    }

    def __init__(
        self,
        config: Optional[AttributionConfig] = None,
        region_map: Optional[dict[str, str]] = None,
    ) -> None:
        self.config = config or DEFAULT_ATTRIBUTION_CONFIG
        self.region_map = region_map or self.DEFAULT_REGIONS

    def analyze(
        self,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_returns: dict[str, float],
        currency_effects: Optional[dict[str, float]] = None,
    ) -> GeographicAttribution:
        """Perform country-level geographic attribution.

        Uses Brinson-Fachler framework at the country level.

        Args:
            portfolio_weights: {country: weight} in portfolio.
            benchmark_weights: {country: weight} in benchmark.
            portfolio_returns: {country: return} in portfolio.
            benchmark_returns: {country: return} in benchmark.
            currency_effects: {country: currency_return} (optional).

        Returns:
            GeographicAttribution with country and region decomposition.
        """
        all_countries = sorted(
            set(portfolio_weights.keys()) | set(benchmark_weights.keys())
        )

        if not all_countries:
            return GeographicAttribution()

        # Total benchmark return
        total_bm = sum(
            benchmark_weights.get(c, 0) * benchmark_returns.get(c, 0)
            for c in all_countries
        )
        total_port = sum(
            portfolio_weights.get(c, 0) * portfolio_returns.get(c, 0)
            for c in all_countries
        )

        countries = []
        for country in all_countries:
            wp = portfolio_weights.get(country, 0.0)
            wb = benchmark_weights.get(country, 0.0)
            rp = portfolio_returns.get(country, 0.0)
            rb = benchmark_returns.get(country, 0.0)

            # Brinson-Fachler effects
            alloc = (wp - wb) * (rb - total_bm)
            sel = wb * (rp - rb)
            inter = (wp - wb) * (rp - rb)

            # Currency effect
            curr = 0.0
            if currency_effects:
                curr = wp * currency_effects.get(country, 0.0)

            countries.append(CountryAttribution(
                country=country,
                region=self.region_map.get(country, "Other"),
                portfolio_weight=round(wp, 4),
                benchmark_weight=round(wb, 4),
                portfolio_return=round(rp, 6),
                benchmark_return=round(rb, 6),
                allocation_effect=round(alloc, 6),
                selection_effect=round(sel, 6),
                interaction_effect=round(inter, 6),
                currency_effect=round(curr, 6),
            ))

        # Aggregate to regions
        regions = self._aggregate_regions(countries)

        # Totals
        total_alloc = sum(c.allocation_effect for c in countries)
        total_sel = sum(c.selection_effect for c in countries)
        total_inter = sum(c.interaction_effect for c in countries)
        total_curr = sum(c.currency_effect for c in countries)

        return GeographicAttribution(
            portfolio_return=round(total_port, 6),
            benchmark_return=round(total_bm, 6),
            active_return=round(total_port - total_bm, 6),
            total_allocation=round(total_alloc, 6),
            total_selection=round(total_sel, 6),
            total_interaction=round(total_inter, 6),
            total_currency=round(total_curr, 6),
            countries=countries,
            regions=regions,
        )

    def top_contributors(
        self,
        result: GeographicAttribution,
        n: int = 5,
        by: str = "total",
    ) -> list[CountryAttribution]:
        """Get top contributing countries.

        Args:
            result: GeographicAttribution result.
            n: Number of top countries.
            by: Sort by 'total', 'allocation', or 'selection'.

        Returns:
            Top N countries sorted by effect.
        """
        if by == "allocation":
            key = lambda c: c.allocation_effect
        elif by == "selection":
            key = lambda c: c.selection_effect
        else:
            key = lambda c: c.total_effect

        return sorted(result.countries, key=key, reverse=True)[:n]

    def bottom_contributors(
        self,
        result: GeographicAttribution,
        n: int = 5,
    ) -> list[CountryAttribution]:
        """Get bottom contributing countries."""
        return sorted(
            result.countries, key=lambda c: c.total_effect
        )[:n]

    def _aggregate_regions(
        self,
        countries: list[CountryAttribution],
    ) -> list[RegionAttribution]:
        """Aggregate country-level data to regions."""
        region_data: dict[str, list[CountryAttribution]] = {}
        for c in countries:
            region_data.setdefault(c.region, []).append(c)

        regions = []
        for region, ctries in sorted(region_data.items()):
            pw = sum(c.portfolio_weight for c in ctries)
            bw = sum(c.benchmark_weight for c in ctries)

            # Weighted returns
            pr = (
                sum(c.portfolio_weight * c.portfolio_return for c in ctries) / pw
                if pw > 0 else 0.0
            )
            br = (
                sum(c.benchmark_weight * c.benchmark_return for c in ctries) / bw
                if bw > 0 else 0.0
            )

            regions.append(RegionAttribution(
                region=region,
                portfolio_weight=round(pw, 4),
                benchmark_weight=round(bw, 4),
                portfolio_return=round(pr, 6),
                benchmark_return=round(br, 6),
                allocation_effect=round(
                    sum(c.allocation_effect for c in ctries), 6
                ),
                selection_effect=round(
                    sum(c.selection_effect for c in ctries), 6
                ),
                interaction_effect=round(
                    sum(c.interaction_effect for c in ctries), 6
                ),
                currency_effect=round(
                    sum(c.currency_effect for c in ctries), 6
                ),
                countries=ctries,
            ))

        regions.sort(key=lambda r: abs(r.total_effect), reverse=True)
        return regions
