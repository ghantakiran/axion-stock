"""Market Breadth Data Models.

Dataclasses for breadth snapshots, indicator values,
signals, and market health assessments.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional
import uuid

from src.breadth.config import (
    BreadthSignal,
    MarketHealthLevel,
    BreadthIndicator,
)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AdvanceDecline:
    """Single day advance-decline data."""
    date: date
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    up_volume: float = 0.0
    down_volume: float = 0.0

    @property
    def total(self) -> int:
        return self.advancing + self.declining + self.unchanged

    @property
    def net_advances(self) -> int:
        return self.advancing - self.declining

    @property
    def ad_ratio(self) -> float:
        if self.declining == 0:
            return float(self.advancing) if self.advancing > 0 else 0.0
        return self.advancing / self.declining

    @property
    def breadth_pct(self) -> float:
        """Advancing / (advancing + declining) as percentage."""
        total = self.advancing + self.declining
        if total == 0:
            return 0.5
        return self.advancing / total

    @property
    def volume_ratio(self) -> float:
        if self.down_volume == 0:
            return float(self.up_volume) if self.up_volume > 0 else 0.0
        return self.up_volume / self.down_volume


@dataclass
class NewHighsLows:
    """Daily new highs/lows data."""
    date: date
    new_highs: int = 0
    new_lows: int = 0

    @property
    def net(self) -> int:
        return self.new_highs - self.new_lows

    @property
    def ratio(self) -> float:
        if self.new_lows == 0:
            return float(self.new_highs) if self.new_highs > 0 else 0.0
        return self.new_highs / self.new_lows


@dataclass
class McClellanData:
    """McClellan Oscillator and Summation Index values."""
    date: date
    fast_ema: float = 0.0
    slow_ema: float = 0.0
    oscillator: float = 0.0
    summation_index: float = 0.0

    @property
    def is_overbought(self) -> bool:
        return self.oscillator > 100.0

    @property
    def is_oversold(self) -> bool:
        return self.oscillator < -100.0


@dataclass
class BreadthThrustData:
    """Breadth thrust indicator data."""
    date: date
    breadth_ema: float = 0.0
    thrust_active: bool = False
    days_since_last_thrust: Optional[int] = None
    last_thrust_date: Optional[date] = None


@dataclass
class BreadthSnapshot:
    """Complete breadth snapshot for a single date."""
    snapshot_id: str = field(default_factory=_new_id)
    date: date = field(default_factory=lambda: date.today())
    advance_decline: Optional[AdvanceDecline] = None
    new_highs_lows: Optional[NewHighsLows] = None
    mcclellan: Optional[McClellanData] = None
    thrust: Optional[BreadthThrustData] = None
    cumulative_ad_line: float = 0.0
    signals: list[BreadthSignal] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class SectorBreadth:
    """Breadth data for a single sector."""
    sector: str
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    pct_advancing: float = 0.0
    net_advances: int = 0
    breadth_score: float = 50.0
    momentum: str = "flat"  # improving, deteriorating, flat

    @property
    def total(self) -> int:
        return self.advancing + self.declining + self.unchanged


@dataclass
class MarketHealth:
    """Composite market health assessment."""
    health_id: str = field(default_factory=_new_id)
    date: date = field(default_factory=lambda: date.today())
    score: float = 50.0
    level: MarketHealthLevel = MarketHealthLevel.NEUTRAL
    ad_score: float = 50.0
    nhnl_score: float = 50.0
    mcclellan_score: float = 50.0
    thrust_score: float = 50.0
    volume_score: float = 50.0
    signals: list[BreadthSignal] = field(default_factory=list)
    sector_breadth: list[SectorBreadth] = field(default_factory=list)
    summary: str = ""
    computed_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict:
        return {
            "date": str(self.date),
            "score": self.score,
            "level": self.level.value,
            "ad_score": self.ad_score,
            "nhnl_score": self.nhnl_score,
            "mcclellan_score": self.mcclellan_score,
            "thrust_score": self.thrust_score,
            "volume_score": self.volume_score,
            "signals": [s.value for s in self.signals],
            "n_sectors": len(self.sector_breadth),
            "summary": self.summary,
        }
