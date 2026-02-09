# PRD-152: Influencer Intelligence Platform

## Overview
Persistent influencer tracking with discovery algorithms, performance analytics, network analysis, and real-time alert integration. Extends the in-memory InfluencerTracker (PRD-141) with database persistence, historical accuracy tracking, and proactive influencer discovery.

## Architecture
```
Social Posts → InfluencerDiscovery → CandidateProfile ranking
                      ↓
              PerformanceLedger → accuracy tracking + sector specialization
                      ↓
              NetworkAnalyzer → community detection + coordination scoring
                      ↓
              InfluencerAlertBridge → mega_mention / reversal / coordination alerts
```

## Components

### Influencer Discovery (`discovery.py`)
- **Engagement velocity**: Upvotes/day growth rate detection
- **Sentiment consistency**: Standard deviation → consistency score (0-1)
- **Early-mover detection**: Tracks who mentions tickers first (1.5x boost)
- **Discovery score**: 30% velocity + 25% engagement + 20% consistency + 15% first-mover + 10% volume
- **Configurable filters**: min_posts, min_engagement_rate, max_candidates

### Performance Ledger (`ledger.py`)
- **Prediction recording**: Direction (bullish/bearish), entry/exit price, sector
- **Outcome evaluation**: Automatic correct/incorrect based on price move direction
- **Accuracy breakdown**: Overall, bullish-only, bearish-only, per-sector
- **Streak tracking**: Current win/loss streak and max historical streak
- **Report generation**: Cross-influencer leaderboard sorted by accuracy

### Network Analyzer (`network.py`)
- **Co-mention graph**: Edge between authors sharing >= N tickers
- **Community detection**: BFS-based connected component clustering
- **Coordination scoring**: Time-window analysis for synchronized posting
- **Centrality metrics**: Degree centrality normalized to graph maximum
- **Density tracking**: Graph density metric (0-1)

### Alert Bridge (`alerts.py`)
- **Mega/macro mention alerts**: HIGH priority for mega, MEDIUM for macro influencers
- **Sentiment reversal alerts**: Triggered when influencer swings sentiment by >= threshold
- **Coordination alerts**: CRITICAL priority when multiple influencers align on same ticker
- **Tier filtering**: Configurable minimum tier and impact score for alert generation

## Database Tables
- `influencer_profiles`: Persistent influencer profiles with tier, accuracy, discovery score
- `influencer_predictions`: Individual prediction records with outcomes
- `influencer_clusters`: Detected community clusters with coordination scores

## Dashboard
4-tab Streamlit interface:
1. **Discovery**: Run discovery scans, view candidates ranked by score
2. **Performance**: Accuracy leaderboard, per-author metrics, streak tracking
3. **Network**: Graph visualization, cluster detection, coordination metrics
4. **Alerts**: Real-time alert feed with priority icons and history

## Integration Points
- **social_intelligence** (PRD-141): Extends InfluencerTracker with persistence and discovery
- **social_crawler** (PRD-140): Feeds post data into discovery and network analysis
- **alert_network** (PRD-142): Alert bridge connects to notification system
- **llm_sentiment** (PRD-151): LLM-powered sentiment for richer influencer signal analysis
