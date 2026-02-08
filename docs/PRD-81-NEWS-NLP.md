# PRD-81: News NLP & Sentiment Analysis

## Overview
Comprehensive financial NLP system with multi-source sentiment analysis, news aggregation, insider trading signals, analyst consensus tracking, earnings call NLP, and advanced sentiment fusion/momentum tracking.

## Components

### 1. News Sentiment Engine (`src/sentiment/news.py`)
- **NewsSentimentEngine** — FinBERT-based NLP with keyword fallback scoring
- Ticker extraction (cashtag `$AAPL` + common ticker recognition)
- Topic classification: earnings, M&A, regulatory, macro, product, management, dividend, guidance
- Time-decay weighted aggregation (recent articles weighted higher)
- Source credibility weighting (Reuters > Bloomberg > SeekingAlpha)

### 2. Social Media Monitor (`src/sentiment/social.py`)
- **SocialMediaMonitor** — Reddit/Twitter/StockTwits mention aggregation
- Trending detection (3x spike threshold), mention spike detection
- Engagement metrics (upvotes, comments), platform-specific aggregation

### 3. Insider Trading Tracker (`src/sentiment/insider.py`)
- **InsiderTracker** — SEC Form 4 analysis with insider title weighting
- Cluster buy detection (3+ insiders in 30 days), 10b5-1 plan detection
- CEO/CFO activity tracking, insider score calculation (-1 to +1)

### 4. Analyst Consensus (`src/sentiment/analyst.py`)
- **AnalystConsensusTracker** — Rating aggregation, price target statistics
- Estimate revision tracking, revision momentum/breadth, rating change detection

### 5. Earnings Call NLP (`src/sentiment/earnings.py`)
- **EarningsCallAnalyzer** — Management tone, Q&A sentiment, key topic extraction
- Forward-looking statement detection, uncertainty word counting
- Guidance direction (raised/maintained/lowered), Fog Index readability
- Quarter-over-quarter comparison

### 6. Composite Sentiment (`src/sentiment/composite.py`)
- **SentimentComposite** — Multi-source fusion with weighted averaging
- Default weights: news 0.25, analyst 0.20, insider 0.20, social 0.15, earnings 0.10, options 0.10
- Confidence levels, batch processing, regime detection (bullish/neutral/bearish)

### 7. Decay Weighting (`src/sentiment/decay_weighting.py`)
- **DecayWeightingEngine** — Exponential time-decay with configurable half-life (default: 48h)
- Credibility weighting per source, freshness ratio calculation

### 8. Sentiment Fusion (`src/sentiment/fusion.py`)
- **SentimentFusionEngine** — Multi-source conflict detection, agreement ratio
- Source reliability tracking, adaptive weighting, dominant source identification

### 9. Consensus Scoring (`src/sentiment/consensus.py`)
- **ConsensusScorer** — Multi-source voting, conviction calculation, unanimity scoring
- Consensus shift detection, market breadth, dissent tracking

### 10. Momentum Tracking (`src/sentiment/momentum.py`)
- **SentimentMomentumTracker** — Trend calculation, momentum (1st derivative), acceleration (2nd derivative)
- Trend strength (R²), inflection point detection, reversal detection

### 11. News Aggregation (`src/news/`)
- **NewsFeedManager** — Multi-source news aggregation, filtering, searching
- **EarningsCalendar** — Earnings tracking with surprise calculation
- **EconomicCalendar** — FOMC/employment/inflation event tracking
- **SECFilingsTracker** — 10-K, 10-Q, 8-K, Form 4 monitoring
- **CorporateEventsTracker** — Dividends, splits, M&A, IPO tracking
- **NewsAlertManager** — Customizable alerts with trigger types and channels

### 12. Configuration (`src/sentiment/config.py`, `src/news/config.py`)
- SentimentConfig with source credibility weights
- NewsSentimentConfig, 8 enum types, sentiment thresholds

## Database Tables
- `news_articles` — Scored articles with sentiment/topic/symbols (migration 009)
- `social_mentions` — Ticker mentions per platform/snapshot (migration 009)
- `insider_filings` — SEC Form 4 transactions (migration 009)
- `analyst_ratings` — Analyst ratings and price targets (migration 009)
- `earnings_analysis` — Earnings call analysis results (migration 009)
- `sentiment_scores` — Composite sentiment scores (migration 009)
- `decay_weighted_sentiment` — Time-decay weighted snapshots (migration 049)
- `sentiment_fusion_results` — Multi-source fusion results (migration 049)
- `sentiment_consensus_snapshots` — Consensus direction/strength (migration 049)
- `sentiment_momentum_snapshots` — Momentum and trend tracking (migration 049)
- `nlp_model_versions` — NLP model versioning and performance tracking (migration 081)
- `sentiment_event_impacts` — Event-to-sentiment impact correlation (migration 081)

## Dashboards
- `app/pages/sentiment.py` — Sentiment intelligence dashboard (composite, decay, fusion, consensus, momentum)
- `app/pages/news.py` — News aggregation (earnings, economic, SEC filings, dividends, alerts)

## Test Coverage
169 tests across 3 test files:
- `tests/test_news.py` — 34 tests (NewsFeedManager, EarningsCalendar, EconomicCalendar, SECFilingsTracker, CorporateEventsTracker, NewsAlertManager)
- `tests/test_sentiment.py` — 66 tests (NewsSentimentEngine, SocialMediaMonitor, InsiderTracker, AnalystConsensus, EarningsCallAnalyzer, SentimentComposite)
- `tests/test_sentiment_aggregation.py` — 69 tests (DecayWeighting, Fusion, Consensus, Momentum, data models)
