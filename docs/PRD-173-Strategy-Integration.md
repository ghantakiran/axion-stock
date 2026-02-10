# PRD-173: Strategy Pipeline Integration

## Overview

Bridges the strategy and signal modules (PRDs 147, 155, 165) into the live bot pipeline through three adapter components. Adds regime-aware strategy selection, signal fusion, and strategy validation as new orchestrator stages, enabling the bot to dynamically adapt its trading approach based on market conditions.

## Problem Statement

The bot pipeline (PRD-170/171) currently processes raw EMA Cloud signals without leveraging:

- **Regime detection** (PRD-155) — Market regime is computed but not used to adapt execution parameters
- **Signal fusion** (PRD-147) — Multiple signal sources exist but are not combined before execution
- **Strategy selection** (PRD-165) — ADX-gated strategy routing is available but not wired into the pipeline

These modules operate independently. This PRD integrates them into the orchestrator's staged pipeline.

## Architecture

- **Module**: `src/bot_pipeline/`
- **Source files**: `regime_bridge.py`, `fusion_bridge.py`, `strategy_bridge.py`
- **Modified**: `orchestrator.py` (3 new stages)

### Pipeline Flow (Updated)

```
Signal
  --> Stage 0.5:  Regime Adaptation (RegimeBridge)       <-- NEW
  --> Stage 1:    Kill Switch (persistent)
  --> Stage 1.5:  SignalGuard (freshness + dedup)
  --> Stage 1.75: Signal Fusion (FusionBridge)            <-- NEW
  --> Stage 2:    Signal Recording (PRD-162)
  --> Stage 3:    Unified Risk Assessment (PRD-163)
  --> Stage 3.25: Strategy Validation (StrategyBridge)    <-- NEW
  --> Stage 3.5:  Instrument Routing (options/ETF)
  --> Stage 4:    Position Sizing
  --> Stage 5-9:  [unchanged]
```

## Key Components

### RegimeBridge (`src/bot_pipeline/regime_bridge.py`)

Maps the current market regime to a `StrategyProfile` and adapts `ExecutorConfig` accordingly.

**Key Methods:**

| Method | Description |
|--------|-------------|
| `detect_regime(market_data)` | Calls RegimeDetector, returns current regime label |
| `get_strategy_profile(regime)` | Maps regime to StrategyProfile with position limits, risk params |
| `adapt_config(config, regime)` | Returns modified ExecutorConfig for the detected regime |

**Regime-to-Config Mapping:**

| Regime | Max Positions | Daily Loss Limit | Signal Threshold | Stop Multiplier |
|--------|--------------|-------------------|-------------------|-----------------|
| `bull` | 8 | -1000 | 60 | 1.5x |
| `bear` | 3 | -400 | 80 | 1.0x |
| `sideways` | 5 | -600 | 70 | 1.2x |
| `crisis` | 1 | -200 | 95 | 0.8x |

### FusionBridge (`src/bot_pipeline/fusion_bridge.py`)

Wraps `SignalFusion` (PRD-147) for pipeline use. Combines multiple signal sources into a unified signal with aggregated conviction.

**Key Methods:**

| Method | Description |
|--------|-------------|
| `fuse_signals(signals)` | Merges signals by ticker, returns fused signal list |
| `update_weights(weight_map)` | Hot-updates source weights (called by FeedbackBridge) |
| `get_fusion_stats()` | Returns fusion metrics: merge rate, avg conviction lift |

**Fusion Logic:**
```python
class FusionBridge:
    def __init__(self, signal_fusion: SignalFusion):
        self._fusion = signal_fusion
        self._weight_overrides = {}

    def fuse_signals(self, signals: list) -> list:
        if self._weight_overrides:
            self._fusion.update_source_weights(self._weight_overrides)
        return self._fusion.fuse(signals)

    def update_weights(self, weight_map: dict):
        self._weight_overrides = weight_map
```

### StrategyBridge (`src/bot_pipeline/strategy_bridge.py`)

