# PRD-41: Portfolio Rebalancing

## Overview
Automated portfolio rebalancing system with drift monitoring, calendar and
threshold-based triggers, tax-aware trade planning, and cost optimization.

## Components

### 1. Drift Monitor (`src/rebalancing/drift.py`)
- **Per-asset drift**: Absolute and relative weight drift vs target
- **Aggregate drift**: Portfolio-level drift metric (max, mean, RMSE)
- **Threshold check**: Flag assets exceeding drift tolerance
- **Drift history**: Track drift evolution over time

### 2. Rebalance Planner (`src/rebalancing/planner.py`)
- **Full rebalance**: Trade all positions to target weights
- **Threshold rebalance**: Only trade positions exceeding drift threshold
- **Tax-aware planning**: Avoid short-term gains, harvest losses
- **Cost optimization**: Minimize turnover subject to drift constraints
- **Min trade filter**: Skip trades below minimum dollar threshold

### 3. Rebalance Scheduler (`src/rebalancing/scheduler.py`)
- **Calendar triggers**: Weekly, monthly, quarterly, annual schedules
- **Threshold triggers**: Rebalance when max drift exceeds limit
- **Combined triggers**: Calendar OR threshold (whichever fires first)
- **Next date calculation**: When is the next scheduled rebalance

## Database Tables (Migration 027)
- `drift_snapshots` — Drift analysis history
- `rebalance_plans` — Generated rebalance plans
- `rebalance_trades` — Individual trade records
- `rebalance_schedules` — Scheduler configuration and history

## Dashboard (`app/pages/rebalancing.py`)
4-tab layout: Drift | Plan | Schedule | History
