"""Tax Optimization System.

Comprehensive tax management for investment portfolios including:
- Tax-loss harvesting with substitute security suggestions
- Wash sale detection and tracking per IRS rules
- Tax lot management with multiple selection methods (FIFO, LIFO, MinTax, etc.)
- Gain/loss tracking by holding period (short-term vs long-term)
- Tax liability estimation with federal/state rates and NIIT
- Tax report generation (Form 8949, Schedule D, summaries)

Example:
    from src.tax import TaxLotManager, TaxLossHarvester, TaxEstimator
    
    # Manage tax lots
    lot_manager = TaxLotManager()
    lot = lot_manager.create_lot("acct1", "AAPL", 100, 150.0)
    
    # Find harvesting opportunities
    harvester = TaxLossHarvester(lot_manager, wash_tracker)
    opportunities = harvester.find_opportunities(positions)
    
    # Estimate tax liability
    estimator = TaxEstimator()
    estimate = estimator.estimate_liability(
        ordinary_income=100_000,
        short_term_gains=5_000,
        long_term_gains=10_000,
    )
"""

from src.tax.config import (
    FilingStatus,
    HoldingPeriod,
    LotSelectionMethod,
    AcquisitionType,
    AccountType,
    BasisReportingCategory,
    AdjustmentCode,
    FEDERAL_BRACKETS_2024,
    LTCG_BRACKETS_2024,
    NIIT_THRESHOLDS,
    NIIT_RATE,
    STATE_TAX_RATES,
    NO_INCOME_TAX_STATES,
    TaxProfile,
    HarvestingConfig,
    WashSaleConfig,
    LotSelectionConfig,
    TaxConfig,
    DEFAULT_TAX_CONFIG,
)

from src.tax.models import (
    TaxLot,
    RealizedGain,
    WashSale,
    HarvestOpportunity,
    HarvestResult,
    GainLossReport,
    TaxEstimate,
    TaxSavingsProjection,
    Form8949Entry,
    Form8949,
    ScheduleD,
    TaxSummaryReport,
)

from src.tax.lots import (
    TaxLotManager,
    LotSelectionResult,
)

from src.tax.wash_sales import (
    WashSaleTracker,
    WashSaleCheckResult,
    Transaction,
)

from src.tax.harvesting import (
    TaxLossHarvester,
    Position,
    ETF_SUBSTITUTES,
)

from src.tax.estimator import (
    TaxEstimator,
)

from src.tax.reports import (
    TaxReportGenerator,
)

__all__ = [
    # Config - Enums
    "FilingStatus",
    "HoldingPeriod",
    "LotSelectionMethod",
    "AcquisitionType",
    "AccountType",
    "BasisReportingCategory",
    "AdjustmentCode",
    # Config - Constants
    "FEDERAL_BRACKETS_2024",
    "LTCG_BRACKETS_2024",
    "NIIT_THRESHOLDS",
    "NIIT_RATE",
    "STATE_TAX_RATES",
    "NO_INCOME_TAX_STATES",
    # Config - Dataclasses
    "TaxProfile",
    "HarvestingConfig",
    "WashSaleConfig",
    "LotSelectionConfig",
    "TaxConfig",
    "DEFAULT_TAX_CONFIG",
    # Models - Core
    "TaxLot",
    "RealizedGain",
    "WashSale",
    "HarvestOpportunity",
    "HarvestResult",
    "GainLossReport",
    # Models - Tax Estimation
    "TaxEstimate",
    "TaxSavingsProjection",
    # Models - Reports
    "Form8949Entry",
    "Form8949",
    "ScheduleD",
    "TaxSummaryReport",
    # Lot Management
    "TaxLotManager",
    "LotSelectionResult",
    # Wash Sales
    "WashSaleTracker",
    "WashSaleCheckResult",
    "Transaction",
    # Harvesting
    "TaxLossHarvester",
    "Position",
    "ETF_SUBSTITUTES",
    # Estimation
    "TaxEstimator",
    # Reports
    "TaxReportGenerator",
]
