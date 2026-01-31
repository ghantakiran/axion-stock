"""Sector Rotation Analysis Module.

Track sector performance, detect rotation, and map to business cycles.

Example:
    from src.sectors import (
        SectorRankings, SectorName, Trend,
        RotationDetector, CycleAnalyzer, RecommendationEngine,
    )
    
    # Create rankings
    rankings = SectorRankings()
    rankings.update_prices(market_data)
    
    # Get top sectors
    top = rankings.get_top_sectors(5)
    
    # Detect rotation
    detector = RotationDetector(rankings)
    signals = detector.detect_rotation()
    
    # Generate recommendations
    engine = RecommendationEngine(rankings)
    recommendations = engine.generate_recommendations()
"""

from src.sectors.config import (
    SectorName,
    CyclePhase,
    Trend,
    SignalStrength,
    Recommendation,
    Conviction,
    SECTOR_ETFS,
    ETF_TO_SECTOR,
    SECTOR_CHARACTERISTICS,
    CYCLE_SECTOR_PREFERENCES,
    DEFAULT_BENCHMARK,
    SectorConfig,
    CycleConfig,
    DEFAULT_SECTOR_CONFIG,
    DEFAULT_CYCLE_CONFIG,
)

from src.sectors.models import (
    Sector,
    SectorPerformance,
    RotationSignal,
    RotationPattern,
    BusinessCycle,
    CycleTransition,
    SectorRecommendation,
    SectorAllocation,
)

from src.sectors.rankings import (
    SectorRankings,
    generate_sample_rankings,
)

from src.sectors.rotation import (
    RotationDetector,
    ROTATION_PATTERNS,
)

from src.sectors.cycle import (
    CycleAnalyzer,
    PHASE_CHARACTERISTICS,
    generate_sample_cycle,
)

from src.sectors.recommendations import (
    RecommendationEngine,
    BENCHMARK_WEIGHTS,
)


__all__ = [
    # Config
    "SectorName",
    "CyclePhase",
    "Trend",
    "SignalStrength",
    "Recommendation",
    "Conviction",
    "SECTOR_ETFS",
    "ETF_TO_SECTOR",
    "SECTOR_CHARACTERISTICS",
    "CYCLE_SECTOR_PREFERENCES",
    "DEFAULT_BENCHMARK",
    "SectorConfig",
    "CycleConfig",
    "DEFAULT_SECTOR_CONFIG",
    "DEFAULT_CYCLE_CONFIG",
    # Models
    "Sector",
    "SectorPerformance",
    "RotationSignal",
    "RotationPattern",
    "BusinessCycle",
    "CycleTransition",
    "SectorRecommendation",
    "SectorAllocation",
    # Rankings
    "SectorRankings",
    "generate_sample_rankings",
    # Rotation
    "RotationDetector",
    "ROTATION_PATTERNS",
    # Cycle
    "CycleAnalyzer",
    "PHASE_CHARACTERISTICS",
    "generate_sample_cycle",
    # Recommendations
    "RecommendationEngine",
    "BENCHMARK_WEIGHTS",
]
