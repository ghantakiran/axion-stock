"""AI Research Reports Configuration.

Enums, constants, and configuration for research report generation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class Rating(str, Enum):
    """Stock rating."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class MoatRating(str, Enum):
    """Economic moat rating."""
    WIDE = "wide"
    NARROW = "narrow"
    NONE = "none"


class MoatTrend(str, Enum):
    """Moat trend direction."""
    STRENGTHENING = "strengthening"
    STABLE = "stable"
    WEAKENING = "weakening"


class RiskLevel(str, Enum):
    """Risk level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class RiskCategory(str, Enum):
    """Risk category."""
    BUSINESS = "business"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    REGULATORY = "regulatory"
    MACRO = "macro"
    ESG = "esg"
    TECHNOLOGY = "technology"
    COMPETITIVE = "competitive"


class ValuationMethod(str, Enum):
    """Valuation methodology."""
    DCF = "dcf"
    COMPARABLE = "comparable"
    DDM = "ddm"
    SOTP = "sotp"
    ASSET_BASED = "asset_based"
    RESIDUAL_INCOME = "residual_income"


class ReportType(str, Enum):
    """Report type."""
    FULL = "full"
    QUICK_TAKE = "quick_take"
    EARNINGS_PREVIEW = "earnings_preview"
    EARNINGS_REVIEW = "earnings_review"
    VALUATION_UPDATE = "valuation_update"
    PEER_COMPARISON = "peer_comparison"


class OutputFormat(str, Enum):
    """Report output format."""
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


class ForceRating(str, Enum):
    """Porter's Five Forces rating."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


# =============================================================================
# Constants
# =============================================================================

# Rating thresholds (based on upside potential)
RATING_THRESHOLDS = {
    Rating.STRONG_BUY: 0.30,   # >30% upside
    Rating.BUY: 0.15,          # 15-30% upside
    Rating.HOLD: -0.10,        # -10% to 15%
    Rating.SELL: -0.25,        # -25% to -10%
    Rating.STRONG_SELL: -1.0,  # <-25%
}

# Default WACC components
DEFAULT_RISK_FREE_RATE = 0.045  # 4.5%
DEFAULT_MARKET_PREMIUM = 0.055  # 5.5%
DEFAULT_BETA = 1.0

# Terminal growth rate bounds
MIN_TERMINAL_GROWTH = 0.01
MAX_TERMINAL_GROWTH = 0.04

# Sector-specific margin benchmarks
SECTOR_MARGINS = {
    "Technology": {"gross": 0.60, "operating": 0.25, "net": 0.20},
    "Healthcare": {"gross": 0.55, "operating": 0.18, "net": 0.12},
    "Financial": {"gross": 0.70, "operating": 0.30, "net": 0.22},
    "Consumer": {"gross": 0.35, "operating": 0.12, "net": 0.08},
    "Industrial": {"gross": 0.30, "operating": 0.12, "net": 0.08},
    "Energy": {"gross": 0.40, "operating": 0.15, "net": 0.10},
    "Utilities": {"gross": 0.45, "operating": 0.20, "net": 0.12},
    "Real Estate": {"gross": 0.60, "operating": 0.35, "net": 0.25},
    "Materials": {"gross": 0.30, "operating": 0.15, "net": 0.10},
    "Communication": {"gross": 0.55, "operating": 0.20, "net": 0.15},
}

# Quality score weights
QUALITY_WEIGHTS = {
    "profitability": 0.25,
    "growth": 0.20,
    "financial_health": 0.20,
    "efficiency": 0.15,
    "valuation": 0.20,
}


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class DCFConfig:
    """DCF valuation configuration."""
    projection_years: int = 5
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    market_premium: float = DEFAULT_MARKET_PREMIUM
    terminal_growth_rate: float = 0.025
    tax_rate: float = 0.21
    use_analyst_estimates: bool = True


@dataclass
class ComparableConfig:
    """Comparable analysis configuration."""
    min_peers: int = 3
    max_peers: int = 8
    same_sector_only: bool = True
    market_cap_range: float = 0.5  # 0.5x to 2x target


@dataclass
class RiskConfig:
    """Risk assessment configuration."""
    include_esg: bool = True
    include_macro: bool = True
    max_risk_factors: int = 10


@dataclass
class ReportConfig:
    """Report generation configuration."""
    report_type: ReportType = ReportType.FULL
    output_format: OutputFormat = OutputFormat.HTML
    include_charts: bool = True
    include_sensitivity: bool = True
    language: str = "en"


@dataclass
class ResearchConfig:
    """Main research configuration."""
    dcf: DCFConfig = field(default_factory=DCFConfig)
    comparable: ComparableConfig = field(default_factory=ComparableConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    report: ReportConfig = field(default_factory=ReportConfig)


DEFAULT_RESEARCH_CONFIG = ResearchConfig()
