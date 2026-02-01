# PRD-43: Options Chain Analysis

## Overview
Comprehensive options analysis module providing Greeks computation via Black-Scholes,
options chain analytics (put-call ratio, max pain, IV skew), and options flow
detection (unusual activity, sweep/block classification, net premium sentiment).

## Components

### 1. Greeks Calculator (`src/options/greeks.py`)
- **Black-Scholes pricing**: European call/put valuation
- **Delta**: Rate of change vs underlying price
- **Gamma**: Rate of change of delta
- **Theta**: Time decay per day
- **Vega**: Sensitivity to volatility (per 1% move)
- **Rho**: Sensitivity to interest rate
- **Implied Volatility**: Newton-Raphson solver from market price

### 2. Chain Analyzer (`src/options/chain.py`)
- **Put-Call Ratio**: Volume-based and open-interest-based
- **Max Pain**: Strike price causing maximum loss for option writers
- **IV Skew**: Volatility smile/skew across strikes
- **Chain Summary**: Aggregate volume, OI, and directional metrics

### 3. Flow Detector (`src/options/flow.py`)
- **Unusual Activity**: Volume/OI ratio spike detection
- **Flow Classification**: Sweep, block, split, normal
- **Net Premium Sentiment**: Dollar-weighted directional bias
- **Activity Scoring**: Multi-factor unusual activity level

## Data Models
- `OptionGreeks`: All Greeks + implied vol for a single contract
- `OptionContract`: Strike, expiry, type, bid/ask, volume, OI, greeks
- `ChainSummary`: Aggregate chain metrics (PCR, max pain, skew)
- `OptionsFlow`: Classified flow event with dollar value and sentiment
- `UnusualActivity`: Flagged unusual options activity with scoring

## Configuration
- `GreeksConfig`: Risk-free rate, dividend yield, IV solver params
- `ChainConfig`: Min volume/OI filters, skew calculation params
- `FlowConfig`: Unusual activity thresholds, sweep detection params

## Database Tables
- `options_greeks`: Computed Greeks snapshots
- `options_chain_snapshots`: Chain-level summary metrics
- `options_flow`: Detected flow events
- `options_unusual_activity`: Flagged unusual activity

## Dashboard
4-tab Streamlit page: Greeks, Chain Analysis, Flow, Unusual Activity
