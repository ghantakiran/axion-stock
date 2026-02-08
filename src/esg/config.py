"""ESG Configuration and Enums."""

from dataclasses import dataclass, field
from enum import Enum


class ESGCategory(Enum):
    """Top-level ESG category."""
    ENVIRONMENTAL = "environmental"
    SOCIAL = "social"
    GOVERNANCE = "governance"
    COMPOSITE = "composite"


class ESGPillar(Enum):
    """ESG scoring pillars."""
    CARBON_EMISSIONS = "carbon_emissions"
    ENERGY_EFFICIENCY = "energy_efficiency"
    WASTE_MANAGEMENT = "waste_management"
    WATER_USAGE = "water_usage"
    BIODIVERSITY = "biodiversity"
    LABOR_PRACTICES = "labor_practices"
    DIVERSITY_INCLUSION = "diversity_inclusion"
    COMMUNITY_IMPACT = "community_impact"
    DATA_PRIVACY = "data_privacy"
    HUMAN_RIGHTS = "human_rights"
    BOARD_COMPOSITION = "board_composition"
    EXECUTIVE_COMPENSATION = "executive_compensation"
    SHAREHOLDER_RIGHTS = "shareholder_rights"
    BUSINESS_ETHICS = "business_ethics"
    TRANSPARENCY = "transparency"


class ESGRating(Enum):
    """ESG letter ratings."""
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"


class ImpactCategory(Enum):
    """Impact measurement categories."""
    CARBON_FOOTPRINT = "carbon_footprint"
    RENEWABLE_ENERGY = "renewable_energy"
    WATER_INTENSITY = "water_intensity"
    WASTE_RECYCLED = "waste_recycled"
    EMPLOYEE_SATISFACTION = "employee_satisfaction"
    GENDER_PAY_GAP = "gender_pay_gap"
    BOARD_INDEPENDENCE = "board_independence"
    TAX_TRANSPARENCY = "tax_transparency"


# Score thresholds for ratings
RATING_THRESHOLDS = {
    ESGRating.AAA: 85,
    ESGRating.AA: 75,
    ESGRating.A: 65,
    ESGRating.BBB: 55,
    ESGRating.BB: 45,
    ESGRating.B: 35,
    ESGRating.CCC: 0,
}

# Pillar-to-category mapping
PILLAR_CATEGORIES = {
    ESGPillar.CARBON_EMISSIONS: ESGCategory.ENVIRONMENTAL,
    ESGPillar.ENERGY_EFFICIENCY: ESGCategory.ENVIRONMENTAL,
    ESGPillar.WASTE_MANAGEMENT: ESGCategory.ENVIRONMENTAL,
    ESGPillar.WATER_USAGE: ESGCategory.ENVIRONMENTAL,
    ESGPillar.BIODIVERSITY: ESGCategory.ENVIRONMENTAL,
    ESGPillar.LABOR_PRACTICES: ESGCategory.SOCIAL,
    ESGPillar.DIVERSITY_INCLUSION: ESGCategory.SOCIAL,
    ESGPillar.COMMUNITY_IMPACT: ESGCategory.SOCIAL,
    ESGPillar.DATA_PRIVACY: ESGCategory.SOCIAL,
    ESGPillar.HUMAN_RIGHTS: ESGCategory.SOCIAL,
    ESGPillar.BOARD_COMPOSITION: ESGCategory.GOVERNANCE,
    ESGPillar.EXECUTIVE_COMPENSATION: ESGCategory.GOVERNANCE,
    ESGPillar.SHAREHOLDER_RIGHTS: ESGCategory.GOVERNANCE,
    ESGPillar.BUSINESS_ETHICS: ESGCategory.GOVERNANCE,
    ESGPillar.TRANSPARENCY: ESGCategory.GOVERNANCE,
}


@dataclass
class ESGConfig:
    """ESG scoring configuration."""
    environmental_weight: float = 0.35
    social_weight: float = 0.30
    governance_weight: float = 0.35
    min_score: float = 0.0
    max_score: float = 100.0
    exclude_sin_stocks: bool = False
    exclude_fossil_fuels: bool = False
    exclude_weapons: bool = False
    carbon_intensity_threshold: float = 500.0  # tCO2e/$M revenue
    controversy_penalty: float = 10.0


DEFAULT_ESG_CONFIG = ESGConfig()
