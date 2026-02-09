# PRD-163: Unified Risk Context & Correlation Guard

## Overview

Consolidates all risk checks into a single real-time risk context that every order must pass before execution. Adds a correlation guard that prevents concentrated exposure to correlated assets, sectors, or factor tilts across the entire portfolio.

## Problem Statement

Risk logic is scattered across the trade executor's 8-check gate (PRD-135), the risk manager (PRD-150), and per-broker position limits. No single component sees the full picture — a portfolio can accumulate dangerous correlation exposure (e.g., 5 tech longs that all move together) even though each individual position passes its own risk check.

## Solution

Two tightly integrated components:

1. **Unified Risk Context** — Aggregates position, P&L, drawdown, exposure, and order-queue data into a single in-memory snapshot refreshed every tick
2. **Correlation Guard** — Computes rolling pairwise and sector-level correlations, blocks new orders that would push portfolio correlation above configurable thresholds

## Architecture

```
Broker Positions ──┐
P&L Stream ────────┤
Pending Orders ────┤──▶ RiskContext (snapshot)
Market Data ───────┤         ↓
Factor Exposures ──┘    CorrelationGuard
                             ↓
                     ┌───────┴───────┐
                     │               │
                   ALLOW           BLOCK
                  (to executor)   (reason logged)
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `UnifiedRiskConfig` | `src/unified_risk/config.py` | Thresholds: max correlation, sector cap, drawdown limit |
| `RiskContext` | `src/unified_risk/context.py` | Real-time aggregated snapshot of all risk dimensions |
| `CorrelationGuard` | `src/unified_risk/correlation.py` | Rolling pairwise/sector correlation with order blocking |
| `RiskGate` | `src/unified_risk/gate.py` | Single pass/fail entry point called before every order |
| `ExposureAnalyzer` | `src/unified_risk/exposure.py` | Factor tilt and sector concentration analysis |

## Data Models

- `RiskSnapshot` -> `risk_snapshots` (18 columns) — snapshot_id, timestamp, total_exposure, net_beta, max_sector_pct, avg_pairwise_corr, drawdown_pct, open_order_exposure, etc.
- `CorrelationBlock` -> `correlation_blocks` (12 columns) — block_id, order_id, ticker, reason, portfolio_corr_before, portfolio_corr_after, threshold, blocked_at

## Implementation

### Source Files
- `src/unified_risk/__init__.py` — Public API exports
- `src/unified_risk/config.py` — Configuration with default thresholds
- `src/unified_risk/context.py` — RiskContext with tick-level refresh
- `src/unified_risk/correlation.py` — Rolling correlation matrix, sector aggregation
- `src/unified_risk/gate.py` — Unified gate: drawdown + exposure + correlation + velocity checks
- `src/unified_risk/exposure.py` — Factor and sector exposure decomposition

### Database
- Migration `alembic/versions/163_unified_risk.py` — revision `163`, down_revision `162`

### Dashboard
- `app/pages/unified_risk.py` — 4 tabs: Risk Snapshot, Correlation Matrix, Block Log, Exposure Heatmap

### Tests
- `tests/test_unified_risk.py` — ~55 tests covering context assembly, correlation calculation, gate pass/block logic, sector caps, and exposure analysis

## Dependencies

- Depends on: PRD-135 (Trade Executor risk gate), PRD-150 (Risk Manager), PRD-146 (Multi-Broker positions)
- Depended on by: PRD-165 (Strategy Selector), PRD-167 (Enhanced Backtest)

## Success Metrics

- All orders pass through unified gate with < 5ms added latency
- Correlation guard blocks orders that would push portfolio pairwise correlation above 0.7 threshold
- Zero instances of sector concentration exceeding configured cap in live trading
- Risk snapshot staleness never exceeds 2 seconds during market hours
