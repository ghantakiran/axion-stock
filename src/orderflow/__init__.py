"""Order Flow Analysis Module.

Order book imbalance detection, block trade identification,
buy/sell pressure measurement, and smart money signal generation.

Example:
    from src.orderflow import ImbalanceAnalyzer, BlockDetector, PressureAnalyzer

    analyzer = ImbalanceAnalyzer()
    snapshot = analyzer.compute_imbalance(bid_volume=50000, ask_volume=30000, symbol="AAPL")
    print(f"Imbalance: {snapshot.imbalance_type.value} ({snapshot.signal.value})")

    pressure = PressureAnalyzer()
    flow = pressure.compute_pressure(buy_volume=100000, sell_volume=60000)
    print(f"Direction: {flow.direction.value}, Delta: {flow.cumulative_delta}")
"""

from src.orderflow.config import (
    FlowSignal,
    ImbalanceType,
    BlockSize,
    PressureDirection,
    ImbalanceConfig,
    BlockConfig,
    PressureConfig,
    OrderFlowConfig,
    DEFAULT_IMBALANCE_CONFIG,
    DEFAULT_BLOCK_CONFIG,
    DEFAULT_PRESSURE_CONFIG,
    DEFAULT_CONFIG,
)

from src.orderflow.models import (
    OrderBookSnapshot,
    BlockTrade,
    FlowPressure,
    SmartMoneySignal,
    OrderFlowSnapshot,
)

from src.orderflow.imbalance import ImbalanceAnalyzer
from src.orderflow.blocks import BlockDetector
from src.orderflow.pressure import PressureAnalyzer

__all__ = [
    # Config
    "FlowSignal",
    "ImbalanceType",
    "BlockSize",
    "PressureDirection",
    "ImbalanceConfig",
    "BlockConfig",
    "PressureConfig",
    "OrderFlowConfig",
    "DEFAULT_IMBALANCE_CONFIG",
    "DEFAULT_BLOCK_CONFIG",
    "DEFAULT_PRESSURE_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "OrderBookSnapshot",
    "BlockTrade",
    "FlowPressure",
    "SmartMoneySignal",
    "OrderFlowSnapshot",
    # Components
    "ImbalanceAnalyzer",
    "BlockDetector",
    "PressureAnalyzer",
]
