# PRD-146: Smart Multi-Broker Execution

## Overview
Unified routing layer that aggregates all connected brokers (Alpaca, Robinhood, Coinbase, Schwab) and routes orders intelligently based on cost, speed, asset support, and availability. Provides automatic failover, portfolio aggregation, and a single pane of glass for multi-broker trading.

## Background
The Axion platform now supports 4 broker integrations (PRD-139 Alpaca, PRD-143 Robinhood, PRD-144 Coinbase, PRD-145 Schwab). PRD-146 creates a unified layer on top that allows the platform to route orders to the best broker automatically and provides a consolidated portfolio view across all accounts.

## Goals
1. **Broker Registry** -- Central registry for all broker connections with status tracking
2. **Intelligent Routing** -- Score brokers on cost (40%), speed (30%), fill quality (30%) with smart defaults
3. **Portfolio Aggregation** -- Merge positions across all brokers into a unified view
4. **Failover Execution** -- Automatic fallback chain when the primary broker fails
5. **Rate Limit Awareness** -- Track per-broker request counts to avoid throttling

## Module Structure

### `src/multi_broker/`
| File | Description | ~Lines |
|------|-------------|--------|
| `__init__.py` | Public exports | ~70 |
| `registry.py` | BrokerAdapter protocol, BrokerInfo, BrokerRegistry | ~250 |
| `router.py` | RoutingRule, RouteDecision, OrderRouter | ~280 |
| `aggregator.py` | AggregatedPosition, AggregatedPortfolio, PortfolioAggregator | ~250 |
| `executor.py` | ExecutionResult, MultiBrokerExecutor with failover | ~200 |

### Supporting Files
| File | Description |
|------|-------------|
| `tests/test_multi_broker.py` | 8 test classes, ~50 tests |
| `app/pages/multi_broker.py` | 4-tab Streamlit dashboard |
| `alembic/versions/146_multi_broker.py` | Migration (multi_broker_connections, multi_broker_routes) |
| `src/db/models.py` | MultiBrokerConnectionRecord, MultiBrokerRouteRecord ORM models |

## API Design

### BrokerAdapter Protocol
- `connect()`, `disconnect()`, `is_connected`, `get_account()`, `get_positions()`
- `place_order(order)`, `cancel_order(order_id)`, `get_quote(symbol)`
- `supported_assets` property

### BrokerRegistry
- `register(name, adapter)` -- Register a broker with optional overrides
- `unregister(name)` -- Remove a broker
- `get_connected()` -- All connected brokers
- `get_by_asset(asset_type)` -- Brokers supporting an asset type
- `get_best_for(asset_type, criteria)` -- Best broker for an asset
- `status_summary()` -- Overview of all broker statuses

### OrderRouter
- `route(order) -> RouteDecision` -- Route a single order
- `route_batch(orders)` -- Route multiple orders
- `add_rule(RoutingRule)` -- Add user-defined routing rule
- Smart defaults: crypto -> Coinbase, stocks -> Alpaca, options -> Schwab, fractional -> Robinhood

### PortfolioAggregator
- `sync_all()` -- Fetch account/position data from all brokers
- `get_unified_portfolio()` -- Merged portfolio view
- `get_cross_broker_exposure(symbol)` -- Per-symbol cross-broker breakdown
- `get_broker_allocation()` -- Allocation percentages

### MultiBrokerExecutor
- `execute(order)` -- Execute with automatic failover
- `execute_batch(orders)` -- Batch execution
- Rate limit awareness per broker

## Database Schema

### multi_broker_connections (10 columns)
Tracks broker connection state, asset types, fee schedule, priority, and sync timestamps.

### multi_broker_routes (12 columns)
Immutable log of all routing decisions including broker selection, scoring, fees, and failover.

## Dashboard
4-tab Streamlit interface:
1. **Broker Status** -- Connection table, latency chart, asset coverage
2. **Unified Portfolio** -- Aggregated positions, allocation, P&L
3. **Order Routing** -- Route preview, execution, recent routes
4. **Configuration** -- Rules editor, priority ordering, fee schedules, scoring weights

## Scoring Algorithm
Brokers are scored with configurable weights (default: cost 40%, speed 30%, fill quality 30%):
```
score = w_cost * (1 - normalized_fee) + w_speed * (1 - normalized_latency) + w_fill * fill_score
```

## Testing
- 8 test classes, ~50 tests
- All tests run in demo mode with mock adapters
- pytest-asyncio for async test support
