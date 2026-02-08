"""PRD-97: GIPS-Compliant Performance Reporting."""

from .config import (
    ReturnMethod,
    FeeType,
    CompositeMembership,
    DispersionMethod,
    ReportPeriod,
    GIPSConfig,
    CompositeConfig,
    FeeSchedule,
)
from .models import (
    CompositeDefinition,
    CompositeReturn,
    CompositePeriod,
    DispersionResult,
    GIPSDisclosure,
    ComplianceCheck,
    ComplianceReport,
    GIPSPresentation,
    PortfolioAssignment,
    PerformanceRecord,
)
from .composite import CompositeManager
from .calculator import GIPSCalculator
from .dispersion import DispersionCalculator
from .compliance import ComplianceValidator
from .generator import GIPSReportGenerator

__all__ = [
    # Config
    "ReturnMethod",
    "FeeType",
    "CompositeMembership",
    "DispersionMethod",
    "ReportPeriod",
    "GIPSConfig",
    "CompositeConfig",
    "FeeSchedule",
    # Models
    "CompositeDefinition",
    "CompositeReturn",
    "CompositePeriod",
    "DispersionResult",
    "GIPSDisclosure",
    "ComplianceCheck",
    "ComplianceReport",
    "GIPSPresentation",
    "PortfolioAssignment",
    "PerformanceRecord",
    # Core
    "CompositeManager",
    "GIPSCalculator",
    "DispersionCalculator",
    "ComplianceValidator",
    "GIPSReportGenerator",
]
