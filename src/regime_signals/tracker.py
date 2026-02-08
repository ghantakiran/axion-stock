"""Performance tracking for regime-aware signals."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict

from src.regime_signals.config import (
    RegimeType,
    SignalType,
    SignalDirection,
    SignalOutcome,
)
from src.regime_signals.models import (
    RegimeSignal,
    SignalPerformance,
)


class PerformanceTracker:
    """Tracks signal performance and accuracy."""
    
    def __init__(self):
        # signal_id -> SignalPerformance
        self._active_signals: dict[str, SignalPerformance] = {}
        # Completed signals
        self._completed_signals: list[SignalPerformance] = []
    
    def start_tracking(
        self,
        signal: RegimeSignal,
        entry_price: Optional[float] = None,
    ) -> SignalPerformance:
        """Start tracking a signal."""
        performance = SignalPerformance(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            signal_type=signal.signal_type,
            regime_type=signal.regime_type,
            direction=signal.direction,
            entry_price=entry_price or signal.entry_price or 0.0,
        )
        
        self._active_signals[signal.signal_id] = performance
        return performance
    
    def update_prices(
        self,
        signal_id: str,
        current_price: float,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
    ) -> Optional[SignalPerformance]:
        """Update tracking with current prices."""
        if signal_id not in self._active_signals:
            return None
        
        perf = self._active_signals[signal_id]
        
        # Update max favorable/adverse excursion
        if perf.direction == SignalDirection.LONG:
            favorable = (high_price or current_price) - perf.entry_price
            adverse = perf.entry_price - (low_price or current_price)
        elif perf.direction == SignalDirection.SHORT:
            favorable = perf.entry_price - (low_price or current_price)
            adverse = (high_price or current_price) - perf.entry_price
        else:
            favorable = 0
            adverse = 0
        
        if perf.max_favorable is None or favorable > perf.max_favorable:
            perf.max_favorable = favorable
        if perf.max_adverse is None or adverse > perf.max_adverse:
            perf.max_adverse = adverse
        
        return perf
    
    def close_signal(
        self,
        signal_id: str,
        exit_price: float,
        hit_stop_loss: bool = False,
        hit_take_profit: bool = False,
    ) -> Optional[SignalPerformance]:
        """Close and record a signal."""
        if signal_id not in self._active_signals:
            return None
        
        perf = self._active_signals.pop(signal_id)
        perf.close_position(exit_price)
        perf.hit_stop_loss = hit_stop_loss
        perf.hit_take_profit = hit_take_profit
        
        self._completed_signals.append(perf)
        return perf
    
    def expire_signal(self, signal_id: str) -> Optional[SignalPerformance]:
        """Expire a signal that wasn't acted upon."""
        if signal_id not in self._active_signals:
            return None
        
        perf = self._active_signals.pop(signal_id)
        perf.outcome = SignalOutcome.EXPIRED
        perf.closed_at = datetime.now(timezone.utc)
        
        self._completed_signals.append(perf)
        return perf
    
    def get_active_signals(
        self,
        symbol: Optional[str] = None,
    ) -> list[SignalPerformance]:
        """Get active signals."""
        signals = list(self._active_signals.values())
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]
        return signals
    
    def get_completed_signals(
        self,
        symbol: Optional[str] = None,
        regime_type: Optional[RegimeType] = None,
        signal_type: Optional[SignalType] = None,
        days: Optional[int] = None,
    ) -> list[SignalPerformance]:
        """Get completed signals with filters."""
        signals = self._completed_signals
        
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]
        if regime_type:
            signals = [s for s in signals if s.regime_type == regime_type]
        if signal_type:
            signals = [s for s in signals if s.signal_type == signal_type]
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            signals = [s for s in signals if s.opened_at >= cutoff]
        
        return signals
    
    def get_accuracy_by_regime(self) -> dict[str, dict]:
        """Get signal accuracy broken down by regime."""
        by_regime: dict[RegimeType, list[SignalPerformance]] = defaultdict(list)
        
        for perf in self._completed_signals:
            if perf.outcome != SignalOutcome.PENDING:
                by_regime[perf.regime_type].append(perf)
        
        results = {}
        for regime_type, performances in by_regime.items():
            wins = sum(1 for p in performances if p.outcome == SignalOutcome.WIN)
            total = len(performances)
            
            returns = [p.return_pct for p in performances if p.return_pct is not None]
            avg_return = sum(returns) / len(returns) if returns else 0
            
            results[regime_type.value] = {
                "total_signals": total,
                "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
                "avg_return": avg_return,
            }
        
        return results
    
    def get_accuracy_by_signal_type(self) -> dict[str, dict]:
        """Get signal accuracy broken down by signal type."""
        by_type: dict[SignalType, list[SignalPerformance]] = defaultdict(list)
        
        for perf in self._completed_signals:
            if perf.outcome != SignalOutcome.PENDING:
                by_type[perf.signal_type].append(perf)
        
        results = {}
        for signal_type, performances in by_type.items():
            wins = sum(1 for p in performances if p.outcome == SignalOutcome.WIN)
            total = len(performances)
            
            returns = [p.return_pct for p in performances if p.return_pct is not None]
            avg_return = sum(returns) / len(returns) if returns else 0
            
            results[signal_type.value] = {
                "total_signals": total,
                "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
                "avg_return": avg_return,
            }
        
        return results
    
    def get_regime_signal_matrix(self) -> dict:
        """Get cross-tabulation of regime vs signal type performance."""
        matrix: dict[tuple, list[SignalPerformance]] = defaultdict(list)
        
        for perf in self._completed_signals:
            if perf.outcome != SignalOutcome.PENDING:
                key = (perf.regime_type.value, perf.signal_type.value)
                matrix[key].append(perf)
        
        results = {}
        for (regime, signal), performances in matrix.items():
            wins = sum(1 for p in performances if p.outcome == SignalOutcome.WIN)
            total = len(performances)
            
            returns = [p.return_pct for p in performances if p.return_pct is not None]
            avg_return = sum(returns) / len(returns) if returns else 0
            
            results[f"{regime}_{signal}"] = {
                "total_signals": total,
                "win_rate": wins / total if total > 0 else 0,
                "avg_return": avg_return,
            }
        
        return results
    
    def get_summary_stats(self) -> dict:
        """Get overall summary statistics."""
        completed = [p for p in self._completed_signals if p.outcome != SignalOutcome.PENDING]
        
        if not completed:
            return {
                "total_completed": 0,
                "total_active": len(self._active_signals),
            }
        
        wins = sum(1 for p in completed if p.outcome == SignalOutcome.WIN)
        losses = sum(1 for p in completed if p.outcome == SignalOutcome.LOSS)
        
        returns = [p.return_pct for p in completed if p.return_pct is not None]
        avg_return = sum(returns) / len(returns) if returns else 0
        
        durations = [p.duration_hours for p in completed if p.duration_hours is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Calculate profit factor
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = abs(sum(r for r in returns if r < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            "total_completed": len(completed),
            "total_active": len(self._active_signals),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / len(completed) if completed else 0,
            "avg_return": avg_return,
            "total_return": sum(returns),
            "profit_factor": profit_factor,
            "avg_duration_hours": avg_duration,
            "best_return": max(returns) if returns else 0,
            "worst_return": min(returns) if returns else 0,
        }
    
    def get_recent_signals(self, limit: int = 20) -> list[SignalPerformance]:
        """Get most recent completed signals."""
        sorted_signals = sorted(
            self._completed_signals,
            key=lambda s: s.closed_at or s.opened_at,
            reverse=True,
        )
        return sorted_signals[:limit]
