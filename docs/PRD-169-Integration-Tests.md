# PRD-169: Integration & E2E Test Suite

## Overview

Provides a comprehensive integration and end-to-end test suite that validates cross-module interactions across the Axion platform. Covers the full signal-to-trade-to-attribution pipeline, multi-broker order routing, risk gate enforcement, and dashboard rendering in a controlled test harness.

## Problem Statement

The platform has 7,290+ unit tests but no systematic integration tests. Each module is tested in isolation with mocks, meaning interface mismatches, serialization bugs, and timing issues between modules go undetected until live deployment. Critical paths like signal-generation -> risk-check -> execution -> attribution have never been tested end-to-end.

## Solution

A layered test framework with three tiers:

1. **Contract Tests** — Validate that each module's public API matches the interface expected by its consumers (type signatures, return shapes, error contracts)
2. **Pipeline Tests** — Test multi-module pipelines end-to-end with real objects (no mocks) against an in-memory database and simulated market data
3. **Scenario Tests** — Replay recorded market scenarios (flash crash, gap open, low liquidity) through the full stack and assert correct system behavior

## Architecture

```
┌─────────────────────────────────┐
│         Scenario Tests          │
│  (recorded market replay)       │
├─────────────────────────────────┤
│         Pipeline Tests          │
│  (multi-module, real objects)   │
├─────────────────────────────────┤
│         Contract Tests          │
│  (interface validation)         │
├─────────────────────────────────┤
│         Test Harness            │
│  (fixtures, factories, clock)   │
└─────────────────────────────────┘
         ↓            ↓
    In-Memory DB   Simulated Feed
    (SQLite)       (recorded data)
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `IntegrationConfig` | `src/integration_tests/config.py` | Test database URL, fixture paths, timeout settings |
| `TestHarness` | `src/integration_tests/harness.py` | Manages test lifecycle: DB setup, clock control, teardown |
| `ContractValidator` | `src/integration_tests/contracts.py` | Validates module interfaces against expected schemas |
| `PipelineRunner` | `src/integration_tests/pipeline.py` | Executes multi-module pipelines with real instances |
| `ScenarioPlayer` | `src/integration_tests/scenarios.py` | Replays recorded market data through full stack |
| `FixtureFactory` | `src/integration_tests/fixtures.py` | Generates realistic test data: signals, orders, positions |

## Test Pipelines Covered

| Pipeline | Modules Tested | Key Assertions |
|----------|---------------|----------------|
| Signal-to-Trade | EMA Signals -> Risk Gate -> Executor -> Attribution | Signal persisted, risk checked, order filled, P&L attributed |
| Multi-Strategy | Regime Detection -> Strategy Selector -> Signal Fusion | Correct strategy chosen per regime, blended conviction valid |
| Broker Routing | Multi-Broker -> Alpaca/Schwab/IBKR | Order routed to correct broker, position synced back |
| Feedback Loop | Attribution -> Aggregator -> Weight Adjuster -> Signal Producer | Weights updated, underperformers deprecated |
| Risk Cascade | New Order -> Unified Risk -> Correlation Guard -> Block/Allow | Correlated orders blocked, uncorrelated orders pass |

## Implementation

### Source Files
- `src/integration_tests/__init__.py` — Public API exports
- `src/integration_tests/config.py` — Test environment configuration
- `src/integration_tests/harness.py` — Test lifecycle manager with controlled clock
- `src/integration_tests/contracts.py` — Interface contract validation
- `src/integration_tests/pipeline.py` — Multi-module pipeline execution
- `src/integration_tests/scenarios.py` — Market scenario replay engine
- `src/integration_tests/fixtures.py` — Test data factory with realistic distributions

### Database
- Migration `alembic/versions/169_integration_tests.py` — revision `169`, down_revision `168`
- Creates `integration_test_runs` and `integration_test_results` tables for tracking test history

### Dashboard
- `app/pages/integration_tests.py` — 4 tabs: Test Runner, Pipeline Results, Scenario Replay, Contract Health

### Tests
- `tests/test_integration_tests.py` — ~60 tests covering harness setup/teardown, contract validation, pipeline execution, scenario replay, and fixture generation
- Additional integration test files in `tests/integration/` for each pipeline

## Dependencies

- Depends on: PRD-162 (Signal Persistence), PRD-163 (Unified Risk), PRD-165 (Strategy Selector), PRD-166 (Signal Feedback), PRD-167 (Enhanced Backtest), PRD-135 (Trade Executor), PRD-146 (Multi-Broker), PRD-160 (Trade Attribution)
- Depended on by: None (terminal node — validates all upstream modules)

## Success Metrics

- All 5 critical pipelines pass end-to-end with zero mocks
- Contract tests detect 100% of interface-breaking changes before merge
- Scenario tests cover at least 10 recorded market conditions (crash, rally, chop, gap, halt, etc.)
- Full integration suite runs in < 5 minutes on CI
- Zero production incidents caused by cross-module interface mismatches after deployment
