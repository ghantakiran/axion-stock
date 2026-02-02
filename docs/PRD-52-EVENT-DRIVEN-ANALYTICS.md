# PRD-52: Event-Driven Analytics

## Overview
Event-driven analytics module for modeling earnings events, M&A probability
scoring, corporate action tracking, and generating event-driven trading signals.

## Components

### 1. Earnings Analyzer (`earnings.py`)
- Earnings surprise computation (EPS and revenue)
- Beat/meet/miss classification
- Post-earnings announcement drift (PEAD) estimation
- Historical pattern analysis (beat rate, avg surprise)
- Pre-earnings drift detection

### 2. Merger Analyzer (`mergers.py`)
- Deal spread computation (annualized)
- Completion probability estimation
- Risk arbitrage signal generation
- Deal status tracking
- Premium analysis

### 3. Corporate Action Tracker (`corporate.py`)
- Dividend tracking (yield, growth, ex-dates)
- Stock split detection and adjustment
- Buyback analysis (amount, float percentage)
- Upcoming event calendar
- Spinoff tracking

### 4. Event Signal Generator (`signals.py`)
- Earnings-based signals (surprise + drift)
- M&A-based signals (spread + probability)
- Corporate action signals
- Composite multi-event scoring
- Signal quality assessment

## Data Models
- EarningsEvent: earnings report with surprise metrics
- MergerEvent: M&A deal with spread and probability
- CorporateAction: dividend, split, buyback, spinoff
- EventSignal: scored event-driven signal

## Technical Details
- In-memory storage pattern
- NumPy for numerical computation
- Dataclass-based models
- Configurable thresholds via dataclass configs
