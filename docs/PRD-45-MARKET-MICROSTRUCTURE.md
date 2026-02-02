# PRD-45: Market Microstructure

## Overview
Market microstructure analysis module providing bid-ask spread analytics,
order book imbalance detection, tick-level trade metrics, and price impact
estimation for informed trading decisions.

## Components

### 1. Spread Analyzer (`src/microstructure/spread.py`)
- Quoted spread, effective spread, realized spread
- Spread decomposition (adverse selection vs inventory)
- Roll's implied spread estimator
- Time-weighted and volume-weighted spread metrics

### 2. Order Book Analyzer (`src/microstructure/orderbook.py`)
- Bid-ask imbalance ratio
- Order book depth at multiple levels
- Book pressure and slope metrics
- Resilience measurement (recovery after trades)

### 3. Tick Analyzer (`src/microstructure/tick.py`)
- Trade classification (Lee-Ready algorithm)
- VWAP and TWAP computation
- Tick-to-trade ratio
- Trade size distribution analysis
- Kyle's lambda (price impact coefficient)

### 4. Impact Estimator (`src/microstructure/impact.py`)
- Temporary vs permanent price impact
- Square-root impact model
- Almgren-Chriss optimal execution framework
- Market impact cost estimation

## Database Tables
- `spread_snapshots_ms` — Spread metric snapshots
- `orderbook_snapshots` — Order book state snapshots
- `tick_metrics` — Tick-level aggregated metrics
- `impact_estimates` — Price impact estimates

## Dashboard
4-tab layout: Spread Analysis | Order Book | Tick Metrics | Price Impact
