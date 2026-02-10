# PRD-175: Live Bot Analytics

## Overview

Provides real-time performance analytics for the running trading bot. Tracks rolling equity curves, per-signal and per-strategy breakdowns, and standard risk-adjusted return metrics. Produces periodic `PerformanceSnapshot` records for historical analysis.

## Architecture

- **Module**: `src/bot_analytics/`
- **Source files**: `__init__.py`, `tracker.py`, `metrics.py`, `snapshot.py`
- **Dependencies**: BotOrchestrator (PRD-170), TradeAttribution (PRD-160)

### Data Flow

```
Trade Closed (P&L)
  --> BotPerformanceTracker.record_trade(trade)
    --> update equity curve, per-signal/strategy breakdowns
    --> MetricsCalculator.compute(returns)
    --> PerformanceSnapshot (every N trades)
      --> BotPerformanceSnapshotRecord (DB)
```

## Key Components

### BotPerformanceTracker (`src/bot_analytics/tracker.py`)

Central analytics engine. Maintains rolling windows of returns and per-dimension breakdowns.

| Method | Description |
|--------|-------------|
| `record_trade(trade)` | Ingests a closed trade, updates all internal state |
| `get_snapshot()` | Returns current PerformanceSnapshot |
| `get_equity_curve(window)` | Returns rolling equity values for chart rendering |
| `get_signal_breakdown()` | P&L, count, win rate by signal type |
| `get_strategy_breakdown()` | P&L, count, win rate by strategy name |
| `reset()` | Clears all state (for new session) |

### MetricsCalculator (`src/bot_analytics/metrics.py`)

Stateless calculator for risk-adjusted return metrics.

| Metric | Formula | Description |
|--------|---------|-------------|
| `sharpe_ratio` | `mean(r) / std(r) * sqrt(252)` | Risk-adjusted return (annualized) |
| `sortino_ratio` | `mean(r) / downside_std(r) * sqrt(252)` | Downside-risk-adjusted return |
| `calmar_ratio` | `annualized_return / max_drawdown` | Return relative to worst drawdown |
| `max_drawdown` | `max(peak - trough) / peak` | Largest peak-to-trough decline |
| `win_rate` | `winning_trades / total_trades` | Percentage of profitable trades |
| `profit_factor` | `gross_profit / gross_loss` | Ratio of gains to losses |

### PerformanceSnapshot (`src/bot_analytics/snapshot.py`)

```python
@dataclass(frozen=True)
class PerformanceSnapshot:
    timestamp: datetime
    trade_count: int
    current_equity: float
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    signal_breakdown: dict[str, dict]    # {signal_type: {pnl, count, win_rate}}
    strategy_breakdown: dict[str, dict]  # {strategy: {pnl, count, win_rate}}
```

## API / Interface

```python
tracker = BotPerformanceTracker(initial_equity=100_000.0, snapshot_interval=50)
tracker.record_trade(trade)
snapshot = tracker.get_snapshot()
print(f"Sharpe: {snapshot.sharpe_ratio:.2f}, Drawdown: {snapshot.max_drawdown:.2%}")
```

## Database Schema

### bot_performance_snapshots

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| snapshot_time | DateTime | When snapshot was captured |
| trade_count | Integer | Total trades at snapshot time |
| current_equity | Float | Portfolio equity value |
| sharpe_ratio | Float | Annualized Sharpe ratio |
| sortino_ratio | Float | Annualized Sortino ratio |
| calmar_ratio | Float | Calmar ratio |
| max_drawdown | Float | Maximum drawdown (0-1) |
| win_rate | Float | Win rate (0-1) |
| profit_factor | Float | Gross profit / gross loss |
| breakdown_json | Text | Signal and strategy breakdowns |
| created_at | DateTime | Record creation time |

### bot_trade_metrics

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| trade_id | VARCHAR(50) | Unique trade identifier |
| ticker | VARCHAR(20) | Symbol traded |
| signal_type | VARCHAR(30) | Signal that generated the trade |
| strategy | VARCHAR(30) | Strategy that approved the trade |
| pnl | Float | Realized P&L |
| return_pct | Float | Return percentage |
| hold_duration_seconds | Integer | How long position was held |
| created_at | DateTime | Trade close timestamp |

**ORM Models:** `BotPerformanceSnapshotRecord`, `BotTradeMetricRecord` in `src/db/models.py`

## Migration

- **Revision**: 175
- **Down revision**: 174
- **Chain**: `...173 -> 174 -> 175`
- **File**: `alembic/versions/175_bot_analytics.py`
- Creates `bot_performance_snapshots` and `bot_trade_metrics` tables
- Indexes on `snapshot_time`, `trade_id`, `signal_type`, and `created_at`

## Dashboard

4-tab Streamlit page at `app/pages/bot_analytics.py`:

| Tab | Contents |
|-----|----------|
| Equity Curve | Rolling equity chart, drawdown overlay, return distribution |
| Risk Metrics | Sharpe/Sortino/Calmar gauges, rolling metric charts |
| Signal Attribution | Per-signal P&L bar chart, win rate table |
| Strategy Performance | Per-strategy comparison table, equity curves by strategy |

## Testing

~52 tests in `tests/test_bot_analytics.py`:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestBotPerformanceTracker` | ~16 | Trade recording, equity updates, rolling window |
| `TestMetricsCalculator` | ~14 | All metrics, edge cases (no trades, all wins, all losses) |
| `TestPerformanceSnapshot` | ~8 | Immutability, serialization, breakdown structure |
| `TestSignalBreakdown` | ~8 | Per-signal aggregation, multi-type trades |
| `TestStrategyBreakdown` | ~6 | Per-strategy aggregation, strategy switching |

## Dependencies

| Module | Usage |
|--------|-------|
| PRD-170 BotOrchestrator | Trade close events feed tracker |
| PRD-160 TradeAttribution | Signal-to-trade linking for attribution |
| PRD-173 StrategyBridge | Strategy name tagging on trades |
| PRD-166 SignalFeedback | Shares rolling performance data |
