# PRD-76: Institutional Dark Pool Access

## Overview
Dark pool analytics system with volume tracking, print analysis and classification, institutional block detection, liquidity estimation, and fill rate modeling across dark and lit venues.

## Components

### 1. Volume Tracker (`src/darkpool/volume.py`)
- **VolumeTracker** — Tracks dark pool vs lit volume with 20-day lookback
- Dark share percentage, elevated dark share detection
- Short volume ratio tracking

### 2. Print Analyzer (`src/darkpool/prints.py`)
- **PrintAnalyzer** — Classifies dark pool prints by type:
  - BLOCK (>=10,000 shares)
  - RETAIL (<=100 shares)
  - INSTITUTIONAL (>1,000 shares, >$50k notional)
  - MIDPOINT (within 10% of NBBO midpoint)
  - UNKNOWN
- Price improvement calculation from NBBO midpoint
- Print summary statistics with block percentage

### 3. Block Detector (`src/darkpool/blocks.py`)
- **BlockDetector** — Institutional block trade detection (>=10,000 shares minimum)
- Direction inference from NBBO (buy above mid, sell below)
- ADV ratio calculation for significance scoring
- Time-based clustering of related blocks
- Smart money signal generation from block patterns

### 4. Liquidity Estimator (`src/darkpool/liquidity.py`)
- **LiquidityEstimator** — Scores dark pool liquidity 0-1
- **LiquidityLevel** — DEEP (>0.7), MODERATE (>0.4), SHALLOW (>0.2), DRY
- Estimated depth calculation
- Fill rate modeling at various order sizes
- Dark/lit ratio analysis, print-enhanced scoring

### 5. Configuration (`src/darkpool/config.py`)
- **PrintType** — BLOCK, MIDPOINT, RETAIL, INSTITUTIONAL, UNKNOWN
- **BlockDirection** — BUY, SELL, UNKNOWN
- **LiquidityLevel** — DEEP, MODERATE, SHALLOW, DRY
- **VenueTier** — MAJOR, MID, MINOR
- Volume, print, block, and liquidity config defaults

### 6. Models (`src/darkpool/models.py`)
- **DarkPoolVolume** — Daily snapshot with dark/lit volumes, dark share %, short volume
- **DarkPrint** — Single trade with price improvement from midpoint
- **DarkBlock** — Block trade with ADV ratio, direction, notional value, significance flag
- **DarkLiquidity** — Liquidity score, level, estimated depth, fill rates by size
- **VolumeSummary** / **PrintSummary** — Aggregated analytics

## Database Tables
- `dark_pool_volume` — Daily dark/lit volumes with symbol/date indexes (migration 033)
- `dark_prints` — Individual dark pool prints with classification (migration 033)
- `dark_blocks` — Detected block trades with direction and significance (migration 033)
- `dark_liquidity` — Liquidity snapshots with scores and fill rates (migration 033)

## Dashboard
4-tab Streamlit dashboard (`app/pages/darkpool.py`):
1. **Volume Analysis** — Dark share %, trend over time, short volume ratio
2. **Print Analysis** — Print type distribution, average size, price improvement
3. **Block Detection** — Block count, direction, clusters, notional value
4. **Liquidity** — Score, level, estimated depth, fill rates at various sizes

## Test Coverage
52 tests in `tests/test_darkpool.py` covering config defaults, model properties/serialization, VolumeTracker (summary/elevated/short ratio/reset), PrintAnalyzer (classify block/retail/midpoint/institutional, analysis), BlockDetector (detection/direction/ADV ratio/filtering/clustering/summary), LiquidityEstimator (scoring/levels/fill rates/prints/consistency), integration pipeline, and module imports.
