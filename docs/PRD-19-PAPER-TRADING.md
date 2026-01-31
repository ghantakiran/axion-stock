# PRD-19: Paper Trading System

## Overview

Live paper trading engine with session management, simulated market data feeds,
strategy automation, real-time performance tracking, and session comparison. Wraps
the existing execution paper broker with session lifecycle, P&L attribution, and
comprehensive reporting.

---

## Components

### 1. Session Management
- Create, start, pause, resume, and stop paper trading sessions
- Session configuration (initial capital, symbols, strategy, data source)
- Session state machine: CREATED → RUNNING → PAUSED → COMPLETED
- Multiple concurrent sessions with independent portfolios
- Session snapshots at configurable intervals

### 2. Simulated Data Feed
- Simulated price feed with configurable volatility and drift
- Historical replay mode (replay past market data at accelerated speed)
- Random walk price generation for testing
- Price update callbacks for strategy triggers
- Multi-symbol concurrent feeds

### 3. Strategy Runner
- Automated strategy execution against data feed
- Signal generation and order routing to paper broker
- Rebalance scheduling (daily, weekly, monthly)
- Strategy parameter configuration
- Pre-trade risk check integration

### 4. Performance Tracker
- Real-time equity curve computation
- Daily/cumulative returns tracking
- Sharpe, Sortino, max drawdown, win rate
- Trade-by-trade P&L logging
- Benchmark comparison (vs SPY or custom)
- Session-level and trade-level metrics

### 5. Session Comparison
- Compare multiple sessions side-by-side
- Metrics comparison table
- Winner-by-metric identification
- Equity curve overlay

### 6. Database Tables
- `paper_sessions`: Session configurations and state
- `paper_trades`: Individual trade records per session
- `paper_snapshots`: Periodic portfolio snapshots
- `paper_session_metrics`: Final session performance metrics

### 7. Success Metrics
- Session start latency: <100ms
- Price feed update rate: 1Hz simulated, configurable
- Performance calculation: <500ms for full metrics
- Support 10+ concurrent sessions

---

*Priority: P1 | Phase: 10*
