"""Influencer Intelligence Platform (PRD-152).

Persistent influencer tracking with discovery, performance analytics,
network analysis, and alert integration. Builds on top of the
existing InfluencerTracker from PRD-141.
"""

from src.influencer_intel.discovery import (
    InfluencerDiscovery,
    DiscoveryConfig,
    DiscoveryResult,
    CandidateProfile,
)
from src.influencer_intel.ledger import (
    PerformanceLedger,
    LedgerConfig,
    PredictionRecord,
    PerformanceStats,
    InfluencerReport,
)
from src.influencer_intel.network import (
    NetworkAnalyzer,
    NetworkConfig,
    InfluencerNode,
    CommunityCluster,
    NetworkReport,
)
from src.influencer_intel.alerts import (
    InfluencerAlertBridge,
    AlertConfig,
    InfluencerAlert,
    AlertPriority,
)

__all__ = [
    # Discovery
    "InfluencerDiscovery",
    "DiscoveryConfig",
    "DiscoveryResult",
    "CandidateProfile",
    # Ledger
    "PerformanceLedger",
    "LedgerConfig",
    "PredictionRecord",
    "PerformanceStats",
    "InfluencerReport",
    # Network
    "NetworkAnalyzer",
    "NetworkConfig",
    "InfluencerNode",
    "CommunityCluster",
    "NetworkReport",
    # Alerts
    "InfluencerAlertBridge",
    "AlertConfig",
    "InfluencerAlert",
    "AlertPriority",
]
