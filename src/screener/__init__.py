"""Advanced Stock Screener.

Comprehensive stock screening with 100+ filters, custom formulas,
saved screens, alerts, and backtesting.

Example:
    from src.screener import ScreenerEngine, Screen, FilterCondition, Operator
    
    # Create a screen
    screen = Screen(
        name="Value Screen",
        filters=[
            FilterCondition(filter_id="pe_ratio", operator=Operator.LT, value=15),
            FilterCondition(filter_id="dividend_yield", operator=Operator.GT, value=2.0),
        ]
    )
    
    # Run the screen
    engine = ScreenerEngine()
    result = engine.run_screen(screen, stock_data)
    print(f"Found {result.matches} matches")
"""

from src.screener.config import (
    FilterCategory,
    DataType,
    Operator,
    Universe,
    SortOrder,
    AlertType,
    RebalanceFrequency,
    SECTORS,
    DEFAULT_COLUMNS,
    ScreenerConfig,
    BacktestConfig,
    DEFAULT_SCREENER_CONFIG,
    DEFAULT_BACKTEST_CONFIG,
)

from src.screener.models import (
    FilterDefinition,
    FilterCondition,
    CustomFormula,
    Screen,
    ScreenMatch,
    ScreenResult,
    ScreenAlert,
    AlertNotification,
    ScreenBacktestConfig,
    ScreenBacktestResult,
)

from src.screener.filters import FilterRegistry, FILTER_REGISTRY
from src.screener.expression import ExpressionParser, ExpressionError
from src.screener.engine import ScreenerEngine, ScreenManager
from src.screener.presets import get_preset_screens, PRESET_SCREENS
from src.screener.alerts import ScreenAlertManager
from src.screener.backtest import ScreenBacktester


__all__ = [
    # Config
    "FilterCategory",
    "DataType",
    "Operator",
    "Universe",
    "SortOrder",
    "AlertType",
    "RebalanceFrequency",
    "SECTORS",
    "DEFAULT_COLUMNS",
    "ScreenerConfig",
    "BacktestConfig",
    "DEFAULT_SCREENER_CONFIG",
    "DEFAULT_BACKTEST_CONFIG",
    # Models
    "FilterDefinition",
    "FilterCondition",
    "CustomFormula",
    "Screen",
    "ScreenMatch",
    "ScreenResult",
    "ScreenAlert",
    "AlertNotification",
    "ScreenBacktestConfig",
    "ScreenBacktestResult",
    # Core
    "FilterRegistry",
    "FILTER_REGISTRY",
    "ExpressionParser",
    "ExpressionError",
    "ScreenerEngine",
    "ScreenManager",
    # Presets
    "get_preset_screens",
    "PRESET_SCREENS",
    # Alerts
    "ScreenAlertManager",
    # Backtest
    "ScreenBacktester",
]
