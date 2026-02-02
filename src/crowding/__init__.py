"""Crowding Analysis Module.

Position crowding detection, hedge fund overlap scoring,
short interest analytics, and consensus divergence.

Example:
    from src.crowding import CrowdingDetector, ShortInterestAnalyzer

    detector = CrowdingDetector()
    score = detector.score("AAPL", [8.0, 7.0, 5.0, 3.0], n_holders=50)
    print(f"Crowding: {score.level.value} ({score.score})")

    si = ShortInterestAnalyzer()
    si.add_data(short_data)
    squeeze = si.analyze("GME")
    print(f"Squeeze risk: {squeeze.risk.value}")
"""

from src.crowding.config import (
    CrowdingLevel,
    SqueezeRisk,
    ConsensusRating,
    OverlapMethod,
    DetectorConfig,
    OverlapConfig,
    ShortInterestConfig,
    ConsensusConfig,
    CrowdingConfig,
    DEFAULT_DETECTOR_CONFIG,
    DEFAULT_OVERLAP_CONFIG,
    DEFAULT_SHORT_INTEREST_CONFIG,
    DEFAULT_CONSENSUS_CONFIG,
    DEFAULT_CONFIG,
)

from src.crowding.models import (
    CrowdingScore,
    FundOverlap,
    CrowdedName,
    ShortInterestData,
    ShortSqueezeScore,
    ConsensusSnapshot,
)

from src.crowding.detector import CrowdingDetector
from src.crowding.overlap import OverlapAnalyzer
from src.crowding.short_interest import ShortInterestAnalyzer
from src.crowding.consensus import ConsensusAnalyzer

__all__ = [
    # Config
    "CrowdingLevel",
    "SqueezeRisk",
    "ConsensusRating",
    "OverlapMethod",
    "DetectorConfig",
    "OverlapConfig",
    "ShortInterestConfig",
    "ConsensusConfig",
    "CrowdingConfig",
    "DEFAULT_DETECTOR_CONFIG",
    "DEFAULT_OVERLAP_CONFIG",
    "DEFAULT_SHORT_INTEREST_CONFIG",
    "DEFAULT_CONSENSUS_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "CrowdingScore",
    "FundOverlap",
    "CrowdedName",
    "ShortInterestData",
    "ShortSqueezeScore",
    "ConsensusSnapshot",
    # Components
    "CrowdingDetector",
    "OverlapAnalyzer",
    "ShortInterestAnalyzer",
    "ConsensusAnalyzer",
]
