"""ESG Data Models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from src.esg.config import ESGCategory, ESGRating, ESGPillar, ImpactCategory, RATING_THRESHOLDS


def _generate_id() -> str:
    return str(uuid4())


@dataclass
class PillarScore:
    """Score for an individual ESG pillar."""
    pillar: ESGPillar
    score: float  # 0-100
    weight: float = 1.0
    data_quality: str = "estimated"  # estimated, reported, audited
    notes: str = ""

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight

    def to_dict(self) -> dict:
        return {
            "pillar": self.pillar.value,
            "score": self.score,
            "weight": self.weight,
            "data_quality": self.data_quality,
        }


@dataclass
class ESGScore:
    """Composite ESG score for a security."""
    id: str = field(default_factory=_generate_id)
    symbol: str = ""
    environmental_score: float = 50.0
    social_score: float = 50.0
    governance_score: float = 50.0
    composite_score: float = 50.0
    rating: ESGRating = ESGRating.BBB
    pillar_scores: list[PillarScore] = field(default_factory=list)
    controversies: list[str] = field(default_factory=list)
    controversy_score: float = 0.0
    sector: str = ""
    sector_rank: Optional[int] = None
    sector_percentile: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def category_scores(self) -> dict[str, float]:
        return {
            ESGCategory.ENVIRONMENTAL.value: self.environmental_score,
            ESGCategory.SOCIAL.value: self.social_score,
            ESGCategory.GOVERNANCE.value: self.governance_score,
            ESGCategory.COMPOSITE.value: self.composite_score,
        }

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "environmental_score": self.environmental_score,
            "social_score": self.social_score,
            "governance_score": self.governance_score,
            "composite_score": self.composite_score,
            "rating": self.rating.value,
            "controversies": self.controversies,
            "controversy_score": self.controversy_score,
            "sector": self.sector,
            "sector_rank": self.sector_rank,
            "pillar_scores": [p.to_dict() for p in self.pillar_scores],
        }


@dataclass
class CarbonMetrics:
    """Carbon footprint metrics for a security."""
    symbol: str = ""
    carbon_intensity: float = 0.0  # tCO2e per $M revenue
    scope1_emissions: float = 0.0  # Direct emissions
    scope2_emissions: float = 0.0  # Indirect (energy)
    scope3_emissions: float = 0.0  # Value chain
    total_emissions: float = 0.0
    yoy_change_pct: float = 0.0
    net_zero_target_year: Optional[int] = None
    renewable_energy_pct: float = 0.0

    @property
    def total_scope12(self) -> float:
        return self.scope1_emissions + self.scope2_emissions

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "carbon_intensity": self.carbon_intensity,
            "scope1": self.scope1_emissions,
            "scope2": self.scope2_emissions,
            "scope3": self.scope3_emissions,
            "total": self.total_emissions,
            "yoy_change_pct": self.yoy_change_pct,
            "renewable_energy_pct": self.renewable_energy_pct,
        }


@dataclass
class ESGScreenResult:
    """Result of ESG screening for a security."""
    symbol: str
    passed: bool
    excluded_reasons: list[str] = field(default_factory=list)
    score: Optional[float] = None
    rating: Optional[ESGRating] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "passed": self.passed,
            "excluded_reasons": self.excluded_reasons,
            "score": self.score,
            "rating": self.rating.value if self.rating else None,
        }


@dataclass
class ImpactMetric:
    """Individual impact measurement."""
    category: ImpactCategory
    value: float
    unit: str
    benchmark: Optional[float] = None
    percentile: Optional[float] = None
    trend: str = "stable"  # improving, stable, declining

    @property
    def vs_benchmark(self) -> Optional[float]:
        if self.benchmark and self.benchmark != 0:
            return (self.value - self.benchmark) / abs(self.benchmark)
        return None

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "value": self.value,
            "unit": self.unit,
            "benchmark": self.benchmark,
            "percentile": self.percentile,
            "trend": self.trend,
        }


@dataclass
class ESGPortfolioSummary:
    """Portfolio-level ESG summary."""
    weighted_esg_score: float = 50.0
    weighted_e_score: float = 50.0
    weighted_s_score: float = 50.0
    weighted_g_score: float = 50.0
    portfolio_carbon_intensity: float = 0.0
    portfolio_rating: ESGRating = ESGRating.BBB
    n_holdings: int = 0
    n_screened_out: int = 0
    coverage_pct: float = 0.0
    best_in_class: list[str] = field(default_factory=list)
    worst_in_class: list[str] = field(default_factory=list)
    controversies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "weighted_esg_score": self.weighted_esg_score,
            "weighted_e_score": self.weighted_e_score,
            "weighted_s_score": self.weighted_s_score,
            "weighted_g_score": self.weighted_g_score,
            "portfolio_carbon_intensity": self.portfolio_carbon_intensity,
            "portfolio_rating": self.portfolio_rating.value,
            "n_holdings": self.n_holdings,
            "n_screened_out": self.n_screened_out,
            "coverage_pct": self.coverage_pct,
            "best_in_class": self.best_in_class,
            "worst_in_class": self.worst_in_class,
        }
