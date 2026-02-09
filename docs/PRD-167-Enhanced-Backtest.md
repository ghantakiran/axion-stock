# PRD-167: Enhanced Backtesting Realism

## Overview

Upgrades the backtesting engine with realistic market simulation including slippage models, partial fill emulation, latency injection, and market impact estimation. Bridges the gap between backtest results and live trading performance to reduce overfitting and improve strategy confidence.

## Problem Statement

Current backtests assume instant fills at exact prices with zero market impact. This produces unrealistically optimistic results — strategies that backtest at 60% win rate often achieve only 45-50% live. The discrepancy erodes trust in backtested strategies and leads to over-allocation to strategies that underperform in production.

## Solution

Four simulation layers added to the existing backtest engine:

1. **Slippage Model** — Configurable slippage based on volatility, spread, and order size relative to volume
2. **Partial Fill Simulator** — Models realistic fill rates using historical volume profiles, with unfilled remainder handled as IOC or queued
3. **Latency Injector** — Adds configurable signal-to-order and order-to-fill delays to simulate real-world infrastructure latency
4. **Market Impact Estimator** — Square-root impact model that penalizes large orders proportionally to their fraction of average volume

## Architecture

```
BacktestEngine (existing)
        ↓
    Order Submission
        ↓
┌───────────────────┐
│  LatencyInjector   │ ← configurable delay
│  (signal → order)  │
└────────┬──────────┘
         ↓
┌───────────────────┐
│  SlippageModel     │ ← volatility + spread based
│  (price adjustment)│
└────────┬──────────┘
         ↓
┌───────────────────┐
│  MarketImpact      │ ← sqrt(size/ADV) model
│  (additional cost)  │
└────────┬──────────┘
         ↓
┌───────────────────┐
│  PartialFill       │ ← volume profile simulation
│  (fill quantity)    │
└────────┬──────────┘
         ↓
    Fill Event (realistic)
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `RealismConfig` | `src/enhanced_backtest/config.py` | Slippage bps, latency ms, impact params, fill model |
| `SlippageModel` | `src/enhanced_backtest/slippage.py` | Volatility-scaled and spread-based slippage |
| `PartialFillSim` | `src/enhanced_backtest/partial_fill.py` | Volume-profile fill simulation with remainder handling |
| `LatencyInjector` | `src/enhanced_backtest/latency.py` | Configurable delay injection between pipeline stages |
| `MarketImpactModel` | `src/enhanced_backtest/impact.py` | Square-root impact with decay for sequential orders |
| `RealismEngine` | `src/enhanced_backtest/engine.py` | Orchestrator that wraps existing backtest fills |

## Data Models

- `RealismRunRecord` -> `realism_backtest_runs` (20 columns) — run_id, strategy, slippage_config, impact_config, latency_config, fill_rate, total_slippage_cost, total_impact_cost, realistic_sharpe, ideal_sharpe, realism_gap, etc.
- `FillSimulationRecord` -> `fill_simulations` (14 columns) — fill_id, run_id, order_id, requested_qty, filled_qty, fill_price, ideal_price, slippage_bps, impact_bps, latency_ms, timestamp

## Implementation

### Source Files
- `src/enhanced_backtest/__init__.py` — Public API exports
- `src/enhanced_backtest/config.py` — Configuration with realistic default parameters
- `src/enhanced_backtest/slippage.py` — Multi-mode slippage: fixed, volatility-scaled, spread-based
- `src/enhanced_backtest/partial_fill.py` — Volume profile and participation rate fill model
- `src/enhanced_backtest/latency.py` — Gaussian and percentile-based latency injection
- `src/enhanced_backtest/impact.py` — Square-root market impact with temporal decay
- `src/enhanced_backtest/engine.py` — Wraps backtest order flow with all realism layers

### Database
- Migration `alembic/versions/167_enhanced_backtest.py` — revision `167`, down_revision `166`

### Dashboard
- `app/pages/enhanced_backtest.py` — 4 tabs: Realism Config, Slippage Analysis, Fill Simulation, Ideal vs. Realistic Comparison

### Tests
- `tests/test_enhanced_backtest.py` — ~55 tests covering slippage calculations, partial fill logic, latency injection, impact model accuracy, and end-to-end realism gap measurement

## Dependencies

- Depends on: PRD-138 (Bot Backtesting), PRD-163 (Unified Risk), PRD-165 (Strategy Selector)
- Depended on by: PRD-169 (Integration Tests)

## Success Metrics

- Realism gap (backtest Sharpe vs. live Sharpe) reduced from > 30% to < 10%
- Partial fill simulation matches historical fill rates within 5% for liquid equities
- Slippage model predicts actual slippage within 2 bps for orders < 1% ADV
- Backtest execution time increase < 20% with all realism layers enabled
