# PRD-148: Adaptive Strategy Optimizer

## Overview
Genetic-algorithm-based parameter optimization system for the Axion trading platform. Automatically tunes 20 strategy parameters across 6 modules to maximize risk-adjusted returns.

## Architecture
```
ParameterSpace (20 params) → AdaptiveOptimizer (GA) → StrategyEvaluator (scoring)
                                                            ↓
                                                    PerformanceDriftMonitor
```

## Components

### Parameter Space (`parameters.py`)
- **ParamType**: CONTINUOUS, INTEGER, CATEGORICAL, BOOLEAN
- **ParamDef**: Name, type, bounds, default, module origin
- **ParameterSpace**: Collection with add/get/serialize helpers
- **20 default parameters** across: ema_signals (5), trade_executor (5), risk (3), signal_fusion (4), scanner (2), regime (1)

### Strategy Evaluator (`evaluator.py`)
- **5-factor composite scoring** (0-100):
  - Sharpe ratio (30%) normalized to max 3.0
  - Total return (20%) normalized to max 100%
  - Max drawdown (20%) inverted (lower = better)
  - Win rate (15%)
  - Profit factor (15%) normalized to max 3.0
- **Regime penalty**: 10% reduction for bear markets

### Adaptive Optimizer (`optimizer.py`)
- **Genetic algorithm** with configurable:
  - Population size (default 20)
  - Generations (default 10)
  - Mutation rate (10%), crossover rate (70%)
  - Elite preservation (top 3)
  - Tournament selection (k=3)
- **Convergence tracking** via final generation score std-dev
- **Improvement history** logs generation-over-generation deltas

### Drift Monitor (`monitor.py`)
- **4 severity levels**: HEALTHY, WARNING, CRITICAL, STALE
- **Sharpe threshold**: 30% decline triggers WARNING
- **Drawdown threshold**: 15% worsening triggers WARNING
- **Both breached**: CRITICAL → "halt_and_review"
- **Recommendations**: healthy / reoptimize / halt_and_review

## Dashboard
4-tab Streamlit interface:
1. **Parameter Space**: All 20 params grouped by module
2. **Optimizer**: GA controls and demo run with generation chart
3. **Performance**: Evaluation metrics display
4. **Drift Monitor**: Status indicator, baseline vs current comparison

## Database Tables
- `strategy_optimization_runs`: Run history with best params and scores
- `strategy_drift_checks`: Drift check history with status and deltas
