# PRD-75: Advanced Order Type Templates

## Overview
Advanced order execution system with multiple order types (market, limit, stop, stop-limit, trailing stop, market-on-close), smart order routing (TWAP, adaptive limit), pre-trade validation, bracket orders, and order flow analysis.

## Components

### 1. Order Models (`src/execution/models.py`)
- **OrderRequest** — Order placement with bracket (take_profit/stop_loss), trailing stop (trail_percent/trail_price), metadata (trigger, notes)
- **Order** — Full order lifecycle with status, fill details, timestamps, commission, slippage
- **OrderType** — MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP, MARKET_ON_CLOSE
- **OrderSide** — BUY, SELL
- **OrderStatus** — PENDING, SUBMITTED, ACCEPTED, PARTIAL_FILL, FILLED, CANCELLED, REJECTED, EXPIRED, FAILED
- **OrderTimeInForce** — DAY, GTC, IOC, FOK, OPG, CLS
- **Position** — Current position with market value, cost basis, unrealized P&L
- **AccountInfo** — Buying power, cash, equity, margin, PDT tracking
- **Trade** — Completed trade record with factor scores, regime context
- **ExecutionResult** — Execution outcome with slippage (bps), commission, timing

### 2. Pre-Trade Validator (`src/execution/order_manager.py`)
- **PreTradeValidator** — 9-point validation:
  1. Buying power sufficiency
  2. Position availability for sells
  3. Position concentration limits (default 25%)
  4. Sector concentration limits (default 40%)
  5. PDT rule compliance (<$25k accounts)
  6. Duplicate order detection (60s window)
  7. Rate limiting (10 orders/min)
  8. Market hours awareness
  9. Minimum position value ($500)
- **ValidationConfig** — Configurable limits and thresholds

### 3. Smart Order Router (`src/execution/order_manager.py`)
- **SmartOrderRouter** — Intelligent execution routing:
  - TWAP execution for large orders (>1% ADV), 5 slices, 30s intervals
  - Adaptive limit pricing (market orders → aggressive limits with 10bps buffer)
  - Direct execution for standard limit orders
  - ADV-based participation rate detection

### 4. Order Manager (`src/execution/order_manager.py`)
- **OrderManager** — High-level orchestration combining validation + routing
  - submit_order() with optional validation skip and smart routing
  - cancel_order() / cancel_all_orders()
  - get_order_status()

### 5. Order Flow Analysis (`src/execution/orderflow.py`)
- **ImbalanceAnalyzer** — Bid/ask volume imbalance with rolling analysis, signal generation
- **BlockDetector** — Block trade detection (medium/large/institutional), smart money signals
- **PressureAnalyzer** — Buy/sell pressure ratio, cumulative delta, smoothed ratio, series computation

### 6. ORM Models (`src/db/models.py`)
- **TradeOrder** — Order history with all execution fields
- **TradeExecution** — Individual execution records
- **OrderTypeEnum** — MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP
- **OrderSideType** — BUY, SELL
- **OrderStatusType** — PENDING through EXPIRED (8 statuses)

## Database Tables
- `trade_orders` — Order history with limit/stop prices, status tracking (migration 005)
- `trade_executions` — Individual fill records with price, quantity, venue (migration 005)
- `portfolio_snapshots` — Daily portfolio state snapshots (migration 005)

## Dashboard
- `app/pages/execution.py` — Execution monitoring interface
- `app/pages/paper_trading.py` — Paper trading order interface
- `app/pages/orderflow.py` — Order flow analysis (imbalance, blocks, pressure)

## Test Coverage
50 tests in `tests/test_orderflow.py` covering imbalance analysis (buy/sell/neutral signals, rolling, history, reset), block detection (classify medium/large/institutional, smart money signals), pressure analysis (buy/sell/neutral pressure, cumulative delta, series, smoothing), integration pipeline, and module imports.
