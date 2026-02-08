# PRD-92: Portfolio Rebalancing

## Overview
Automated portfolio rebalancing with drift detection, calendar/threshold/combined triggers, tax-aware trade planning, cost management, broker execution integration, and what-if simulation.

## Components

### 1. Drift Monitor (`src/rebalancing/drift.py`)
- **DriftMonitor** — Portfolio weight drift detection
- Absolute/relative drift computation per asset
- Critical drift flagging (>10%), threshold breaches (>5%)
- Aggregate metrics: max drift, mean drift, RMSE drift
- Drift history tracking

### 2. Rebalance Planner (`src/rebalancing/planner.py`)
- **RebalancePlanner** — Trade plan generation
- `plan_full_rebalance()` — Rebalance all assets to exact targets
- `plan_threshold_rebalance()` — Rebalance only drifted assets
- `plan_tax_aware_rebalance()` — Skip short-term gains, harvest losses
- Trade filtering (min $100), cost/tax estimates

### 3. Rebalance Scheduler (`src/rebalancing/scheduler.py`)
- **RebalanceScheduler** — Trigger management
- Triggers: CALENDAR, THRESHOLD, COMBINED, MANUAL
- Calendar: WEEKLY, MONTHLY, QUARTERLY, ANNUAL
- Automatic drift checks, next date calculation, state tracking

### 4. Rebalance Engine (`src/execution/rebalancer.py`)
- **RebalanceEngine** — Full broker integration
- Sell-first logic (free cash before buying)
- Limit order support with configurable buffers
- Stop-loss triggers, signal-based exits (factor score thresholds)

### 5. Rebalance Bot (`src/bots/rebalance.py`)
- **RebalanceBot** — Three automated rebalance methods
- Full rebalance, threshold-only (drift-based), tax-aware

### 6. Rebalance Simulator (`src/scenarios/rebalance.py`)
- **RebalanceSimulator** — What-if analysis
- Post-rebalance drift projections, tax impact calculations
- Optimal frequency recommendations

### 7. Configuration (`src/rebalancing/config.py`)
- DriftConfig: threshold 5%, critical 10%, method (absolute/relative)
- CalendarConfig: frequency, day/month scheduling
- TaxConfig: short-term gain avoidance, loss harvesting, wash sale rules
- CostConfig: min trade size, spread costs, commissions

### 8. Models (`src/rebalancing/models.py`)
- **Holding** — Symbol, shares, price, weights, cost basis, acquisition date
- **DriftAnalysis** — Per-asset drift with critical flags
- **PortfolioDrift** — Portfolio-level aggregates
- **RebalanceTrade** — Trade details (side, shares, tax impact)
- **RebalancePlan** — Complete trade plan with costs and tax estimates
- **ScheduleState** — Next rebalance date, days until next, threshold status

## Database Tables
- `drift_snapshots` — Date-based drift history (migration 027)
- `rebalance_plans` — Generated plans with status (migration 027)
- `rebalance_trades` — Individual trade records (migration 027)
- `rebalance_schedules` — Scheduler config and history (migration 027)
- `rebalance_performance_log` — Pre/post rebalance performance comparison (migration 092)
- `drift_alert_history` — Drift threshold breach alerts (migration 092)

## Dashboard
Streamlit dashboard (`app/pages/rebalancing.py`) for drift monitoring, trade planning, and execution.

## Test Coverage
54 tests in `tests/test_rebalancing.py` covering config (12), models (11), DriftMonitor (8), RebalancePlanner (9), RebalanceScheduler (9), integration (3), module imports (2).
