"""Parameter optimization for regime-aware signals."""

from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

from src.regime_signals.config import (
    RegimeType,
    SignalType,
    REGIME_PARAMETERS,
    SignalConfig,
    DEFAULT_SIGNAL_CONFIG,
)
from src.regime_signals.models import (
    RegimeParameter,
    SignalPerformance,
    SignalOutcome,
)


class ParameterOptimizer:
    """Optimizes signal parameters based on historical performance."""
    
    def __init__(self, config: SignalConfig = DEFAULT_SIGNAL_CONFIG):
        self.config = config
        # (regime_type, signal_type, indicator, param) -> RegimeParameter
        self._parameters: dict[tuple, RegimeParameter] = {}
        # Store performance history
        self._performance_history: list[SignalPerformance] = []
        
        # Initialize default parameters
        self._init_default_parameters()
    
    def _init_default_parameters(self) -> None:
        """Initialize default parameters from config."""
        for regime_type_str, params in REGIME_PARAMETERS.items():
            regime_type = RegimeType(regime_type_str)
            
            # Create parameters for each indicator/param combination
            for param_name, value in params.items():
                if param_name == "preferred_signals":
                    continue
                
                if isinstance(value, (int, float)):
                    key = (regime_type, SignalType.MOMENTUM, "general", param_name)
                    self._parameters[key] = RegimeParameter(
                        regime_type=regime_type,
                        signal_type=SignalType.MOMENTUM,
                        indicator_name="general",
                        parameter_name=param_name,
                        default_value=float(value),
                    )
    
    def get_parameter(
        self,
        regime_type: RegimeType,
        signal_type: SignalType,
        indicator_name: str,
        parameter_name: str,
    ) -> Optional[RegimeParameter]:
        """Get a specific parameter."""
        key = (regime_type, signal_type, indicator_name, parameter_name)
        return self._parameters.get(key)
    
    def get_parameters_for_regime(
        self,
        regime_type: RegimeType,
    ) -> list[RegimeParameter]:
        """Get all parameters for a regime."""
        return [
            param for key, param in self._parameters.items()
            if key[0] == regime_type
        ]
    
    def get_optimized_value(
        self,
        regime_type: RegimeType,
        signal_type: SignalType,
        indicator_name: str,
        parameter_name: str,
    ) -> float:
        """Get optimized (or default) parameter value."""
        param = self.get_parameter(regime_type, signal_type, indicator_name, parameter_name)
        if param:
            return param.get_value()
        
        # Fall back to regime parameters
        regime_params = REGIME_PARAMETERS.get(regime_type.value, {})
        return regime_params.get(parameter_name, 0.0)
    
    def record_performance(self, performance: SignalPerformance) -> None:
        """Record signal performance for optimization."""
        self._performance_history.append(performance)
    
    def optimize_parameters(
        self,
        regime_type: Optional[RegimeType] = None,
        signal_type: Optional[SignalType] = None,
    ) -> dict[str, float]:
        """Optimize parameters based on historical performance."""
        # Filter performance history
        filtered = self._performance_history
        
        if regime_type:
            filtered = [p for p in filtered if p.regime_type == regime_type]
        if signal_type:
            filtered = [p for p in filtered if p.signal_type == signal_type]
        
        if len(filtered) < self.config.min_samples_for_optimization:
            return {}  # Not enough data
        
        # Group by regime and signal type
        groups: dict[tuple, list[SignalPerformance]] = defaultdict(list)
        for perf in filtered:
            key = (perf.regime_type, perf.signal_type)
            groups[key].append(perf)
        
        optimized = {}
        
        for (reg_type, sig_type), performances in groups.items():
            if len(performances) < self.config.min_samples_for_optimization:
                continue
            
            # Calculate win rate
            wins = sum(1 for p in performances if p.outcome == SignalOutcome.WIN)
            win_rate = wins / len(performances)
            
            # Calculate average return
            returns = [p.return_pct for p in performances if p.return_pct is not None]
            avg_return = sum(returns) / len(returns) if returns else 0
            
            # Calculate Sharpe-like ratio
            if returns and len(returns) > 1:
                mean_ret = avg_return
                variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
                std_ret = variance ** 0.5
                sharpe = mean_ret / std_ret if std_ret > 0 else 0
            else:
                sharpe = 0
            
            # Adjust parameters based on performance
            key_prefix = f"{reg_type.value}_{sig_type.value}"
            
            # If win rate is low, tighten stops
            current_stop = self.get_optimized_value(reg_type, sig_type, "general", "stop_loss_atr")
            if win_rate < 0.4:
                optimized[f"{key_prefix}_stop_loss_atr"] = current_stop * 0.9
            elif win_rate > 0.6:
                optimized[f"{key_prefix}_stop_loss_atr"] = current_stop * 1.1
            
            # If average return is good, widen take profit
            current_tp = self.get_optimized_value(reg_type, sig_type, "general", "take_profit_atr")
            if avg_return > 2.0:
                optimized[f"{key_prefix}_take_profit_atr"] = current_tp * 1.2
            elif avg_return < 0:
                optimized[f"{key_prefix}_take_profit_atr"] = current_tp * 0.8
            
            # Update parameters
            for param_key, new_value in optimized.items():
                if param_key.startswith(key_prefix):
                    param_name = param_key.replace(f"{key_prefix}_", "")
                    param = self.get_parameter(reg_type, sig_type, "general", param_name)
                    if param:
                        param.optimized_value = new_value
                        param.sample_size = len(performances)
                        param.optimization_score = sharpe
                        param.last_optimized_at = datetime.now(timezone.utc)
        
        return optimized
    
    def get_performance_stats(
        self,
        regime_type: Optional[RegimeType] = None,
        signal_type: Optional[SignalType] = None,
    ) -> dict:
        """Get performance statistics."""
        filtered = self._performance_history
        
        if regime_type:
            filtered = [p for p in filtered if p.regime_type == regime_type]
        if signal_type:
            filtered = [p for p in filtered if p.signal_type == signal_type]
        
        if not filtered:
            return {"total_signals": 0}
        
        wins = sum(1 for p in filtered if p.outcome == SignalOutcome.WIN)
        losses = sum(1 for p in filtered if p.outcome == SignalOutcome.LOSS)
        breakeven = sum(1 for p in filtered if p.outcome == SignalOutcome.BREAKEVEN)
        
        returns = [p.return_pct for p in filtered if p.return_pct is not None]
        
        return {
            "total_signals": len(filtered),
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": wins / len(filtered) if filtered else 0,
            "avg_return": sum(returns) / len(returns) if returns else 0,
            "max_return": max(returns) if returns else 0,
            "min_return": min(returns) if returns else 0,
            "total_return": sum(returns) if returns else 0,
        }
    
    def reset_optimization(self, regime_type: Optional[RegimeType] = None) -> int:
        """Reset optimized values to defaults."""
        count = 0
        for key, param in self._parameters.items():
            if regime_type is None or key[0] == regime_type:
                param.optimized_value = None
                param.optimization_score = None
                param.sample_size = 0
                count += 1
        return count
