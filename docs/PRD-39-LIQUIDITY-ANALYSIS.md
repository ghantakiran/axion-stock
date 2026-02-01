# PRD-39: Liquidity Analysis

## Overview
Comprehensive liquidity analysis system providing bid-ask spread analysis,
volume profiling, market impact estimation, slippage prediction, and
composite liquidity scoring for informed position sizing.

## Components

### 1. Liquidity Engine (`src/liquidity/engine.py`)
- **Spread analysis**: Average, median, and effective spread computation
- **Volume analysis**: Avg/median volume, volume ratios, VWAP
- **Intraday profile**: Hourly volume distribution (U-shape detection)
- **Relative spread**: Spread as fraction of mid-price

### 2. Market Impact Estimator (`src/liquidity/impact.py`)
- **Linear model**: Impact = k * (size / avg_volume) * volatility
- **Square-root model**: Impact = k * sqrt(size / avg_volume) * volatility
- **Total cost**: Spread cost + impact cost
- **Max safe size**: Largest order within participation constraint
- **Execution horizon**: Optimal days to execute large orders

### 3. Liquidity Scorer (`src/liquidity/scoring.py`)
- **Composite score**: Weighted blend of spread, volume, and impact sub-scores (0-100)
- **Level classification**: VERY_HIGH / HIGH / MEDIUM / LOW / VERY_LOW
- **Universe ranking**: Sort assets by liquidity score
- **Size recommendation**: Max safe position given liquidity constraints

## Data Models
- `SpreadAnalysis` — Spread statistics for a symbol
- `VolumeAnalysis` — Volume statistics and VWAP
- `MarketImpact` — Impact/slippage estimate for a given trade size
- `LiquidityScore` — Composite score with sub-components
- `LiquiditySnapshot` — Point-in-time liquidity assessment

## Database Tables (Migration 025)
- `spread_analyses` — Historical spread computations
- `volume_analyses` — Volume statistics history
- `market_impacts` — Impact estimations
- `liquidity_scores` — Composite scores over time

## Configuration
- `LiquidityLevel` enum: VERY_HIGH, HIGH, MEDIUM, LOW, VERY_LOW
- `ImpactModel` enum: LINEAR, SQUARE_ROOT
- Configurable windows, participation rates, scoring weights, thresholds

## Dashboard (`app/pages/liquidity.py`)
4-tab layout: Overview | Spread | Impact | Scoring
