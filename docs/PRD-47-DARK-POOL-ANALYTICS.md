# PRD-47: Dark Pool Analytics

## Overview
Dark pool analytics module for tracking off-exchange volume, analyzing
dark prints, detecting institutional block trades, and estimating
hidden liquidity for informed execution decisions.

## Components

### 1. Volume Tracker (`src/darkpool/volume.py`)
- Dark pool volume vs lit exchange volume
- Dark pool market share (% of total volume)
- Volume trend analysis and momentum
- Venue-level breakdown (ATS identification)
- Short sale volume in dark pools

### 2. Print Analyzer (`src/darkpool/prints.py`)
- Dark print classification (block, retail, midpoint, etc.)
- Print size distribution analysis
- Price improvement measurement
- Time-of-day patterns
- Print-to-NBBO distance analysis

### 3. Block Detector (`src/darkpool/blocks.py`)
- Institutional block trade identification
- Block frequency and clustering
- Block direction inference (buyer/seller initiated)
- Size-relative-to-ADV scoring
- Block impact analysis

### 4. Liquidity Estimator (`src/darkpool/liquidity.py`)
- Hidden liquidity estimation from dark activity
- Effective dark pool depth
- Liquidity score (accessibility metric)
- Fill rate estimation at various sizes
- Dark-lit liquidity ratio

## Database Tables
- `dark_pool_volume` — Daily dark pool volume records
- `dark_prints` — Individual dark print records
- `dark_blocks` — Detected block trades
- `dark_liquidity` — Liquidity estimation snapshots

## Dashboard
4-tab layout: Volume Analysis | Print Analysis | Block Detection | Liquidity
