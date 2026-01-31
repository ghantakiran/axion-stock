"""Tax Optimization Configuration.

Tax rates, filing statuses, lot selection methods, and configuration dataclasses.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class FilingStatus(str, Enum):
    """IRS filing status."""
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_SEPARATE = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"


class HoldingPeriod(str, Enum):
    """Tax holding period classification."""
    SHORT_TERM = "short_term"  # <= 1 year
    LONG_TERM = "long_term"    # > 1 year


class LotSelectionMethod(str, Enum):
    """Tax lot selection methods for sales."""
    FIFO = "fifo"           # First In, First Out
    LIFO = "lifo"           # Last In, First Out
    SPEC_ID = "spec_id"     # Specific Identification
    MIN_TAX = "min_tax"     # Minimize Tax Impact
    MAX_LOSS = "max_loss"   # Maximize Loss (for harvesting)
    HIGH_COST = "high_cost" # Highest Cost First


class AcquisitionType(str, Enum):
    """How shares were acquired."""
    BUY = "buy"
    DIVIDEND_REINVEST = "dividend_reinvest"
    TRANSFER = "transfer"
    GIFT = "gift"
    INHERITANCE = "inheritance"
    STOCK_SPLIT = "stock_split"
    MERGER = "merger"


class AccountType(str, Enum):
    """Account tax status."""
    TAXABLE = "taxable"
    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    SEP_IRA = "sep_ira"
    SIMPLE_IRA = "simple_ira"
    K401 = "401k"
    K403B = "403b"
    HSA = "hsa"


class BasisReportingCategory(str, Enum):
    """Form 8949 basis reporting categories."""
    A = "A"  # Short-term, basis reported to IRS
    B = "B"  # Short-term, basis NOT reported to IRS
    C = "C"  # Short-term, Form 1099-B not received
    D = "D"  # Long-term, basis reported to IRS
    E = "E"  # Long-term, basis NOT reported to IRS
    F = "F"  # Long-term, Form 1099-B not received


class AdjustmentCode(str, Enum):
    """Form 8949 adjustment codes."""
    W = "W"  # Wash sale loss disallowed
    B = "B"  # Basis reported to IRS is incorrect
    T = "T"  # Short-term/long-term determination different from 1099-B
    O = "O"  # Other adjustments


# =============================================================================
# Tax Rate Tables (2024)
# =============================================================================

# Federal ordinary income tax brackets (2024)
FEDERAL_BRACKETS_2024: dict[FilingStatus, list[tuple[float, float]]] = {
    FilingStatus.SINGLE: [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (609_350, 0.35),
        (float('inf'), 0.37),
    ],
    FilingStatus.MARRIED_JOINT: [
        (23_200, 0.10),
        (94_300, 0.12),
        (201_050, 0.22),
        (383_900, 0.24),
        (487_450, 0.32),
        (731_200, 0.35),
        (float('inf'), 0.37),
    ],
    FilingStatus.MARRIED_SEPARATE: [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (365_600, 0.35),
        (float('inf'), 0.37),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (16_550, 0.10),
        (63_100, 0.12),
        (100_500, 0.22),
        (191_950, 0.24),
        (243_700, 0.32),
        (609_350, 0.35),
        (float('inf'), 0.37),
    ],
}

# Long-term capital gains brackets (2024)
LTCG_BRACKETS_2024: dict[FilingStatus, list[tuple[float, float]]] = {
    FilingStatus.SINGLE: [
        (47_025, 0.00),
        (518_900, 0.15),
        (float('inf'), 0.20),
    ],
    FilingStatus.MARRIED_JOINT: [
        (94_050, 0.00),
        (583_750, 0.15),
        (float('inf'), 0.20),
    ],
    FilingStatus.MARRIED_SEPARATE: [
        (47_025, 0.00),
        (291_850, 0.15),
        (float('inf'), 0.20),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (63_000, 0.00),
        (551_350, 0.15),
        (float('inf'), 0.20),
    ],
}

# Net Investment Income Tax thresholds
NIIT_THRESHOLDS: dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 200_000,
    FilingStatus.MARRIED_JOINT: 250_000,
    FilingStatus.MARRIED_SEPARATE: 125_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 200_000,
}
NIIT_RATE = 0.038  # 3.8%

# State income tax rates (simplified - top marginal rates)
STATE_TAX_RATES: dict[str, float] = {
    "AL": 0.05, "AK": 0.00, "AZ": 0.025, "AR": 0.047, "CA": 0.133,
    "CO": 0.044, "CT": 0.0699, "DE": 0.066, "FL": 0.00, "GA": 0.055,
    "HI": 0.11, "ID": 0.058, "IL": 0.0495, "IN": 0.0315, "IA": 0.057,
    "KS": 0.057, "KY": 0.04, "LA": 0.0425, "ME": 0.0715, "MD": 0.0575,
    "MA": 0.09, "MI": 0.0425, "MN": 0.0985, "MS": 0.05, "MO": 0.048,
    "MT": 0.059, "NE": 0.0584, "NV": 0.00, "NH": 0.00, "NJ": 0.1075,
    "NM": 0.059, "NY": 0.109, "NC": 0.0475, "ND": 0.0225, "OH": 0.035,
    "OK": 0.0475, "OR": 0.099, "PA": 0.0307, "RI": 0.0599, "SC": 0.064,
    "SD": 0.00, "TN": 0.00, "TX": 0.00, "UT": 0.0465, "VT": 0.0875,
    "VA": 0.0575, "WA": 0.00, "WV": 0.055, "WI": 0.0765, "WY": 0.00,
    "DC": 0.1075,
}

# States with no income tax
NO_INCOME_TAX_STATES = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}

# States with different capital gains treatment
STATE_LTCG_EXCLUSIONS: dict[str, float] = {
    "SC": 0.44,  # 44% exclusion for LTCG
    "WI": 0.30,  # 30% exclusion
    "MT": 0.02,  # 2% rate for capital gains
}


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class TaxProfile:
    """User's tax profile for calculations."""
    filing_status: FilingStatus = FilingStatus.SINGLE
    state: str = "CA"
    estimated_ordinary_income: float = 100_000
    include_niit: bool = True
    
    @property
    def state_rate(self) -> float:
        """Get state tax rate."""
        return STATE_TAX_RATES.get(self.state, 0.0)
    
    @property
    def has_state_tax(self) -> bool:
        """Check if state has income tax."""
        return self.state not in NO_INCOME_TAX_STATES


