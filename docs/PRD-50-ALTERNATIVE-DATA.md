# PRD-50: Alternative Data Integration

## Overview
Alternative data integration system providing satellite imagery signal analysis,
web traffic analytics, social sentiment aggregation, and composite alternative
data scoring for alpha generation.

## Components

### 1. Satellite Signal Analyzer (`satellite.py`)
- Parking lot traffic, oil storage, shipping, and construction signals
- Z-score normalization against historical baselines
- Anomaly detection with configurable thresholds
- Trend computation via linear regression slope

### 2. Web Traffic Analyzer (`webtraffic.py`)
- Visit counts, unique visitors, bounce rate, session duration
- Growth rate computation over configurable lookback windows
- Engagement scoring (inverse bounce rate + duration)
- Traffic momentum detection

### 3. Social Sentiment Aggregator (`social.py`)
- Multi-source: Reddit, Twitter/X, StockTwits, news
- Mention counting with volume spike detection
- Sentiment scoring (bullish/bearish ratio)
- Cross-source aggregation with configurable weights

### 4. Alternative Data Scorer (`scoring.py`)
- Per-source signal scoring (satellite, web, social, app)
- Signal quality assessment (HIGH/MEDIUM/LOW/NOISE)
- Weighted composite scoring across all data sources
- Confidence estimation based on data coverage and quality

## Data Models
- `SatelliteSignal` — Normalized satellite observation with z-score
- `WebTrafficSnapshot` — Point-in-time web traffic metrics
- `SocialMention` — Individual social media mention record
- `SocialSentiment` — Aggregated sentiment for symbol/source
- `AltDataSignal` — Single-source scored signal
- `AltDataComposite` — Multi-source composite score

## Configuration
- `SatelliteConfig` — Anomaly threshold, min observations, lookback
- `WebTrafficConfig` — Growth window, engagement weights
- `SocialConfig` — Source weights, spike threshold, min mentions
- `ScoringConfig` — Source weights, quality thresholds, min sources
- `AltDataConfig` — Top-level config aggregating all sub-configs

## Database Tables
- `satellite_signals` — Satellite observation records
- `web_traffic_snapshots` — Web traffic snapshots
- `social_mentions` — Social media mentions
- `alt_data_composites` — Composite alternative data scores

## Dependencies
- numpy for statistical computation
- Existing project infrastructure (Alembic, Streamlit)
