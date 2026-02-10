# PRD-176: Adaptive Feedback Loop

## Overview

Closes the feedback loop between live trading performance and signal source weighting. A `WeightStore` persists weight history for audit, and a `FeedbackBridge` triggers automatic weight adjustments every N trades, feeding updated weights into `FusionBridge` (PRD-173).

## Architecture

- **Modules**: `src/signal_feedback/`, `src/bot_pipeline/`
- **Source files**: `src/signal_feedback/weight_store.py`, `src/bot_pipeline/feedback_bridge.py`
- **Dependencies**: SignalFeedback (PRD-166), FusionBridge (PRD-173), BotPerformanceTracker (PRD-175)

### Complete Feedback Cycle

```
Trade Closed
  --> BotPerformanceTracker.record_trade() (PRD-175)
  --> FeedbackBridge.on_trade(trade)
    --> trade_count % adjustment_interval == 0?
      --> WeightAdjuster.compute_weights() (PRD-166)
      --> WeightStore.save(new_weights, context)
      --> FusionBridge.update_weights(new_weights) (PRD-173)
```

## Key Components

### WeightStore (`src/signal_feedback/weight_store.py`)

Persists signal source weights with full history for audit and rollback.

| Method | Description |
|--------|-------------|
| `save(weights, context)` | Persists weight snapshot with performance context |
| `load_latest()` | Returns most recent weight map |
| `load_history(n)` | Returns last N weight snapshots |
| `rollback(snapshot_id)` | Restores weights from a previous snapshot |

**Storage Format:**

```python
@dataclass
class WeightSnapshot:
    snapshot_id: str
    timestamp: datetime
    weights: dict[str, float]           # {source_name: weight}
    sharpe_ratios: dict[str, float]     # {source_name: rolling_sharpe}
    trade_count_at_snapshot: int
    trigger: str                         # "scheduled", "manual", "rollback"
```

### FeedbackBridge (`src/bot_pipeline/feedback_bridge.py`)

Orchestrates the feedback cycle: counts trades, triggers weight recalculation, persists results, and pushes to fusion.

| Method | Description |
|--------|-------------|
| `on_trade(trade)` | Increments counter, triggers adjustment if interval reached |
| `force_adjustment()` | Manually triggers weight recalculation |
| `get_current_weights()` | Returns active weight map |
| `set_interval(n)` | Changes adjustment interval |

**Configuration:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `adjustment_interval` | `25` | Trades between weight recalculations |
| `min_trades_per_source` | `5` | Minimum trades before source gets adjusted |
| `max_weight_change` | `0.15` | Maximum single-step weight change (dampening) |
| `weight_floor` | `0.05` | Minimum weight for any source |
| `weight_ceiling` | `0.50` | Maximum weight for any source |

**Dampening Logic:**

```python
def _dampen_weights(self, current: dict, proposed: dict) -> dict:
    dampened = {}
    for source, new_w in proposed.items():
        old_w = current.get(source, 0.2)
        delta = max(-self._max_weight_change, min(self._max_weight_change, new_w - old_w))
        dampened[source] = max(self._weight_floor, min(self._weight_ceiling, old_w + delta))
    total = sum(dampened.values())
    return {s: w / total for s, w in dampened.items()}
```

## API / Interface

```python
weight_store = WeightStore(state_dir=".bot_state")
feedback_bridge = FeedbackBridge(
    weight_adjuster=weight_adjuster, weight_store=weight_store,
    fusion_bridge=fusion_bridge, adjustment_interval=25
)
orchestrator.set_feedback_bridge(feedback_bridge)
```

## Database Schema

### signal_weight_history

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| snapshot_id | VARCHAR(50) | Unique snapshot identifier |
| source_name | VARCHAR(30) | Signal source name |
| weight | Float | Assigned weight (0-1) |
| previous_weight | Float | Weight before this adjustment |
| sharpe_ratio | Float | Rolling Sharpe at adjustment time |
| trade_count | Integer | Source trade count at snapshot |
| win_rate | Float | Source win rate at snapshot |
| trigger | VARCHAR(20) | scheduled, manual, rollback |
| created_at | DateTime | Snapshot timestamp |

**ORM Model:** `SignalWeightHistoryRecord` in `src/db/models.py`

## Migration

- **Revision**: 176
- **Down revision**: 175
- **Chain**: `...174 -> 175 -> 176`
- **File**: `alembic/versions/176_adaptive_feedback.py`
- Creates `signal_weight_history` table
- Indexes on `snapshot_id`, `source_name`, `trigger`, and `created_at`

## Dashboard

4-tab Streamlit page at `app/pages/adaptive_feedback.py`:

| Tab | Contents |
|-----|----------|
| Weight Timeline | Line chart of weight evolution per source over time |
| Adjustment Log | Table of all weight adjustments with trigger, context, delta |
| Source Performance | Per-source Sharpe, win rate, P&L driving the weight changes |
| Feedback Config | Interval, dampening, floor/ceiling settings with live editor |

## Testing

~42 tests in `tests/test_adaptive_feedback.py`:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestWeightStore` | ~14 | Save, load, rollback, history, atomic writes |
| `TestFeedbackBridge` | ~12 | Interval triggering, force adjustment, wiring |
| `TestWeightDampening` | ~8 | Max change, floor/ceiling, normalization |
| `TestFullCycle` | ~8 | End-to-end: trade -> adjust -> fuse with new weights |

## Dependencies

| Module | Usage |
|--------|-------|
| PRD-166 WeightAdjuster | Computes Sharpe-proportional weights |
| PRD-173 FusionBridge | Receives updated weights for signal fusion |
| PRD-175 BotPerformanceTracker | Per-source rolling performance data |
| PRD-170 PersistentStateManager | Shares state directory for file persistence |