@dataclass
class HarvestingConfig:
    """Tax-loss harvesting configuration."""
    min_loss_threshold: float = 100.0
    wash_sale_window_days: int = 30
    min_holding_days: int = 0
    max_daily_harvests: int = 10
    annual_harvest_limit: float = 0.0  # 0 = unlimited
    correlation_threshold: float = 0.85
    prefer_etf_substitutes: bool = True
    auto_repurchase: bool = False
    repurchase_delay_days: int = 31


@dataclass
class WashSaleConfig:
    """Wash sale detection configuration."""
    lookback_days: int = 30
    lookforward_days: int = 30
    include_options: bool = True
    include_related_etfs: bool = False
    etf_similarity_threshold: float = 0.90


@dataclass
class LotSelectionConfig:
    """Tax lot selection configuration."""
    default_method: LotSelectionMethod = LotSelectionMethod.FIFO
    optimize_for_account_type: bool = True
    consider_holding_period: bool = True
    min_lot_value: float = 0.01


@dataclass
class TaxConfig:
    """Main tax optimization configuration."""
    tax_profile: TaxProfile = field(default_factory=TaxProfile)
    harvesting: HarvestingConfig = field(default_factory=HarvestingConfig)
    wash_sale: WashSaleConfig = field(default_factory=WashSaleConfig)
    lot_selection: LotSelectionConfig = field(default_factory=LotSelectionConfig)
    tax_year: int = 2024
    use_federal_rates: bool = True
    track_wash_sales: bool = True


# Default configuration
DEFAULT_TAX_CONFIG = TaxConfig()
