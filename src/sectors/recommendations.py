"""Sector Recommendations.

Generate sector ETF recommendations based on analysis.
"""

from datetime import datetime, date, timezone
from typing import Optional
import logging

from src.sectors.config import (
    SectorName,
    Recommendation,
    Conviction,
    SECTOR_ETFS,
    SECTOR_CHARACTERISTICS,
)
from src.sectors.models import (
    Sector,
    SectorRecommendation,
    SectorAllocation,
    BusinessCycle,
)
from src.sectors.rankings import SectorRankings
from src.sectors.cycle import CycleAnalyzer

logger = logging.getLogger(__name__)


# Benchmark sector weights (approximate S&P 500 weights)
BENCHMARK_WEIGHTS = {
    SectorName.TECHNOLOGY: 0.28,
    SectorName.HEALTHCARE: 0.13,
    SectorName.FINANCIALS: 0.13,
    SectorName.CONSUMER_DISC: 0.10,
    SectorName.COMMUNICATION: 0.09,
    SectorName.INDUSTRIALS: 0.09,
    SectorName.CONSUMER_STAPLES: 0.06,
    SectorName.ENERGY: 0.04,
    SectorName.UTILITIES: 0.03,
    SectorName.REAL_ESTATE: 0.03,
    SectorName.MATERIALS: 0.02,
}


