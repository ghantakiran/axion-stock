# PRD-55: Market Regime Detection

## Overview
ML-based market regime detection using Hidden Markov Models and clustering
to classify market states (bull, bear, sideways, crisis), estimate regime
transition probabilities, and drive regime-aware portfolio allocation.

## New Components

### 1. HMM Regime Detector (`hmm.py`)
- Gaussian HMM fitting on returns + volatility features
- Regime classification (bull, bear, sideways, crisis)
- Current regime identification with confidence
- Regime duration and persistence statistics
- Smoothed regime probabilities over time

### 2. Clustering Regime Classifier (`clustering.py`)
- Feature engineering (return, volatility, skewness, correlation)
- K-Means / agglomerative clustering on feature windows
- Regime labeling based on cluster characteristics
- Silhouette-based optimal cluster count
- Regime similarity scoring

### 3. Regime Transition Analyzer (`transitions.py`)
- Empirical transition matrix from regime history
- Expected regime duration per state
- Transition probability forecasting
- Regime change detection (breakpoint analysis)
- Conditional statistics per regime

### 4. Regime-Aware Allocator (`allocation.py`)
- Per-regime target allocations
- Regime-conditional return/risk estimates
- Blended allocation using regime probabilities
- Allocation shift recommendations on regime change
- Regime-filtered signal generation

## Data Models
- RegimeState: current regime with confidence
- RegimeHistory: time series of regime classifications
- TransitionMatrix: regime transition probabilities
- RegimeAllocation: regime-conditional portfolio weights

## Technical Details
- New src/regime/ module
- NumPy/SciPy for HMM and clustering (no hmmlearn dependency)
- Dataclass-based models
- Integration with existing risk and portfolio modules
