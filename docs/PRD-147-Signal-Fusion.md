# PRD-147: Autonomous Signal Fusion Agent

## Overview
The Signal Fusion Agent aggregates signals from all platform sources (EMA Cloud, Social Intelligence, Factor Engine, ML models, Sentiment, Technical, Fundamental, News) into unified trade recommendations with confidence scoring.

## Architecture

### Pipeline
1. **Collect** -- SignalCollector gathers RawSignals from 8 sources
2. **Fuse** -- SignalFusion merges signals into weighted consensus with time decay
3. **Recommend** -- TradeRecommender converts fused signals to actionable BUY/SELL/HOLD
4. **Execute** -- FusionAgent optionally routes to broker (paper or live)

### Signal Sources (SignalSource enum)
| Source | Default Weight | Description |
|--------|---------------|-------------|
| EMA_CLOUD | 0.25 | Ripster EMA cloud signals |
| FACTOR | 0.20 | Multi-factor model scores |
| SOCIAL | 0.15 | Social intelligence signals |
| ML_RANKING | 0.15 | ML ranking model output |
| SENTIMENT | 0.10 | Sentiment analysis |
| TECHNICAL | 0.10 | Technical indicators |
| FUNDAMENTAL | 0.05 | Fundamental analysis |
| NEWS | -- | News event signals |

### Fusion Algorithm
- Group signals by symbol
- Weight by source importance (configurable)
- Apply exponential time decay (configurable half-life)
- Calculate agreement ratio across sources
- Generate composite score (-100 to +100)
- Produce human-readable reasoning

### Action Thresholds
| Composite Score | Action |
|----------------|--------|
| >= +50 | STRONG_BUY |
| >= +20 | BUY |
| -20 to +20 | HOLD |
| <= -20 | SELL |
| <= -50 | STRONG_SELL |

## Module Structure
- `src/signal_fusion/collector.py` -- SignalSource, RawSignal, SignalCollector
- `src/signal_fusion/fusion.py` -- FusionConfig, FusedSignal, SignalFusion
- `src/signal_fusion/recommender.py` -- Action, Recommendation, TradeRecommender
- `src/signal_fusion/agent.py` -- AgentConfig, AgentState, FusionAgent

## Database Tables
- `signal_fusion_scans` -- Scan execution log
- `signal_fusion_recommendations` -- Generated recommendations

## Dashboard
4-tab Streamlit dashboard: Signal Scanner, Fusion Results, Recommendations, Agent Config.

## Configuration
- Source weights adjustable via dashboard sliders
- Min confidence threshold (default 0.5)
- Max concurrent positions (default 10)
- Scan interval (default 15 minutes)
- Auto-execute toggle with paper mode safety

## Testing
50 tests across 8 test classes covering all components and edge cases.
