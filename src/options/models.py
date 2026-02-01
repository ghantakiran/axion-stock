"""Options Chain Analysis Data Models."""

from dataclasses import dataclass, field
from typing import Optional

from src.options.pricing import OptionType
from src.options.config import FlowType, ActivityLevel, Sentiment


@dataclass
class OptionGreeks:
    """Greeks for a single option contract."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    implied_vol: float = 0.0
    price: float = 0.0

    def to_dict(self) -> dict:
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "implied_vol": self.implied_vol,
            "price": self.price,
        }


@dataclass
class OptionContract:
    """Single option contract with market data and greeks."""
    symbol: str = ""
    strike: float = 0.0
    expiry_days: float = 30.0
    option_type: OptionType = OptionType.CALL
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    open_interest: int = 0
    greeks: Optional[OptionGreeks] = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2 if self.bid > 0 and self.ask > 0 else self.last

    @property
    def spread(self) -> float:
        return self.ask - self.bid if self.ask > 0 and self.bid > 0 else 0.0

    @property
    def vol_oi_ratio(self) -> float:
        return self.volume / self.open_interest if self.open_interest > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "strike": self.strike,
            "expiry_days": self.expiry_days,
            "option_type": self.option_type.value,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "mid": self.mid,
            "spread": self.spread,
            "vol_oi_ratio": self.vol_oi_ratio,
            "greeks": self.greeks.to_dict() if self.greeks else None,
        }


@dataclass
class ChainSummary:
    """Aggregate options chain metrics."""
    symbol: str = ""
    underlying_price: float = 0.0
    total_call_volume: int = 0
    total_put_volume: int = 0
    total_call_oi: int = 0
    total_put_oi: int = 0
    pcr_volume: float = 0.0
    pcr_oi: float = 0.0
    max_pain_strike: float = 0.0
    iv_skew: float = 0.0
    atm_iv: float = 0.0
    n_contracts: int = 0

    @property
    def total_volume(self) -> int:
        return self.total_call_volume + self.total_put_volume

    @property
    def total_oi(self) -> int:
        return self.total_call_oi + self.total_put_oi

    @property
    def net_sentiment(self) -> str:
        if self.pcr_volume < 0.7:
            return "bullish"
        elif self.pcr_volume > 1.3:
            return "bearish"
        return "neutral"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "underlying_price": self.underlying_price,
            "total_call_volume": self.total_call_volume,
            "total_put_volume": self.total_put_volume,
            "total_call_oi": self.total_call_oi,
            "total_put_oi": self.total_put_oi,
            "pcr_volume": self.pcr_volume,
            "pcr_oi": self.pcr_oi,
            "max_pain_strike": self.max_pain_strike,
            "iv_skew": self.iv_skew,
            "atm_iv": self.atm_iv,
            "n_contracts": self.n_contracts,
            "total_volume": self.total_volume,
            "total_oi": self.total_oi,
            "net_sentiment": self.net_sentiment,
        }


@dataclass
class OptionsFlow:
    """Classified options flow event."""
    symbol: str = ""
    strike: float = 0.0
    expiry_days: float = 30.0
    option_type: OptionType = OptionType.CALL
    flow_type: FlowType = FlowType.NORMAL
    size: int = 0
    premium: float = 0.0
    side: str = ""
    sentiment: Sentiment = Sentiment.NEUTRAL

    @property
    def is_sweep(self) -> bool:
        return self.flow_type == FlowType.SWEEP

    @property
    def is_block(self) -> bool:
        return self.flow_type == FlowType.BLOCK

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "strike": self.strike,
            "expiry_days": self.expiry_days,
            "option_type": self.option_type.value,
            "flow_type": self.flow_type.value,
            "size": self.size,
            "premium": self.premium,
            "side": self.side,
            "sentiment": self.sentiment.value,
            "is_sweep": self.is_sweep,
            "is_block": self.is_block,
        }


@dataclass
class UnusualActivity:
    """Flagged unusual options activity."""
    symbol: str = ""
    strike: float = 0.0
    expiry_days: float = 30.0
    option_type: OptionType = OptionType.CALL
    volume: int = 0
    open_interest: int = 0
    vol_oi_ratio: float = 0.0
    premium: float = 0.0
    activity_level: ActivityLevel = ActivityLevel.NORMAL
    score: float = 0.0

    @property
    def is_unusual(self) -> bool:
        return self.activity_level in (ActivityLevel.UNUSUAL, ActivityLevel.EXTREME)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "strike": self.strike,
            "expiry_days": self.expiry_days,
            "option_type": self.option_type.value,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "vol_oi_ratio": self.vol_oi_ratio,
            "premium": self.premium,
            "activity_level": self.activity_level.value,
            "score": self.score,
            "is_unusual": self.is_unusual,
        }
