"""Data models for Regime-Aware Signals."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid

from src.regime_signals.config import (
    RegimeType,
    SignalType,
    SignalDirection,
    DetectionMethod,
    TrendDirection,
    VolatilityLevel,
    SignalOutcome,
)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RegimeState:
    """Market regime state."""
    
    symbol: str
    regime_type: RegimeType
    detection_method: DetectionMethod
    confidence: float = 0.0
    volatility_level: Optional[VolatilityLevel] = None
    trend_direction: Optional[TrendDirection] = None
    trend_strength: Optional[float] = None
    regime_duration_days: int = 0
    transition_probability: Optional[float] = None
    timestamp: datetime = field(default_factory=_now)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "regime_type": self.regime_type.value,
            "detection_method": self.detection_method.value,
            "confidence": self.confidence,
            "volatility_level": self.volatility_level.value if self.volatility_level else None,
            "trend_direction": self.trend_direction.value if self.trend_direction else None,
            "trend_strength": self.trend_strength,
            "regime_duration_days": self.regime_duration_days,
            "transition_probability": self.transition_probability,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class RegimeSignal:
    """Regime-aware trading signal."""
    
    symbol: str
    signal_type: SignalType
    direction: SignalDirection
    regime_type: RegimeType
    strength: float = 0.0
    confidence: float = 0.0
    regime_confidence: float = 0.0
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    indicators_used: list[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    notes: str = ""
    signal_id: str = field(default_factory=_new_id)
    is_active: bool = True
    expires_at: Optional[datetime] = None
    timestamp: datetime = field(default_factory=_now)
    
    def calculate_risk_reward(self) -> Optional[float]:
        """Calculate risk/reward ratio."""
        if not all([self.entry_price, self.stop_loss, self.take_profit]):
            return None
        
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        
        if risk == 0:
            return None
        
        self.risk_reward_ratio = reward / risk
        return self.risk_reward_ratio
    
    def is_expired(self) -> bool:
        """Check if signal has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "direction": self.direction.value,
            "regime_type": self.regime_type.value,
            "strength": self.strength,
            "confidence": self.confidence,
            "regime_confidence": self.regime_confidence,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward_ratio": self.risk_reward_ratio,
            "indicators_used": self.indicators_used,
            "parameters": self.parameters,
            "notes": self.notes,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SignalPerformance:
    """Signal performance tracking."""
    
    signal_id: str
    symbol: str
    signal_type: SignalType
    regime_type: RegimeType
    direction: SignalDirection
    entry_price: float
    exit_price: Optional[float] = None
    return_pct: Optional[float] = None
    max_favorable: Optional[float] = None
    max_adverse: Optional[float] = None
    duration_hours: Optional[float] = None
    hit_stop_loss: bool = False
    hit_take_profit: bool = False
    outcome: SignalOutcome = SignalOutcome.PENDING
    opened_at: datetime = field(default_factory=_now)
    closed_at: Optional[datetime] = None
    
    def close_position(self, exit_price: float) -> None:
        """Close the position and calculate returns."""
        self.exit_price = exit_price
        self.closed_at = datetime.now(timezone.utc)
        
        if self.direction == SignalDirection.LONG:
            self.return_pct = ((exit_price - self.entry_price) / self.entry_price) * 100
        elif self.direction == SignalDirection.SHORT:
            self.return_pct = ((self.entry_price - exit_price) / self.entry_price) * 100
        else:
            self.return_pct = 0.0
        
        self.duration_hours = (self.closed_at - self.opened_at).total_seconds() / 3600
        
        # Determine outcome
        if self.return_pct > 0.1:
            self.outcome = SignalOutcome.WIN
        elif self.return_pct < -0.1:
            self.outcome = SignalOutcome.LOSS
        else:
            self.outcome = SignalOutcome.BREAKEVEN
    
    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "regime_type": self.regime_type.value,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "return_pct": self.return_pct,
            "max_favorable": self.max_favorable,
            "max_adverse": self.max_adverse,
            "duration_hours": self.duration_hours,
            "hit_stop_loss": self.hit_stop_loss,
            "hit_take_profit": self.hit_take_profit,
            "outcome": self.outcome.value,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }


@dataclass
class RegimeParameter:
    """Regime-specific parameter configuration."""
    
    regime_type: RegimeType
    signal_type: SignalType
    indicator_name: str
    parameter_name: str
    default_value: float
    optimized_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    optimization_score: Optional[float] = None
    sample_size: int = 0
    last_optimized_at: Optional[datetime] = None
    param_id: str = field(default_factory=_new_id)
    is_active: bool = True
    
    def get_value(self) -> float:
        """Get the current value (optimized or default)."""
        return self.optimized_value if self.optimized_value is not None else self.default_value
    
    def to_dict(self) -> dict:
        return {
            "param_id": self.param_id,
            "regime_type": self.regime_type.value,
            "signal_type": self.signal_type.value,
            "indicator_name": self.indicator_name,
            "parameter_name": self.parameter_name,
            "default_value": self.default_value,
            "optimized_value": self.optimized_value,
            "current_value": self.get_value(),
            "min_value": self.min_value,
            "max_value": self.max_value,
            "optimization_score": self.optimization_score,
            "sample_size": self.sample_size,
            "last_optimized_at": self.last_optimized_at.isoformat() if self.last_optimized_at else None,
            "is_active": self.is_active,
        }


@dataclass
class SignalResult:
    """Result of signal generation."""
    
    signals: list[RegimeSignal]
    regime_state: RegimeState
    generation_time_ms: float = 0.0
    indicators_computed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "signals": [s.to_dict() for s in self.signals],
            "regime_state": self.regime_state.to_dict(),
            "generation_time_ms": self.generation_time_ms,
            "indicators_computed": self.indicators_computed,
            "warnings": self.warnings,
            "signal_count": len(self.signals),
        }
