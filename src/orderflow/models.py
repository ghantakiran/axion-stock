"""Order Flow Analysis Data Models."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from src.orderflow.config import (
    FlowSignal,
    ImbalanceType,
    BlockSize,
    PressureDirection,
)


@dataclass
class OrderBookSnapshot:
    """Order book imbalance snapshot."""
    symbol: str = ""
    bid_volume: float = 0.0
    ask_volume: float = 0.0
    imbalance_ratio: float = 1.0
    imbalance_type: ImbalanceType = ImbalanceType.BALANCED
    signal: FlowSignal = FlowSignal.NEUTRAL
    timestamp: Optional[datetime] = None

    @property
    def total_volume(self) -> float:
        return self.bid_volume + self.ask_volume

    @property
    def net_imbalance(self) -> float:
        """Bid - ask volume."""
        return self.bid_volume - self.ask_volume

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid_volume": round(self.bid_volume, 0),
            "ask_volume": round(self.ask_volume, 0),
            "imbalance_ratio": round(self.imbalance_ratio, 3),
            "imbalance_type": self.imbalance_type.value,
            "signal": self.signal.value,
            "net_imbalance": round(self.net_imbalance, 0),
        }


@dataclass
class BlockTrade:
    """Detected block trade."""
    symbol: str = ""
    size: int = 0
    price: float = 0.0
    side: str = "buy"
    dollar_value: float = 0.0
    block_size: BlockSize = BlockSize.SMALL
    timestamp: Optional[datetime] = None

    @property
    def is_institutional(self) -> bool:
        return self.block_size == BlockSize.INSTITUTIONAL

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "size": self.size,
            "price": round(self.price, 4),
            "side": self.side,
            "dollar_value": round(self.dollar_value, 0),
            "block_size": self.block_size.value,
            "is_institutional": self.is_institutional,
        }


@dataclass
class FlowPressure:
    """Buy/sell pressure measurement."""
    symbol: str = ""
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    net_flow: float = 0.0
    pressure_ratio: float = 1.0
    direction: PressureDirection = PressureDirection.NEUTRAL
    cumulative_delta: float = 0.0
    date: Optional[date] = None

    @property
    def total_volume(self) -> float:
        return self.buy_volume + self.sell_volume

    @property
    def buy_pct(self) -> float:
        total = self.total_volume
        if total > 0:
            return round(self.buy_volume / total * 100, 1)
        return 50.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "buy_volume": round(self.buy_volume, 0),
            "sell_volume": round(self.sell_volume, 0),
            "net_flow": round(self.net_flow, 0),
            "pressure_ratio": round(self.pressure_ratio, 3),
            "direction": self.direction.value,
            "cumulative_delta": round(self.cumulative_delta, 0),
            "buy_pct": self.buy_pct,
        }


@dataclass
class SmartMoneySignal:
    """Smart money signal from institutional flow analysis."""
    symbol: str = ""
    signal: FlowSignal = FlowSignal.NEUTRAL
    confidence: float = 0.0
    block_ratio: float = 0.0
    institutional_net_flow: float = 0.0
    institutional_buy_pct: float = 50.0
    date: Optional[date] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signal": self.signal.value,
            "confidence": round(self.confidence, 2),
            "block_ratio": round(self.block_ratio, 3),
            "institutional_net_flow": round(self.institutional_net_flow, 0),
            "institutional_buy_pct": round(self.institutional_buy_pct, 1),
        }


@dataclass
class OrderFlowSnapshot:
    """Point-in-time order flow assessment."""
    symbol: str = ""
    book: Optional[OrderBookSnapshot] = None
    pressure: Optional[FlowPressure] = None
    smart_money: Optional[SmartMoneySignal] = None
    n_blocks: int = 0
    date: Optional[date] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "book": self.book.to_dict() if self.book else None,
            "pressure": self.pressure.to_dict() if self.pressure else None,
            "smart_money": self.smart_money.to_dict() if self.smart_money else None,
            "n_blocks": self.n_blocks,
        }
