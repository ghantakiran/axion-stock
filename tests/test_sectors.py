"""Tests for Sector Rotation Analysis Module."""

import pytest
from datetime import date

from src.sectors import (
    # Config
    SectorName, CyclePhase, Trend, SignalStrength, Recommendation,
    SECTOR_ETFS, SECTOR_CHARACTERISTICS,
    # Models
    Sector, RotationSignal, BusinessCycle, SectorRecommendation,
    # Rankings
    SectorRankings, generate_sample_rankings,
    # Rotation
    RotationDetector, ROTATION_PATTERNS,
    # Cycle
    CycleAnalyzer, generate_sample_cycle,
    # Recommendations
    RecommendationEngine, BENCHMARK_WEIGHTS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_sector():
    """Sample sector data."""
    return Sector(
        name=SectorName.TECHNOLOGY,
        etf_symbol="XLK",
        price=200.0,
        change_1d=1.2,
        change_1w=2.5,
        change_1m=5.0,
        change_3m=12.0,
        rs_ratio=1.05,
        trend=Trend.UP,
    )


@pytest.fixture
def rankings_with_data():
    """Rankings with sample data."""
    return generate_sample_rankings()


# =============================================================================
# Test Sector Model
# =============================================================================

class TestSector:
    """Tests for Sector model."""
    
    def test_is_outperforming(self, sample_sector):
        """Test outperformance check."""
        assert sample_sector.is_outperforming is True
        
        sample_sector.rs_ratio = 0.95
        assert sample_sector.is_outperforming is False
    
    def test_is_trending_up(self, sample_sector):
        """Test trend detection."""
        assert sample_sector.is_trending_up is True
        
        sample_sector.trend = Trend.DOWN
        assert sample_sector.is_trending_up is False


# =============================================================================
# Test Sector Rankings
# =============================================================================

class TestSectorRankings:
    """Tests for SectorRankings."""
    
    def test_initialization(self):
        """Test rankings initialization."""
        rankings = SectorRankings()
        sectors = rankings.get_all_sectors()
        
        # Should have all 11 GICS sectors
        assert len(sectors) == 11
    
    def test_update_sector(self, sample_sector):
        """Test updating sector data."""
        rankings = SectorRankings()
        rankings.update_sector(sample_sector)
        
        retrieved = rankings.get_sector(SectorName.TECHNOLOGY)
        assert retrieved is not None
        assert retrieved.change_1m == 5.0
    
    def test_get_top_sectors(self, rankings_with_data):
        """Test getting top sectors."""
        top = rankings_with_data.get_top_sectors(5, by="momentum")
        
        assert len(top) == 5
        # Should be sorted by momentum (descending)
        scores = [s.momentum_score for s in top]
        assert scores == sorted(scores, reverse=True)
    
    def test_get_outperformers(self, rankings_with_data):
        """Test getting outperformers."""
        outperformers = rankings_with_data.get_outperformers()
        
        for sector in outperformers:
            assert sector.rs_ratio > 1.0
    
    def test_performance_spread(self, rankings_with_data):
        """Test performance spread calculation."""
        spread = rankings_with_data.get_performance_spread()
        
        assert "spread_1m" in spread
        assert spread["spread_1m"] >= 0


# =============================================================================
# Test Rotation Detector
# =============================================================================

class TestRotationDetector:
    """Tests for RotationDetector."""
    
    def test_detect_rotation(self, rankings_with_data):
        """Test rotation detection."""
        detector = RotationDetector(rankings_with_data)
        signals = detector.detect_rotation()
        
        # Should detect some rotation signals
        assert isinstance(signals, list)
    
    def test_rotation_summary(self, rankings_with_data):
        """Test rotation summary."""
        detector = RotationDetector(rankings_with_data)
        detector.detect_rotation()
        
        summary = detector.get_rotation_summary()
        
        assert "direction" in summary
        assert "top_sectors" in summary
        assert "bottom_sectors" in summary
    
    def test_patterns(self):
        """Test rotation patterns exist."""
        assert len(ROTATION_PATTERNS) >= 4
        assert "risk_on" in ROTATION_PATTERNS
        assert "risk_off" in ROTATION_PATTERNS


# =============================================================================
# Test Cycle Analyzer
# =============================================================================

class TestCycleAnalyzer:
    """Tests for CycleAnalyzer."""
    
    def test_set_indicators(self):
        """Test setting indicators."""
        analyzer = CycleAnalyzer()
        analyzer.set_indicators(
            gdp_trend=Trend.UP,
            employment_trend=Trend.UP,
        )
        
        # Should not raise
        assert True
    
    def test_analyze(self):
        """Test cycle analysis."""
        analyzer = generate_sample_cycle()
        cycle = analyzer.get_current_cycle()
        
        assert cycle is not None
        assert cycle.current_phase is not None
        assert cycle.phase_confidence > 0
    
    def test_favored_sectors(self):
        """Test getting favored sectors."""
        analyzer = generate_sample_cycle()
        
        favored = analyzer.get_favored_sectors()
        unfavored = analyzer.get_unfavored_sectors()
        
        assert isinstance(favored, list)
        assert isinstance(unfavored, list)
    
    def test_predict_next_phase(self):
        """Test phase prediction."""
        analyzer = generate_sample_cycle()
        
        next_phase, prob = analyzer.predict_next_phase()
        
        assert isinstance(next_phase, CyclePhase)
        assert 0 <= prob <= 1


# =============================================================================
# Test Recommendation Engine
# =============================================================================

class TestRecommendationEngine:
    """Tests for RecommendationEngine."""
    
    def test_generate_recommendations(self, rankings_with_data):
        """Test generating recommendations."""
        engine = RecommendationEngine(rankings_with_data)
        recommendations = engine.generate_recommendations()
        
        assert len(recommendations) == 11  # All sectors
    
    def test_recommendation_scores(self, rankings_with_data):
        """Test recommendation scores are valid."""
        engine = RecommendationEngine(rankings_with_data)
        recommendations = engine.generate_recommendations()
        
        for rec in recommendations:
            assert 0 <= rec.momentum_score <= 100
            assert 0 <= rec.relative_strength_score <= 100
            assert 0 <= rec.overall_score <= 100
    
    def test_overweight_underweight(self, rankings_with_data):
        """Test getting overweight/underweight."""
        engine = RecommendationEngine(rankings_with_data)
        engine.generate_recommendations()
        
        overweight = engine.get_overweight_sectors()
        underweight = engine.get_underweight_sectors()
        
        for rec in overweight:
            assert rec.recommendation == Recommendation.OVERWEIGHT
        
        for rec in underweight:
            assert rec.recommendation == Recommendation.UNDERWEIGHT
    
    def test_with_cycle(self, rankings_with_data):
        """Test recommendations with cycle data."""
        cycle_analyzer = generate_sample_cycle()
        engine = RecommendationEngine(rankings_with_data, cycle_analyzer)
        
        recommendations = engine.generate_recommendations()
        
        # Should have cycle alignment scores
        assert all(rec.cycle_alignment_score > 0 for rec in recommendations)
    
    def test_generate_allocation(self, rankings_with_data):
        """Test generating allocation."""
        engine = RecommendationEngine(rankings_with_data)
        engine.generate_recommendations()
        
        allocation = engine.generate_allocation()
        
        assert len(allocation.allocations) == 11
        # Weights should sum to ~1
        total = sum(allocation.allocations.values())
        assert 0.99 <= total <= 1.01


# =============================================================================
# Test Constants
# =============================================================================

class TestConstants:
    """Test configuration constants."""
    
    def test_sector_etfs(self):
        """Test sector ETF mapping."""
        assert len(SECTOR_ETFS) == 11
        assert SECTOR_ETFS[SectorName.TECHNOLOGY] == "XLK"
    
    def test_sector_characteristics(self):
        """Test sector characteristics."""
        assert len(SECTOR_CHARACTERISTICS) == 11
        
        tech = SECTOR_CHARACTERISTICS[SectorName.TECHNOLOGY]
        assert tech["cyclical"] is True
    
    def test_benchmark_weights(self):
        """Test benchmark weights sum to 1."""
        total = sum(BENCHMARK_WEIGHTS.values())
        assert 0.99 <= total <= 1.01