class RecommendationEngine:
    """Generates sector recommendations.
    
    Example:
        engine = RecommendationEngine(rankings, cycle_analyzer)
        
        recommendations = engine.generate_recommendations()
        for rec in recommendations:
            print(f"{rec.sector.value}: {rec.recommendation.value}")
    """
    
    def __init__(
        self,
        rankings: SectorRankings,
        cycle_analyzer: Optional[CycleAnalyzer] = None,
    ):
        self.rankings = rankings
        self.cycle_analyzer = cycle_analyzer
        self._recommendations: list[SectorRecommendation] = []
    
    def generate_recommendations(self) -> list[SectorRecommendation]:
        """Generate sector recommendations.
        
        Returns:
            List of SectorRecommendation sorted by score.
        """
        recommendations = []
        
        # Get cycle data if available
        cycle = None
        if self.cycle_analyzer:
            cycle = self.cycle_analyzer.get_current_cycle()
        
        for sector in self.rankings.get_all_sectors():
            rec = self._generate_recommendation(sector, cycle)
            recommendations.append(rec)
        
        # Sort by overall score
        recommendations.sort(key=lambda r: r.overall_score, reverse=True)
        
        self._recommendations = recommendations
        return recommendations
    
    def _generate_recommendation(
        self,
        sector: Sector,
        cycle: Optional[BusinessCycle],
    ) -> SectorRecommendation:
        """Generate recommendation for a single sector."""
        # Calculate scores
        momentum_score = self._calculate_momentum_score(sector)
        rs_score = self._calculate_rs_score(sector)
        cycle_score = self._calculate_cycle_score(sector.name, cycle)
        
        # Overall score (weighted average)
        overall_score = (
            momentum_score * 0.4 +
            rs_score * 0.35 +
            cycle_score * 0.25
        )
        
        # Determine recommendation
        recommendation, conviction = self._score_to_recommendation(overall_score)
        
        # Calculate target weight
        benchmark_weight = BENCHMARK_WEIGHTS.get(sector.name, 0.05)
        if recommendation == Recommendation.OVERWEIGHT:
            target_weight = benchmark_weight * 1.5
        elif recommendation == Recommendation.UNDERWEIGHT:
            target_weight = benchmark_weight * 0.5
        else:
            target_weight = benchmark_weight
        
        # Generate rationale
        rationale = self._generate_rationale(
            sector, momentum_score, rs_score, cycle_score, cycle
        )
        
        return SectorRecommendation(
            sector=sector.name,
            etf_symbol=sector.etf_symbol,
            recommendation=recommendation,
            conviction=conviction,
            momentum_score=momentum_score,
            relative_strength_score=rs_score,
            cycle_alignment_score=cycle_score,
            overall_score=overall_score,
            target_weight=target_weight,
            benchmark_weight=benchmark_weight,
            active_weight=target_weight - benchmark_weight,
            rationale=rationale,
        )
    
    def _calculate_momentum_score(self, sector: Sector) -> float:
        """Calculate momentum score (0-100)."""
        score = 50  # Base
        
        # Recent performance
        if sector.change_1m > 3:
            score += 15
        elif sector.change_1m > 0:
            score += 5
        elif sector.change_1m < -3:
            score -= 15
        elif sector.change_1m < 0:
            score -= 5
        
        # Trend
        if sector.is_trending_up:
            score += 20
        elif sector.trend.value == "down":
            score -= 20
        
        # 3-month momentum
        if sector.change_3m > 10:
            score += 15
        elif sector.change_3m < -5:
            score -= 15
        
        return max(0, min(100, score))
    
    def _calculate_rs_score(self, sector: Sector) -> float:
        """Calculate relative strength score (0-100)."""
        # RS ratio centered around 1.0
        # 1.1 = strong, 0.9 = weak
        rs = sector.rs_ratio
        
        if rs >= 1.1:
            return 90
        elif rs >= 1.05:
            return 75
        elif rs >= 1.0:
            return 60
        elif rs >= 0.95:
            return 40
        elif rs >= 0.9:
            return 25
        else:
            return 10
    
    def _calculate_cycle_score(
        self,
        sector_name: SectorName,
        cycle: Optional[BusinessCycle],
    ) -> float:
        """Calculate cycle alignment score (0-100)."""
        if not cycle:
            return 50  # Neutral if no cycle data
        
        if sector_name in cycle.overweight_sectors:
            return 85
        elif sector_name in cycle.underweight_sectors:
            return 15
        else:
            return 50
    
    def _score_to_recommendation(
        self,
        score: float,
    ) -> tuple[Recommendation, Conviction]:
        """Convert score to recommendation and conviction."""
        if score >= 75:
            return Recommendation.OVERWEIGHT, Conviction.HIGH
        elif score >= 60:
            return Recommendation.OVERWEIGHT, Conviction.MEDIUM
        elif score >= 55:
            return Recommendation.NEUTRAL, Conviction.MEDIUM
        elif score >= 45:
            return Recommendation.NEUTRAL, Conviction.LOW
        elif score >= 35:
            return Recommendation.UNDERWEIGHT, Conviction.MEDIUM
        else:
            return Recommendation.UNDERWEIGHT, Conviction.HIGH
    
    def _generate_rationale(
        self,
        sector: Sector,
        momentum: float,
        rs: float,
        cycle: float,
        cycle_data: Optional[BusinessCycle],
    ) -> list[str]:
        """Generate rationale for recommendation."""
        rationale = []
        
        # Momentum rationale
        if momentum >= 70:
            rationale.append(f"Strong momentum (1M: {sector.change_1m:+.1f}%, 3M: {sector.change_3m:+.1f}%)")
        elif momentum <= 30:
            rationale.append(f"Weak momentum (1M: {sector.change_1m:+.1f}%, 3M: {sector.change_3m:+.1f}%)")
        
        # RS rationale
        if sector.rs_ratio >= 1.05:
            rationale.append(f"Outperforming market (RS: {sector.rs_ratio:.2f})")
        elif sector.rs_ratio <= 0.95:
            rationale.append(f"Underperforming market (RS: {sector.rs_ratio:.2f})")
        
        # Cycle rationale
        if cycle_data:
            if sector.name in cycle_data.overweight_sectors:
                rationale.append(f"Favored in {cycle_data.current_phase.value.replace('_', ' ')} phase")
            elif sector.name in cycle_data.underweight_sectors:
                rationale.append(f"Not favored in {cycle_data.current_phase.value.replace('_', ' ')} phase")
        
        # Characteristics
        chars = SECTOR_CHARACTERISTICS.get(sector.name, {})
        if chars.get("cyclical"):
            rationale.append("Cyclical sector")
        elif chars.get("type") == "defensive":
            rationale.append("Defensive sector")
        
        return rationale
    
    def get_recommendations(
        self,
        recommendation_type: Optional[Recommendation] = None,
    ) -> list[SectorRecommendation]:
        """Get recommendations with optional filtering."""
        recs = self._recommendations
        
        if recommendation_type:
            recs = [r for r in recs if r.recommendation == recommendation_type]
        
        return recs
    
    def get_overweight_sectors(self) -> list[SectorRecommendation]:
        """Get overweight recommendations."""
        return self.get_recommendations(Recommendation.OVERWEIGHT)
    
    def get_underweight_sectors(self) -> list[SectorRecommendation]:
        """Get underweight recommendations."""
        return self.get_recommendations(Recommendation.UNDERWEIGHT)
    
    def generate_allocation(self) -> SectorAllocation:
        """Generate tactical sector allocation.
        
        Returns:
            SectorAllocation with recommended weights.
        """
        allocations = {}
        
        for rec in self._recommendations:
            allocations[rec.sector] = rec.target_weight
        
        # Normalize to sum to 100%
        total = sum(allocations.values())
        if total > 0:
            allocations = {k: v / total for k, v in allocations.items()}
        
        # Calculate active share
        active_weights = []
        for sector, weight in allocations.items():
            benchmark = BENCHMARK_WEIGHTS.get(sector, 0)
            active_weights.append(abs(weight - benchmark))
        
        active_share = sum(active_weights) / 2 * 100  # Divide by 2 for one-sided
        
        return SectorAllocation(
            name="Tactical Sector Allocation",
            allocations=allocations,
            benchmark_allocations=BENCHMARK_WEIGHTS,
            active_share=active_share,
        )
