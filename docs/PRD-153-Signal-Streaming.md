# PRD-153: Real-Time Signal Streaming

## Overview
Bridges sentiment and influencer signals to WebSocket channels for live push to clients. Includes aggregation windowing to prevent client overload, configurable threshold filters, and health monitoring for the streaming pipeline.

## Architecture
```
Sentiment Observations → StreamingAggregator → window + threshold
                                ↓
                          StreamFilter → per-ticker / global rules
                                ↓
                        SignalBroadcaster → format for WebSocket
                                ↓
                     WebSocket ChannelRouter → client delivery
                                ↓
                        StreamMonitor → health + latency tracking
```

## Components

### Streaming Aggregator (`aggregator.py`)
- **Windowed buffering**: Configurable window (default 30s) per ticker
- **Confidence-weighted averaging**: High-confidence observations weighted more
- **Threshold gating**: Only emit when score change exceeds min_score_change (0.1)
- **Urgency bypass**: High-urgency observations skip the window for immediate delivery
- **Buffer trimming**: Max 1000 observations per ticker to prevent memory issues

### Signal Broadcaster (`broadcaster.py`)
- **Multi-channel support**: SENTIMENT, INFLUENCER, SIGNAL, ALERT channels
- **Wire format**: Compatible with existing StreamMessage (type, channel, data, sequence, timestamp)
- **Message queue**: Configurable max queue size (500) with auto-trimming
- **Dedup window**: Suppress duplicate messages within 5s window
- **Sequence numbering**: Monotonic sequence for client gap detection

### Stream Filter (`filters.py`)
- **Default + per-ticker rules**: Different thresholds for different tickers
- **Filter criteria**: min_score_change, min_confidence, min_observations, urgency
- **Ticker allowlist/blocklist**: Control which tickers can broadcast
- **Urgency bypass**: High urgency always passes regardless of other thresholds
- **Pass rate tracking**: Monitor what percentage of updates get through

### Stream Monitor (`monitor.py`)
- **Health assessment**: healthy / degraded / unhealthy status
- **Latency tracking**: Average and max latency per window
- **Error rate monitoring**: Alert on high error rates (>10%)
- **Throughput tracking**: Messages per minute with minimum threshold alerts
- **Active ticker count**: How many tickers are actively streaming

## Database Tables
- `stream_events`: Event log for debugging and replay
- `stream_health_snapshots`: Point-in-time health assessments

## Dashboard
4-tab Streamlit interface:
1. **Live Feed**: Simulated real-time signal stream with sentiment indicators
2. **Aggregation**: Window and threshold configuration with explanations
3. **Filters**: Rule testing with pass/reject visualization
4. **Health**: Pipeline health metrics, latency, throughput, error rates

## Integration Points
- **websocket** (existing): ChannelRouter for actual WebSocket delivery
- **ws_scaling** (PRD-119): Distributed message routing for multi-instance
- **llm_sentiment** (PRD-151): LLM sentiment observations feed into aggregator
- **influencer_intel** (PRD-152): Influencer alerts broadcast via INFLUENCER channel
- **social_intelligence** (PRD-141): Social signals feed into sentiment stream
