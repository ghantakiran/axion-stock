# PRD-166: Signal Performance Feedback Loop

## Overview

Closes the loop between signal generation and trade outcomes by continuously measuring signal accuracy, adjusting conviction weights in real time, and deprecating consistently underperforming signal types. Transforms static signal scoring into a self-improving adaptive system.

## Problem Statement

Signal conviction scores are calibrated once during development and never updated. A signal type that worked well in Q1 may degrade in Q2, but the system keeps weighting it the same. PRD-160 (Trade Attribution) tracks performance retrospectively, but nothing feeds those insights back into the signal pipeline to adjust future behavior.

## Solution

A closed-loop feedback system with three stages:

1. **Performance Aggregator** — Pulls attribution data (PRD-160) and computes rolling accuracy, profit factor, and Sharpe per signal type
2. **Weight Adjuster** — Applies Bayesian updating to signal conviction multipliers based on recent performance, with decay for stale data
3. **Signal Deprecator** — Automatically downgrades or disables signal types that fall below minimum performance thresholds for configurable periods

## Architecture

```
Trade Attribution (PRD-160)
        ↓
    PerformanceAggregator
    (rolling windows: 7d/30d/90d)
        ↓
    WeightAdjuster
    (Bayesian update)
        ↓
  ┌─────┴─────┐
  │            │
Boost       Deprecate
(multiplier   (disable/
 > 1.0)       downgrade)
  │            │
  └─────┬─────┘
        ↓
    Signal Producers
    (updated conviction multipliers)
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `FeedbackConfig` | `src/signal_feedback/config.py` | Windows, thresholds, decay rates, min sample sizes |
| `PerformanceAggregator` | `src/signal_feedback/aggregator.py` | Rolling stats per signal type from attribution data |
| `WeightAdjuster` | `src/signal_feedback/adjuster.py` | Bayesian conviction multiplier updates |
| `SignalDeprecator` | `src/signal_feedback/deprecator.py` | Automatic disable/downgrade for underperformers |
| `FeedbackLoop` | `src/signal_feedback/loop.py` | Orchestrator: aggregate -> adjust -> deprecate cycle |

## Data Models

- `SignalWeightRecord` -> `signal_weight_history` (14 columns) — record_id, signal_type, window, accuracy, profit_factor, sharpe, prior_multiplier, posterior_multiplier, sample_count, updated_at, etc.
- `DeprecationEvent` -> `signal_deprecation_events` (10 columns) — event_id, signal_type, action (downgrade/disable/restore), reason, threshold_violated, performance_value, effective_at, expires_at

## Implementation

### Source Files
- `src/signal_feedback/__init__.py` — Public API exports
- `src/signal_feedback/config.py` — Configuration with default windows and thresholds
- `src/signal_feedback/aggregator.py` — Multi-window rolling performance computation
- `src/signal_feedback/adjuster.py` — Bayesian weight updates with configurable priors
- `src/signal_feedback/deprecator.py` — Rule-based deprecation with cooldown periods
- `src/signal_feedback/loop.py` — End-to-end orchestrator with scheduling

### Database
- Migration `alembic/versions/166_signal_feedback.py` — revision `166`, down_revision `165`

### Dashboard
- `app/pages/signal_feedback.py` — 4 tabs: Performance Dashboard, Weight History, Deprecation Log, Feedback Cycle

### Tests
- `tests/test_signal_feedback.py` — ~55 tests covering aggregation windows, Bayesian updates, deprecation triggers, restoration logic, and end-to-end loop execution

## Dependencies

- Depends on: PRD-160 (Trade Attribution), PRD-162 (Signal Persistence), PRD-134 (EMA Signals), PRD-147 (Signal Fusion)
- Depended on by: PRD-169 (Integration Tests)

## Success Metrics

- Conviction multipliers converge within 50 trades per signal type
- Deprecated signals are disabled within 24 hours of crossing threshold
- Portfolio Sharpe improves by > 10% after 90 days of feedback vs. static weights
- Weight adjustment cycle completes in < 2s for all active signal types
