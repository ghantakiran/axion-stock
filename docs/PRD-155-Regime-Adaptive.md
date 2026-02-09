# PRD-155: Regime-Adaptive Strategy

## Overview
Dynamically adjusts trading parameters based on detected market regimes. When the market shifts from bull to bear or enters crisis mode, the strategy engine automatically tightens risk, reduces position sizes, and filters signals to match the new environment. This creates a feedback loop between regime detection and trade execution.

## Architecture
```
RegimeDetector → RegimeMonitor → track transitions + circuit breaker
                      ↓
                ProfileRegistry → get regime-specific StrategyProfile
                      ↓
                RegimeAdapter → apply profile to ExecutorConfig
                      ↓               ↓
              ConfigAdaptation   filter_signals() → suppress bad types
                      ↓
              PerformanceTuner → further adjust based on recent P&L
```

## Components

### Strategy Profiles (`profiles.py`)
- **4 built-in profiles**: Bull (aggressive), Bear (defensive), Sideways (neutral), Crisis (protective)
- **Profile blending**: Low-confidence regimes blend toward sideways baseline
- **Custom profiles**: Register overrides for specific market conditions
- **Signal type preferences**: Each regime prefers/avoids specific EMA signal types

### Regime Adapter (`adapter.py`)
- **Config overlay**: Maps StrategyProfile fields onto ExecutorConfig
- **Smooth transitions**: Interpolate parameters during regime changes (no sudden jumps)
- **Signal filtering**: Remove signals that perform poorly in current regime
- **Adaptation history**: Full audit trail of parameter changes with reasons

### Performance Tuner (`tuner.py`)
- **Streak detection**: Track consecutive wins/losses
- **Dynamic tightening**: 3+ losses → reduce risk parameters (floor at 50% of base)
- **Dynamic loosening**: 5+ wins with >60% win rate → increase toward defaults (cap at 130%)
- **Trade-by-trade tracking**: Records PnL, signal type, and regime for each trade

### Regime Monitor (`monitor.py`)
- **Transition detection**: Identifies regime changes above confidence threshold
- **Circuit breaker**: Caps transitions at 5/hour to prevent whipsawing
- **Duration tracking**: How long the current regime has persisted
- **Frequency analysis**: Which regime transitions occur most often

## Regime Parameters

| Parameter | Bull | Bear | Sideways | Crisis |
|-----------|------|------|----------|--------|
| Max Risk/Trade | 6% | 3% | 4% | 2% |
| Max Positions | 12 | 5 | 8 | 3 |
| Daily Loss Limit | 12% | 6% | 8% | 4% |
| R:R Target | 1.8 | 2.5 | 2.0 | 3.0 |
| Min Conviction | 50 | 70 | 60 | 80 |
| Size Multiplier | 1.2x | 0.6x | 0.8x | 0.3x |
| Time Stop | 180m | 90m | 120m | 60m |
| Scale-in | Yes | No | Yes | No |

## Database Tables
- `regime_adaptations`: Config adaptation log with before/after snapshots
- `regime_transitions`: Regime transition history with confidence and method

## Dashboard
4-tab Streamlit interface:
1. **Profiles**: View/compare all regime profiles with blending preview
2. **Adaptation**: Live config adaptation with change visualization
3. **Tuning**: Performance-based parameter tuning with streak simulation
4. **Monitor**: Regime transition timeline with circuit breaker status

## Integration Points
- **regime** (PRD-55/61): RegimeType enum and ensemble detection
- **trade_executor** (PRD-135): ExecutorConfig parameter adaptation
- **ema_signals** (PRD-134): Signal type filtering by regime
- **agent_consensus** (PRD-154): Regime context feeds into agent voting
