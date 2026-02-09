"""Real-Time Signal Streaming (PRD-153).

Bridges sentiment and influencer signals to WebSocket channels
for live push to clients. Includes aggregation windowing,
threshold filtering, and multi-channel broadcasting.
"""

from src.signal_streaming.aggregator import (
    StreamingAggregator,
    AggregatorConfig,
    AggregatedUpdate,
    TickerState,
)
from src.signal_streaming.broadcaster import (
    SignalBroadcaster,
    BroadcasterConfig,
    BroadcastMessage,
    ChannelMapping,
)
from src.signal_streaming.filters import (
    StreamFilter,
    FilterConfig,
    FilterResult,
    ThresholdRule,
)
from src.signal_streaming.monitor import (
    StreamMonitor,
    MonitorConfig,
    StreamStats,
    StreamHealth,
)

__all__ = [
    # Aggregator
    "StreamingAggregator",
    "AggregatorConfig",
    "AggregatedUpdate",
    "TickerState",
    # Broadcaster
    "SignalBroadcaster",
    "BroadcasterConfig",
    "BroadcastMessage",
    "ChannelMapping",
    # Filters
    "StreamFilter",
    "FilterConfig",
    "FilterResult",
    "ThresholdRule",
    # Monitor
    "StreamMonitor",
    "MonitorConfig",
    "StreamStats",
    "StreamHealth",
]
