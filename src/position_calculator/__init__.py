"""Position Calculator Module.

Trade-level position sizing with risk management, portfolio heat
tracking, and drawdown monitoring.

Example:
    from src.position_calculator import PositionSizingEngine, SizingInputs

    engine = PositionSizingEngine()
    result = engine.calculate(SizingInputs(
        account_value=100_000,
        entry_price=150.00,
        stop_price=145.00,
    ))
    print(f"Buy {result.position_size} shares, risking ${result.risk_amount:.0f}")
"""

from src.position_calculator.config import (
    StopType,
    InstrumentType,
    SizingMethod,
    DrawdownAction,
    SizingConfig,
    KellyConfig,
    HeatConfig,
    DrawdownConfig,
    PositionCalculatorConfig,
    DEFAULT_SIZING_CONFIG,
    DEFAULT_KELLY_CONFIG,
    DEFAULT_HEAT_CONFIG,
    DEFAULT_DRAWDOWN_CONFIG,
    DEFAULT_CONFIG,
)

from src.position_calculator.models import (
    SizingInputs,
    SizingResult,
    PositionRisk,
    PortfolioHeat,
    DrawdownState,
    SizingRecord,
)

from src.position_calculator.sizing import PositionSizingEngine
from src.position_calculator.heat import HeatTracker
from src.position_calculator.drawdown import DrawdownMonitor

__all__ = [
    # Config
    "StopType",
    "InstrumentType",
    "SizingMethod",
    "DrawdownAction",
    "SizingConfig",
    "KellyConfig",
    "HeatConfig",
    "DrawdownConfig",
    "PositionCalculatorConfig",
    "DEFAULT_SIZING_CONFIG",
    "DEFAULT_KELLY_CONFIG",
    "DEFAULT_HEAT_CONFIG",
    "DEFAULT_DRAWDOWN_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "SizingInputs",
    "SizingResult",
    "PositionRisk",
    "PortfolioHeat",
    "DrawdownState",
    "SizingRecord",
    # Components
    "PositionSizingEngine",
    "HeatTracker",
    "DrawdownMonitor",
]
