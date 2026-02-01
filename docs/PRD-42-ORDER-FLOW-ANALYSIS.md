# PRD-42: Order Flow Analysis

## Overview
Order flow analysis system providing order book imbalance detection,
large block trade identification, buy/sell pressure measurement,
cumulative delta tracking, and smart money signal generation.

## Components

### 1. Imbalance Analyzer (`src/orderflow/imbalance.py`)
- **Book imbalance**: Bid vs ask volume ratio at best levels
- **Imbalance classification**: Bid-heavy, ask-heavy, balanced
- **Rolling imbalance**: Smoothed imbalance over configurable window
- **Imbalance signals**: Threshold-based buy/sell signals

### 2. Block Detector (`src/orderflow/blocks.py`)
- **Block detection**: Identify trades above size thresholds
- **Size classification**: Small, medium, large, institutional
- **Institutional flow**: Aggregate large/institutional block direction
- **Block ratio**: Fraction of volume from large trades

### 3. Pressure Analyzer (`src/orderflow/pressure.py`)
- **Buy/sell pressure**: Volume-weighted directional pressure
- **Net flow**: Buy volume minus sell volume
- **Cumulative delta**: Running sum of net flow
- **Pressure ratio**: Buy/sell volume ratio with smoothing

## Database Tables (Migration 028)
- `orderbook_snapshots` — Order book imbalance history
- `block_trades` — Detected large block trades
- `flow_pressure` — Buy/sell pressure measurements
- `smart_money_signals` — Smart money signal history

## Dashboard (`app/pages/orderflow.py`)
4-tab layout: Imbalance | Blocks | Pressure | Smart Money
