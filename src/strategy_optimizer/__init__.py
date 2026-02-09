"""Adaptive Strategy Optimizer (PRD-148).

Genetic-algorithm-based parameter optimization with 20 tunable parameters
across EMA signals, trade executor, risk gate, signal fusion, and scanner
modules.  Includes a drift monitor for detecting live performance decay.
"""

from src.strategy_optimizer.parameters import (
    ParamType,
    ParamDef,
    ParameterSpace,
    build_default_parameter_space,
    DEFAULT_PARAM_COUNT,
)
from src.strategy_optimizer.evaluator import (
    PerformanceMetrics,
    EvaluationResult,
    StrategyEvaluator,
)
from src.strategy_optimizer.optimizer import (
    OptimizerConfig,
    OptimizationResult,
    AdaptiveOptimizer,
)
from src.strategy_optimizer.monitor import (
    DriftStatus,
    DriftConfig,
    DriftReport,
    PerformanceDriftMonitor,
)

__all__ = [
    # Parameters
    "ParamType",
    "ParamDef",
    "ParameterSpace",
    "build_default_parameter_space",
    "DEFAULT_PARAM_COUNT",
    # Evaluator
    "PerformanceMetrics",
    "EvaluationResult",
    "StrategyEvaluator",
    # Optimizer
    "OptimizerConfig",
    "OptimizationResult",
    "AdaptiveOptimizer",
    # Monitor
    "DriftStatus",
    "DriftConfig",
    "DriftReport",
    "PerformanceDriftMonitor",
]
