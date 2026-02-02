# PRD-46: Fund Flow Analysis

## Overview
Fund flow analysis module for tracking ETF/mutual fund flows, institutional
positioning, sector rotation detection, and smart money signal generation.

## Components

### 1. Flow Tracker (`src/fundflow/tracker.py`)
- Daily/weekly fund flow aggregation
- Net flow computation (inflows - outflows)
- Flow momentum (rate of change)
- Cumulative flow tracking
- Flow-to-AUM ratio normalization

### 2. Institutional Analyzer (`src/fundflow/institutional.py`)
- 13F filing position tracking
- Institutional ownership concentration
- Quarter-over-quarter position changes
- Top holder analysis
- Ownership momentum signals

### 3. Rotation Detector (`src/fundflow/rotation.py`)
- Sector-level flow aggregation
- Relative flow strength ranking
- Rotation momentum scoring
- Regime-based rotation patterns
- Cross-sector flow divergence

### 4. Smart Money Detector (`src/fundflow/smartmoney.py`)
- Smart money flow indicator (institutional vs retail)
- Conviction scoring from position sizing
- Contrarian signal detection
- Flow-price divergence alerts
- Accumulation/distribution classification

## Database Tables
- `fund_flows` — Daily fund flow records
- `institutional_positions` — 13F position snapshots
- `sector_rotations` — Sector rotation scores
- `smart_money_signals` — Smart money signal records

## Dashboard
4-tab layout: Fund Flows | Institutional | Sector Rotation | Smart Money
