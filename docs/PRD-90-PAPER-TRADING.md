# PRD-90: Paper Trading

## Overview
Paper trading simulator with virtual portfolio tracking, realistic order execution with slippage/commission modeling, session lifecycle management, market data feeds, performance benchmarking, and session comparison.

## Components

### 1. Session Manager (`src/paper_trading/session.py`)
- **SessionManager** — Full session lifecycle and order execution
- Create/start/pause/resume/complete/cancel sessions
- Buy/sell order execution with slippage and commission simulation
- Equal-weight rebalancing with threshold triggers
- Snapshot recording, metrics computation
- Multi-session management, session deletion

### 2. Data Feed (`src/paper_trading/data_feed.py`)
- **DataFeed** — Market data simulation
- Simulated feed (geometric Brownian motion with configurable drift/vol)
- Historical replay from real price data
- Random walk (zero drift)
- Price history tracking, feed reset

### 3. Performance Tracker (`src/paper_trading/performance.py`)
- **PerformanceTracker** — Real-time performance metrics
- Sharpe ratio, Sortino ratio, Calmar ratio
- Max drawdown with duration tracking
- Win rate, profit factor, average win/loss
- Session comparison and ranking

### 4. Paper Broker (`src/execution/paper_broker.py`, `src/execution/brokers/paper.py`)
- **PaperBroker** — Realistic broker simulation
- Market, limit, and stop order execution
- Slippage modeling (10bps per 1% ADV)
- Commission and bid-ask spread simulation
- Margin tracking (1-4x multiplier), day trading counter

### 5. Configuration (`src/paper_trading/config.py`)
- SessionStatus (CREATED/RUNNING/PAUSED/COMPLETED/CANCELLED)
- DataFeedType (SIMULATED/HISTORICAL/RANDOM_WALK)
- RebalanceSchedule, StrategyType
- SessionConfig, DataFeedConfig, StrategyConfig

### 6. Models (`src/paper_trading/models.py`)
- **PaperSession** — Session with lifecycle states, cash/equity/drawdown tracking
- **SessionTrade** — Individual trades with PnL, slippage, commission
- **PortfolioPosition** — Symbol holdings with unrealized PnL
- **SessionSnapshot** — Point-in-time portfolio state
- **SessionMetrics** — 30+ performance metrics

## Database Tables
- `paper_sessions` — Session configs and state (migration 020)
- `paper_trades` — Individual trade records (migration 020)
- `paper_snapshots` — Portfolio snapshots (migration 020)
- `paper_session_metrics` — Computed metrics (migration 020)
- `paper_leaderboard` — Session rankings and comparison (migration 090)
- `paper_strategy_log` — Strategy parameter change tracking (migration 090)

## Dashboard
Streamlit dashboard (`app/pages/trading.py`) for paper and live trading.

## Test Coverage
39 tests in `tests/test_paper_trading.py` covering config (7), models (7), DataFeed (7), PerformanceTracker (4), SessionManager (12: lifecycle, buy/sell, insufficient funds, feed advance, snapshots, rebalance, metrics), full workflow (1), module imports (1).
