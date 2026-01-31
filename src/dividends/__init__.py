"""Dividend Tracker.

Track dividends, project income, analyze safety, and simulate DRIP.

Example:
    from src.dividends import (
        DividendCalendar, DividendEvent, DividendFrequency,
        IncomeProjector, DividendHolding,
        SafetyAnalyzer, GrowthAnalyzer, DRIPSimulator, TaxAnalyzer,
    )
    
    # Create calendar
    calendar = DividendCalendar()
    calendar.add_event(DividendEvent(
        symbol="AAPL",
        ex_dividend_date=date(2024, 2, 9),
        amount=0.24,
    ))
    
    # Project income
    projector = IncomeProjector()
    holdings = [
        DividendHolding(symbol="AAPL", shares=100, annual_dividend=0.96, ...),
    ]
    income = projector.project_portfolio(holdings)
    print(f"Annual income: ${income.annual_income:,.2f}")
"""

from src.dividends.config import (
    DividendFrequency,
    DividendType,
    SafetyRating,
    DividendStatus,
    TaxClassification,
    FREQUENCY_MULTIPLIERS,
    SECTOR_YIELDS,
    DividendConfig,
    DRIPConfig,
    DEFAULT_DIVIDEND_CONFIG,
    DEFAULT_DRIP_CONFIG,
)

from src.dividends.models import (
    DividendEvent,
    DividendRecord,
    DividendHolding,
    DividendIncome,
    PortfolioIncome,
    YieldAnalysis,
    DividendSafety,
    DividendGrowth,
    DRIPYear,
    DRIPSimulation,
    DividendTaxAnalysis,
)

from src.dividends.calendar import (
    DividendCalendar,
    generate_sample_calendar,
)

from src.dividends.income import IncomeProjector

from src.dividends.safety import (
    SafetyAnalyzer,
    FinancialMetrics,
)

from src.dividends.growth import (
    GrowthAnalyzer,
    generate_sample_growth_data,
)

from src.dividends.drip import DRIPSimulator

from src.dividends.tax import TaxAnalyzer


__all__ = [
    # Config
    "DividendFrequency",
    "DividendType",
    "SafetyRating",
    "DividendStatus",
    "TaxClassification",
    "FREQUENCY_MULTIPLIERS",
    "SECTOR_YIELDS",
    "DividendConfig",
    "DRIPConfig",
    "DEFAULT_DIVIDEND_CONFIG",
    "DEFAULT_DRIP_CONFIG",
    # Models
    "DividendEvent",
    "DividendRecord",
    "DividendHolding",
    "DividendIncome",
    "PortfolioIncome",
    "YieldAnalysis",
    "DividendSafety",
    "DividendGrowth",
    "DRIPYear",
    "DRIPSimulation",
    "DividendTaxAnalysis",
    # Calendar
    "DividendCalendar",
    "generate_sample_calendar",
    # Income
    "IncomeProjector",
    # Safety
    "SafetyAnalyzer",
    "FinancialMetrics",
    # Growth
    "GrowthAnalyzer",
    "generate_sample_growth_data",
    # DRIP
    "DRIPSimulator",
    # Tax
    "TaxAnalyzer",
]
