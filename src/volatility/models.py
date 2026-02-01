"""Volatility Analysis Data Models."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.volatility.config import VolMethod, VolRegime


@dataclass
class VolEstimate:
    """Single volatility measurement."""
    symbol: str = ""
    value: float = 0.0
    method: VolMethod = VolMethod.HISTORICAL
    window: int = 21
    annualized: bool = True
    date: Optional[date] = None
    percentile: Optional[float] = None

    @property
    def daily(self) -> float:
        """Convert annualized vol to daily."""
        if self.annualized:
            return self.value / (252.0 ** 0.5)
        return self.value

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "value": round(self.value, 6),
            "method": self.method.value,
            "window": self.window,
            "annualized": self.annualized,
            "date": self.date.isoformat() if self.date else None,
            "percentile": round(self.percentile, 1) if self.percentile is not None else None,
        }


@dataclass
class TermStructurePoint:
    """One tenor on the term structure."""
    tenor_days: int = 0
    implied_vol: Optional[float] = None
    realized_vol: Optional[float] = None

    @property
    def vol_risk_premium(self) -> Optional[float]:
        """IV - RV spread."""
        if self.implied_vol is not None and self.realized_vol is not None:
            return round(self.implied_vol - self.realized_vol, 6)
        return None


@dataclass
class TermStructure:
    """Full volatility term structure."""
    symbol: str = ""
    points: list[TermStructurePoint] = field(default_factory=list)
    date: Optional[date] = None

    @property
    def is_contango(self) -> bool:
        """Longer-dated vol > shorter-dated vol."""
        if len(self.points) < 2:
            return False
        vols = [p.implied_vol or p.realized_vol or 0 for p in self.points]
        return vols[-1] > vols[0]

    @property
    def is_backwardation(self) -> bool:
        """Shorter-dated vol > longer-dated vol."""
        if len(self.points) < 2:
            return False
        vols = [p.implied_vol or p.realized_vol or 0 for p in self.points]
        return vols[0] > vols[-1]

    @property
    def slope(self) -> float:
        """Vol per tenor-day from first to last point."""
        if len(self.points) < 2:
            return 0.0
        first = self.points[0]
        last = self.points[-1]
        v_first = first.implied_vol or first.realized_vol or 0
        v_last = last.implied_vol or last.realized_vol or 0
        day_diff = last.tenor_days - first.tenor_days
        if day_diff == 0:
            return 0.0
        return (v_last - v_first) / day_diff


@dataclass
class VolSmilePoint:
    """Single strike on the volatility smile."""
    strike: float = 0.0
    moneyness: float = 1.0
    implied_vol: float = 0.0
    delta: Optional[float] = None


@dataclass
class VolSurface:
    """Complete volatility surface (strike x tenor)."""
    symbol: str = ""
    spot: float = 0.0
    smiles: dict[int, list[VolSmilePoint]] = field(default_factory=dict)
    date: Optional[date] = None

    @property
    def tenors(self) -> list[int]:
        """Available tenor days, sorted."""
        return sorted(self.smiles.keys())

    @property
    def n_tenors(self) -> int:
        return len(self.smiles)

    def get_smile(self, tenor_days: int) -> list[VolSmilePoint]:
        """Get smile for a specific tenor."""
        return self.smiles.get(tenor_days, [])

    def get_atm_vol(self, tenor_days: int) -> Optional[float]:
        """Get ATM implied vol for a tenor."""
        smile = self.get_smile(tenor_days)
        if not smile:
            return None
        # Find point closest to moneyness=1.0
        closest = min(smile, key=lambda p: abs(p.moneyness - 1.0))
        return closest.implied_vol

    def skew(self, tenor_days: int, delta: float = 0.25) -> Optional[float]:
        """25-delta skew: put vol - call vol."""
        smile = self.get_smile(tenor_days)
        if len(smile) < 3:
            return None
        # Approximate: low moneyness vol - high moneyness vol
        sorted_pts = sorted(smile, key=lambda p: p.moneyness)
        otm_put = sorted_pts[0]
        otm_call = sorted_pts[-1]
        return round(otm_put.implied_vol - otm_call.implied_vol, 6)

    def butterfly(self, tenor_days: int) -> Optional[float]:
        """25-delta butterfly: wing avg - ATM."""
        smile = self.get_smile(tenor_days)
        if len(smile) < 3:
            return None
        sorted_pts = sorted(smile, key=lambda p: p.moneyness)
        wing_avg = (sorted_pts[0].implied_vol + sorted_pts[-1].implied_vol) / 2
        atm_vol = self.get_atm_vol(tenor_days)
        if atm_vol is None:
            return None
        return round(wing_avg - atm_vol, 6)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "spot": self.spot,
            "date": self.date.isoformat() if self.date else None,
            "n_tenors": self.n_tenors,
            "tenors": self.tenors,
        }


@dataclass
class VolRegimeState:
    """Current volatility regime assessment."""
    regime: VolRegime = VolRegime.NORMAL
    current_vol: float = 0.0
    avg_vol: float = 0.0
    z_score: float = 0.0
    percentile: float = 50.0
    days_in_regime: int = 0
    date: Optional[date] = None
    prev_regime: Optional[VolRegime] = None
    regime_changed: bool = False

    @property
    def vol_ratio(self) -> float:
        """Current vol / average vol."""
        if self.avg_vol > 0:
            return round(self.current_vol / self.avg_vol, 3)
        return 1.0

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "current_vol": round(self.current_vol, 6),
            "avg_vol": round(self.avg_vol, 6),
            "z_score": round(self.z_score, 2),
            "percentile": round(self.percentile, 1),
            "days_in_regime": self.days_in_regime,
            "date": self.date.isoformat() if self.date else None,
            "regime_changed": self.regime_changed,
        }


@dataclass
class VolConePoint:
    """One window on the volatility cone."""
    window: int = 0
    percentiles: dict[float, float] = field(default_factory=dict)
    current: float = 0.0

    @property
    def current_percentile(self) -> Optional[float]:
        """Where current vol sits in the cone."""
        if not self.percentiles:
            return None
        below = [p for p, v in self.percentiles.items() if v <= self.current]
        if not below:
            return 0.0
        return max(below)
