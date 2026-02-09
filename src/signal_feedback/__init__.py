"""Signal Performance Feedback Loop (PRD-166).

Closes the loop between trade attribution and signal weighting:
- Rolling Sharpe ratio per signal source
- Adaptive weight adjustment in SignalFusion based on trailing performance
- Confidence decay for underperforming sources
- Performance dashboard data generation

Pipeline: Execution outcome → Attribution → Performance tracker → Weight adjustment → Fusion
"""

from src.signal_feedback.tracker import (
    SourcePerformance,
    PerformanceTracker,
    TrackerConfig,
)
from src.signal_feedback.adjuster import (
    WeightAdjuster,
    AdjusterConfig,
    WeightUpdate,
)

__all__ = [
    "SourcePerformance",
    "PerformanceTracker",
    "TrackerConfig",
    "WeightAdjuster",
    "AdjusterConfig",
    "WeightUpdate",
]