Wraps `StrategySelector` (PRD-165) for pipeline use. Validates that the fused signal aligns with the selected strategy before allowing execution.

**Key Methods:**

| Method | Description |
|--------|-------------|
| `validate_signal(signal, regime)` | Checks signal against active strategy constraints |
| `select_strategy(regime, adx)` | Returns active strategy name (ema_cloud or mean_reversion) |
| `get_decision_record()` | Returns StrategyDecisionRecord for audit |

**Validation Rules:**
- EMA Cloud strategy requires conviction >= 60 and trend-following signal types
- Mean-reversion strategy requires RSI/Z-score/Bollinger signal types
- ADX > 25 routes to EMA Cloud; ADX <= 25 routes to mean-reversion
- Mismatched signal type vs active strategy results in rejection with logged reason

## API / Interface

```python
# RegimeBridge usage
bridge = RegimeBridge(regime_detector)
regime = bridge.detect_regime(market_data)
adapted_config = bridge.adapt_config(pipeline_config, regime)

# FusionBridge usage
fusion_bridge = FusionBridge(signal_fusion)
fused = fusion_bridge.fuse_signals([ema_signal, rsi_signal, vwap_signal])

# StrategyBridge usage
strategy_bridge = StrategyBridge(strategy_selector)
decision = strategy_bridge.validate_signal(fused_signal, regime="bull")
if decision.approved:
    # proceed to risk assessment
```

## Database Schema

### strategy_decisions

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| decision_id | VARCHAR(50) | Unique decision identifier |
| ticker | VARCHAR(20) | Symbol evaluated |
| regime | VARCHAR(20) | Detected market regime |
| adx_value | Float | ADX value at decision time |
| selected_strategy | VARCHAR(30) | ema_cloud or mean_reversion |
| signal_type | VARCHAR(30) | Incoming signal type |
| approved | Boolean | Whether signal passed strategy validation |
| rejection_reason | Text | Reason if rejected (null if approved) |
| conviction_score | Float | Signal conviction at decision time |
| pipeline_run_id | VARCHAR(50) | Links to pipeline execution |
| created_at | DateTime | Decision timestamp |

**ORM Model:** `StrategyDecisionRecord` in `src/db/models.py`

## Migration

- **Revision**: 173
- **Down revision**: 172
- **Chain**: `...171 -> 172 -> 173`
- **File**: `alembic/versions/173_strategy_integration.py`
- Creates `strategy_decisions` table
- Indexes on `ticker`, `regime`, `selected_strategy`, and `created_at`

## Dashboard

4-tab Streamlit page at `app/pages/strategy_integration.py`:

| Tab | Contents |
|-----|----------|
| Regime Monitor | Current regime, historical regime timeline, config adaptations |
| Signal Fusion | Fusion merge rates, conviction distributions, source contributions |
| Strategy Selection | Strategy split (EMA vs mean-reversion), ADX distribution, approval rates |
| Decision Audit | Full decision log with filtering by ticker, regime, strategy |

## Testing

~48 tests in `tests/test_strategy_integration.py`:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestRegimeBridge` | ~14 | All 4 regimes, config adaptation, edge cases |
| `TestFusionBridge` | ~12 | Multi-source fusion, weight updates, empty inputs |
| `TestStrategyBridge` | ~12 | ADX routing, validation rules, rejection logging |
| `TestPipelineIntegration` | ~10 | Full pipeline with all 3 bridges, stage ordering |

## Dependencies

| Module | Usage |
|--------|-------|
| PRD-147 SignalFusion | Wrapped by FusionBridge for signal combination |
| PRD-155 RegimeAdaptive | Wrapped by RegimeBridge for regime detection |
| PRD-165 StrategySelector | Wrapped by StrategyBridge for strategy routing |
| PRD-170 BotOrchestrator | Modified to include 3 new pipeline stages |
| PRD-162 SignalPersistence | Records strategy decisions alongside signals |
