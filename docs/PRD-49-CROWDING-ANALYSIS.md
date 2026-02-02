# PRD-49: Crowding Analysis

## Overview
Crowding analysis module for detecting position crowding, scoring hedge
fund overlap, analyzing short interest dynamics, and identifying
consensus divergence for contrarian signal generation.

## Components

### 1. Crowding Detector (`src/crowding/detector.py`)
- Position crowding score from ownership concentration
- Crowding intensity (rate of increase in shared positions)
- Crowding risk classification (low/medium/high/extreme)
- Historical crowding percentile ranking
- De-crowding alert detection

### 2. Overlap Analyzer (`src/crowding/overlap.py`)
- Hedge fund portfolio overlap scoring
- Pairwise fund similarity (Jaccard/cosine)
- Most-crowded names identification
- Ownership breadth vs depth analysis
- Overlap momentum (increasing/decreasing)

### 3. Short Interest Analyzer (`src/crowding/short_interest.py`)
- Short interest ratio (shares short / float)
- Days-to-cover computation
- Short interest momentum
- Short squeeze risk scoring
- Cost-to-borrow signal integration

### 4. Consensus Analyzer (`src/crowding/consensus.py`)
- Analyst consensus tracking
- Consensus divergence scoring
- Estimate revision momentum
- Contrarian opportunity detection
- Buy/sell/hold distribution analysis

## Database Tables
- `crowding_scores` — Position crowding snapshots
- `fund_overlaps` — Fund overlap scores
- `short_interest` — Short interest records
- `consensus_signals` — Consensus divergence signals

## Dashboard
4-tab layout: Crowding | Fund Overlap | Short Interest | Consensus
