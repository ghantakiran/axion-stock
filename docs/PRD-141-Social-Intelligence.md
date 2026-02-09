# PRD-141: Social Signal Intelligence

## Overview
Advanced analytics layer on top of Social Signal Crawler (PRD-140). Processes crawled social data into actionable trading signals using multi-factor scoring, volume anomaly detection, influencer tracking, and cross-platform correlation.

## Architecture

### Source Files (`src/social_intelligence/`)

| File | Lines | Description |
|------|-------|-------------|
| `__init__.py` | ~80 | Public API: 20 exports across 5 submodules |
| `scorer.py` | ~280 | Multi-factor signal scorer (sentiment, engagement, velocity, freshness, credibility) |
| `volume.py` | ~250 | Z-score based volume anomaly detection with sustained spike tracking |
| `influencer.py` | ~260 | Influencer profiling, tier classification, accuracy tracking |
| `correlator.py` | ~240 | Cross-platform sentiment correlation and consensus detection |
| `generator.py` | ~280 | Full pipeline orchestrator producing SocialTradingSignal objects |

### Key Components

1. **SignalScorer** — Combines 5 weighted factors into a 0-100 score:
   - Sentiment (30%): polarity strength
   - Engagement (20%): normalized upvotes + comments
   - Velocity (20%): mention acceleration vs baseline (log-scaled)
   - Freshness (15%): time-decay recency
   - Credibility (15%): source platform reliability

2. **VolumeAnalyzer** — Detects unusual mention spikes:
   - Z-score analysis (threshold: 2.0σ)
   - Sustained anomaly tracking (3+ consecutive periods)
   - Extreme classification (5x+ baseline ratio)

3. **InfluencerTracker** — Profiles high-impact authors:
   - 4 tiers: mega (10K+), macro (5K+), micro (1K+), nano
   - Prediction accuracy recording
   - Impact score: 40% reach + 40% accuracy + 20% consistency

4. **CrossPlatformCorrelator** — Compares signals across platforms:
   - Weighted consensus calculation (Twitter 30%, Reddit 25%, etc.)
   - Agreement score (0-1) with sentiment spread bonus
   - Consensus flag (≥2 platforms, ≥0.7 agreement)

5. **SocialSignalGenerator** — Full pipeline orchestrator:
   - Runs all 4 layers in sequence
   - Applies boost factors: volume (+15), influencer (+10), consensus (+12)
   - Classifies into actions: STRONG_BUY/BUY/WATCH/HOLD/SELL/STRONG_SELL

### Data Flow

```
SocialPost[] → SignalScorer → ScoredTicker[]
             → VolumeAnalyzer → VolumeAnomaly[]
             → InfluencerTracker → InfluencerSignal[]
             → CrossPlatformCorrelator → CorrelationResult[]
                        ↓
             SocialSignalGenerator.analyze()
                        ↓
             IntelligenceReport (unified output)
```

## ORM Models (`src/db/models.py`)

| Model | Table | Description |
|-------|-------|-------------|
| `SocialSignalScoreRecord` | `social_signal_scores` | Composite signal scores per ticker |
| `SocialVolumeAnomalyRecord` | `social_volume_anomalies` | Detected volume spikes |
| `SocialInfluencerProfileRecord` | `social_influencer_profiles` | Influencer profiles |
| `SocialTradingSignalRecord` | `social_trading_signals` | Generated trading signals |

## Migration

- **File**: `alembic/versions/141_social_intelligence.py`
- **Revision**: `141` → `down_revision`: `140`
- **Tables**: 4 new tables with appropriate indexes

## Dashboard (`app/pages/social_intelligence.py`)

4 tabs:
1. **Signal Overview** — Scored tickers with factor breakdown, score distribution chart
2. **Volume Anomalies** — Z-score threshold slider, anomaly detection on demo data
3. **Influencer Tracking** — Top influencers table, recent influencer signals
4. **Intelligence Report** — Full pipeline with trading signals, cross-platform correlation

## Tests (`tests/test_social_intelligence.py`)

8 test classes, ~55 tests:

| Test Class | Tests | Coverage |
|---|---|---|
| `TestSignalScorer` | 10 | Multi-factor scoring, strength classification, velocity, direction |
| `TestVolumeAnalyzer` | 9 | Stable volume, spikes, extreme/sustained, batch, timeseries |
| `TestInfluencerTracker` | 7 | Profile building, thresholds, signals, tiers, predictions |
| `TestCrossPlatformCorrelator` | 7 | Consensus, divergence, agreement score, single platform |
| `TestSocialSignalGenerator` | 9 | Full pipeline, action classification, volume boost, report |
| `TestMentionTimeseries` | 2 | Add/properties, to_dict |
| `TestModuleImports` | 4 | Exports, enums, config defaults |

## Dependencies

- **Required**: `src/sentiment/social.py` (SocialPost, TickerMention)
- **Optional**: `src/social_crawler/` (for live crawled data)
