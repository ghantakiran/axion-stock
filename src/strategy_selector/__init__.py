"""Multi-Strategy Selector & Mean-Reversion Engine (PRD-165).

Dynamically selects between trading strategies based on market regime:
- EMA Cloud (trend-following) for trending markets
- Mean-Reversion for choppy/range-bound markets
- ADX gating to determine trend strength
- Walk-forward A/B comparison between strategies

Strategy routing: Regime detected → ADX gated → Strategy selected → Signals generated
"""

from src.strategy_selector.mean_reversion import (
    MeanReversionConfig,
    MeanReversionSignal,
    MeanReversionStrategy,
)
from src.strategy_selector.selector import (
    StrategySelector,
    StrategyChoice,
    SelectorConfig,
)
from src.strategy_selector.adx_gate import (
    ADXGate,
    ADXConfig,
    TrendStrength,
)

__all__ = [
    # Mean reversion
    "MeanReversionConfig",
    "MeanReversionSignal",
    "MeanReversionStrategy",
    # Selector
    "StrategySelector",
    "StrategyChoice",
    "SelectorConfig",
    # ADX gate
    "ADXGate",
    "ADXConfig",
    "TrendStrength",
]
