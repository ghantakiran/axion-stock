# PRD-53: Credit Risk Analysis

## Overview
Credit risk analysis module for spread modeling, default probability
estimation, credit rating migration tracking, and debt structure analysis.

## Components

### 1. Credit Spread Analyzer (`spreads.py`)
- Spread tracking (OAS, Z-spread, ASW)
- Z-score and percentile ranking
- Spread trend detection (widening/tightening)
- Term structure analysis by maturity
- Cross-issuer relative value comparison

### 2. Default Probability Estimator (`default.py`)
- Merton structural model (distance-to-default, N(-DD))
- CDS-implied default probability
- Statistical model (Altman Z-score variant)
- Multi-horizon PD (1Y, 5Y)

### 3. Credit Rating Tracker (`rating.py`)
- Rating history tracking with outlook
- Migration direction detection (upgrade/downgrade)
- Transition probability matrix estimation
- Rating momentum scoring
- Negative outlook watchlist

### 4. Debt Structure Analyzer (`structure.py`)
- Leverage ratio computation (debt/equity, debt/EBITDA)
- Interest coverage ratio
- Maturity profile / maturity wall analysis
- Refinancing risk scoring
- Composite credit health score

## Data Models
- CreditSpread: point-in-time spread with z-score
- SpreadSummary: aggregated spread analysis
- DefaultProbability: PD with model attribution
- RatingSnapshot: rating at a point in time
- RatingTransition: from/to rating with probability
- DebtStructure: comprehensive debt analysis

## Technical Details
- In-memory storage pattern
- NumPy/SciPy for Merton model (normal CDF)
- Dataclass-based models
- Configurable via dataclass configs
