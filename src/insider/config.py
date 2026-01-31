"""Insider Trading Tracker Configuration.

Enums, constants, and configuration for insider trading analysis.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class InsiderType(str, Enum):
    """Type of insider."""
    CEO = "ceo"
    CFO = "cfo"
    COO = "coo"
    CTO = "cto"
    PRESIDENT = "president"
    DIRECTOR = "director"
    OFFICER = "officer"
    TEN_PCT_OWNER = "10%_owner"
    BENEFICIAL_OWNER = "beneficial_owner"
    OTHER = "other"


class TransactionType(str, Enum):
    """Type of insider transaction."""
    BUY = "buy"                    # P - Open market purchase
    SELL = "sell"                  # S - Open market sale
    OPTION_EXERCISE = "exercise"   # M - Option exercise
    GRANT = "grant"                # A - Award/Grant
    GIFT = "gift"                  # G - Gift
    TAX = "tax"                    # F - Tax withholding
    CONVERSION = "conversion"      # C - Conversion
    OTHER = "other"


class SignalStrength(str, Enum):
    """Signal strength levels."""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class InstitutionType(str, Enum):
    """Type of institutional investor."""
    HEDGE_FUND = "hedge_fund"
    MUTUAL_FUND = "mutual_fund"
    PENSION = "pension"
    INSURANCE = "insurance"
    BANK = "bank"
    FAMILY_OFFICE = "family_office"
    ENDOWMENT = "endowment"
    SOVEREIGN_WEALTH = "sovereign_wealth"
    OTHER = "other"


class FilingType(str, Enum):
    """SEC filing types."""
    FORM_4 = "form_4"
    FORM_3 = "form_3"
    FORM_5 = "form_5"
    FORM_144 = "form_144"
    FORM_13F = "form_13f"
    FORM_13D = "form_13d"
    FORM_13G = "form_13g"


# =============================================================================
# Constants
# =============================================================================

# Transaction type codes (SEC)
TRANSACTION_CODES = {
    "P": TransactionType.BUY,
    "S": TransactionType.SELL,
    "M": TransactionType.OPTION_EXERCISE,
    "A": TransactionType.GRANT,
    "G": TransactionType.GIFT,
    "F": TransactionType.TAX,
    "C": TransactionType.CONVERSION,
}

# Bullish transaction types
BULLISH_TRANSACTIONS = {TransactionType.BUY}

# Bearish transaction types (context-dependent)
BEARISH_TRANSACTIONS = {TransactionType.SELL}

# Neutral transaction types
NEUTRAL_TRANSACTIONS = {
    TransactionType.OPTION_EXERCISE,
    TransactionType.GRANT,
    TransactionType.GIFT,
    TransactionType.TAX,
}

# Insider title mappings
TITLE_TO_TYPE = {
    "ceo": InsiderType.CEO,
    "chief executive officer": InsiderType.CEO,
    "cfo": InsiderType.CFO,
    "chief financial officer": InsiderType.CFO,
    "coo": InsiderType.COO,
    "chief operating officer": InsiderType.COO,
    "cto": InsiderType.CTO,
    "chief technology officer": InsiderType.CTO,
    "president": InsiderType.PRESIDENT,
    "director": InsiderType.DIRECTOR,
    "10% owner": InsiderType.TEN_PCT_OWNER,
}

# Cluster detection thresholds
DEFAULT_CLUSTER_WINDOW_DAYS = 14
DEFAULT_CLUSTER_MIN_INSIDERS = 2
DEFAULT_CLUSTER_MIN_VALUE = 100_000

# Signal thresholds
LARGE_BUY_THRESHOLD = 500_000
SIGNIFICANT_BUY_THRESHOLD = 100_000
CEO_BUY_MULTIPLIER = 2.0  # CEO buys weighted 2x

# Institutional thresholds
SIGNIFICANT_HOLDING_PCT = 5.0  # 5% of portfolio
SIGNIFICANT_CHANGE_PCT = 25.0  # 25% position change


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class InsiderConfig:
    """Configuration for insider trading tracker."""
    cluster_window_days: int = 14
    cluster_min_insiders: int = 2
    cluster_min_value: float = 100_000
    large_buy_threshold: float = 500_000
    track_sells: bool = True
    include_options: bool = False


@dataclass
class InstitutionalConfig:
    """Configuration for institutional tracking."""
    min_holding_value: float = 1_000_000
    significant_change_pct: float = 25.0
    track_new_positions: bool = True
    track_sold_out: bool = True


DEFAULT_INSIDER_CONFIG = InsiderConfig()
DEFAULT_INSTITUTIONAL_CONFIG = InstitutionalConfig()
