# PRD-94: Earnings Intelligence

## Overview
Earnings intelligence system with calendar management, analyst estimate tracking, historical analysis, earnings quality assessment (Beneish M-Score), price reaction analysis, ML-based surprise prediction, earnings call NLP, and alert management.

## Components

### 1. Earnings Calendar (`src/earnings/calendar.py`)
- **EarningsCalendar** — Event management with symbol/date/time filtering
- Add/retrieve events, next event lookup, upcoming events, day view
- Sample data generation for testing

### 2. Estimate Tracker (`src/earnings/estimates.py`)
- **EstimateTracker** — Analyst consensus, EPS/revenue estimates
- Revision tracking, spread calculation, YoY comparisons
- Revision trend analysis (up/down/flat)

### 3. History Analyzer (`src/earnings/history.py`)
- **HistoryAnalyzer** — Beat rates, surprise patterns, seasonal trends
- Quarterly data aggregation, consecutive beat/miss tracking
- Sector comparison capabilities

### 4. Quality Analyzer (`src/earnings/quality.py`)
- **QualityAnalyzer** — Beneish M-Score, accruals analysis, cash conversion
- 8 M-Score components (DSRI, GMI, AQI, SGI, DEPI, SGAI, TATA, LVGI)
- Quality ratings: HIGH, MEDIUM, LOW, WARNING
- Red flag detection, accruals warning threshold (10%)

### 5. Reaction Analyzer (`src/earnings/reactions.py`)
- **ReactionAnalyzer** — Gap analysis, post-earnings drift (PEAD)
- Pre/post-earnings price metrics, fade analysis
- Drift calculation and historical reaction patterns

### 6. Alert Manager (`src/earnings/alerts.py`)
- **EarningsAlertManager** — 5 alert types
- UPCOMING, RELEASED, SURPRISE, REVISION, GUIDANCE
- Notification generation, filtered alert retrieval

### 7. ML Prediction (`src/ml/models/earnings.py`)
- **EarningsPredictionModel** — XGBoost beat/miss classifier
- Feature engineering: beat lags, revision momentum, dispersion

### 8. Earnings Call NLP (`src/sentiment/earnings.py`)
- **EarningsCallAnalyzer** — Management tone, confidence, guidance direction
- Fog index, forward-looking statements, uncertainty counts

### 9. Models (`src/earnings/models.py`)
- **EarningsEvent** — Event with estimates, actuals, surprise calculations
- **EarningsEstimate** — Analyst consensus with revision metrics
- **QuarterlyEarnings** — Historical quarterly data with prices
- **EarningsQuality** — Quality assessment with M-Score components
- **EarningsReaction** — Pre/post-earnings price metrics
- **EarningsAlert** — Alert with type, symbol, message

## Database Tables
- Earnings-related tables in earlier migrations (009, 046)
- `earnings_quality_scores` — Quality assessment history (migration 094)
- `earnings_reaction_history` — Price reaction tracking (migration 094)

## Dashboard
Streamlit dashboard (`app/pages/earnings.py`) with calendar view, estimates tracker, history analysis, quality metrics.

## Test Coverage
27 tests in `tests/test_earnings.py` covering EarningsEvent (4: surprise calculations, beat/miss), EarningsCalendar (6: CRUD, filtering, sampling), EstimateTracker (4: consensus, spread, revision), HistoryAnalyzer (2: aggregation, sampling), QualityAnalyzer (4: M-Score, accruals, cash conversion, ratings), ReactionAnalyzer (2: recording, retrieval), EarningsAlertManager (5: upcoming/released/surprise/revision alerts, filtering).
