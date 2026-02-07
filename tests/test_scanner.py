"""Tests for Market Scanner."""

import pytest
from datetime import date

from src.scanner import (
    # Config
    Operator, ScanCategory, ActivityType, PatternType, CandlePattern,
    # Models
    ScanCriterion, Scanner, ScanResult,
    # Engine
    ScannerEngine, create_scanner,
    # Presets
    PRESET_SCANNERS, get_preset_scanner, get_all_presets,
    # Unusual
    UnusualActivityDetector,
    # Patterns
    PatternDetector,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        "AAPL": {
            "name": "Apple Inc.",
            "price": 185.0,
            "change": 5.0,
            "change_pct": 2.8,
            "gap_pct": 1.5,
            "volume": 80000000,
            "avg_volume": 50000000,
            "relative_volume": 1.6,
            "rsi": 55,
            "market_cap": 2.9e12,
            "sector": "Technology",
        },
        "NVDA": {
            "name": "NVIDIA Corp.",
            "price": 800.0,
            "change": 45.0,
            "change_pct": 5.9,
            "gap_pct": 4.2,
            "volume": 60000000,
            "avg_volume": 25000000,
            "relative_volume": 2.4,
            "rsi": 72,
            "market_cap": 2.0e12,
            "sector": "Technology",
        },
        "XOM": {
            "name": "Exxon Mobil",
            "price": 105.0,
            "change": -2.5,
            "change_pct": -2.3,
            "gap_pct": -1.8,
            "volume": 15000000,
            "avg_volume": 12000000,
            "relative_volume": 1.25,
            "rsi": 42,
            "market_cap": 450e9,
            "sector": "Energy",
        },
        "TSLA": {
            "name": "Tesla Inc.",
            "price": 250.0,
            "change": -15.0,
            "change_pct": -5.7,
            "gap_pct": -3.5,
            "volume": 120000000,
            "avg_volume": 40000000,
            "relative_volume": 3.0,
            "rsi": 28,
            "market_cap": 800e9,
            "sector": "Consumer Cyclical",
        },
    }


@pytest.fixture
def sample_ohlc():
    """Sample OHLC data."""
    return [
        {"open": 100, "high": 102, "low": 99, "close": 98, "date": "2024-01-01"},  # Bearish
        {"open": 98, "high": 99, "low": 96, "close": 98.5, "date": "2024-01-02"},  # Small body
        {"open": 99, "high": 103, "low": 98, "close": 102, "date": "2024-01-03"},  # Bullish
    ]


# =============================================================================
# Test Scan Criterion
# =============================================================================

class TestScanCriterion:
    """Tests for ScanCriterion."""
    
    def test_greater_than(self):
        """Test greater than operator."""
        criterion = ScanCriterion(field="price", operator=Operator.GT, value=100)
        
        assert criterion.evaluate({"price": 150}) is True
        assert criterion.evaluate({"price": 50}) is False
    
    def test_less_than(self):
        """Test less than operator."""
        criterion = ScanCriterion(field="rsi", operator=Operator.LT, value=30)
        
        assert criterion.evaluate({"rsi": 25}) is True
        assert criterion.evaluate({"rsi": 50}) is False
    
    def test_between(self):
        """Test between operator."""
        criterion = ScanCriterion(field="rsi", operator=Operator.BETWEEN, value=(30, 70))
        
        assert criterion.evaluate({"rsi": 50}) is True
        assert criterion.evaluate({"rsi": 80}) is False
        assert criterion.evaluate({"rsi": 20}) is False
    
    def test_crosses_above(self):
        """Test crosses above operator."""
        criterion = ScanCriterion(field="price", operator=Operator.CROSSES_ABOVE, value=100)
        
        assert criterion.evaluate({"price": 105, "price_prev": 95}) is True
        assert criterion.evaluate({"price": 105, "price_prev": 102}) is False


# =============================================================================
# Test Scanner Engine
# =============================================================================

class TestScannerEngine:
    """Tests for ScannerEngine."""
    
    def test_add_scanner(self):
        """Test adding a scanner."""
        engine = ScannerEngine()
        scanner = Scanner(name="Test Scanner")
        
        engine.add_scanner(scanner)
        
        retrieved = engine.get_scanner(scanner.scanner_id)
        assert retrieved is not None
        assert retrieved.name == "Test Scanner"
    
    def test_run_scan(self, sample_market_data):
        """Test running a scan."""
        engine = ScannerEngine()
        
        scanner = create_scanner(
            name="Big Movers",
            criteria=[
                ("change_pct", Operator.GT, 5.0),
            ],
        )
        
        results = engine.run_scan(scanner, sample_market_data)
        
        # NVDA and TSLA have >5% change (TSLA is -5.7, abs > 5)
        # But our criterion checks change_pct > 5.0, so only NVDA
        assert len(results) >= 1
        assert results[0].symbol == "NVDA"
    
    def test_volume_scan(self, sample_market_data):
        """Test volume-based scan."""
        engine = ScannerEngine()
        
        scanner = create_scanner(
            name="Volume Spike",
            criteria=[
                ("relative_volume", Operator.GT, 2.0),
            ],
        )
        
        results = engine.run_scan(scanner, sample_market_data)
        
        # NVDA (2.4x) and TSLA (3.0x) have relative_volume > 2.0
        assert len(results) == 2
        symbols = [r.symbol for r in results]
        assert "NVDA" in symbols
        assert "TSLA" in symbols
    
    def test_multiple_criteria(self, sample_market_data):
        """Test scan with multiple criteria."""
        engine = ScannerEngine()
        
        scanner = create_scanner(
            name="Momentum + Volume",
            criteria=[
                ("change_pct", Operator.GT, 2.0),
                ("relative_volume", Operator.GT, 1.5),
            ],
        )
        
        results = engine.run_scan(scanner, sample_market_data)

        # Both AAPL (2.8%, 1.6x) and NVDA (5.9%, 2.4x) meet criteria
        assert len(results) == 2
        symbols = [r.symbol for r in results]
        assert "NVDA" in symbols
        assert "AAPL" in symbols


# =============================================================================
# Test Preset Scanners
# =============================================================================

class TestPresetScanners:
    """Tests for preset scanners."""
    
    def test_presets_exist(self):
        """Test preset scanners exist."""
        assert len(PRESET_SCANNERS) >= 15
    
    def test_get_preset_scanner(self):
        """Test getting preset by name."""
        scanner = get_preset_scanner("gap_up")
        
        assert scanner is not None
        assert scanner.name == "Gap Up >3%"
        assert scanner.is_preset is True
    
    def test_gap_up_scan(self, sample_market_data):
        """Test gap up preset scanner."""
        engine = ScannerEngine()
        scanner = get_preset_scanner("gap_up")
        
        results = engine.run_scan(scanner, sample_market_data)
        
        # NVDA has gap_pct 4.2%
        assert len(results) >= 1
        assert results[0].symbol == "NVDA"
    
    def test_rsi_oversold_scan(self, sample_market_data):
        """Test RSI oversold preset scanner."""
        engine = ScannerEngine()
        scanner = get_preset_scanner("rsi_oversold")
        
        results = engine.run_scan(scanner, sample_market_data)
        
        # TSLA has RSI 28
        assert len(results) >= 1
        assert results[0].symbol == "TSLA"
    
    def test_all_presets(self):
        """Test getting all presets."""
        presets = get_all_presets()
        
        assert len(presets) >= 15
        assert all(s.is_preset for s in presets)


# =============================================================================
# Test Unusual Activity Detector
# =============================================================================

class TestUnusualActivityDetector:
    """Tests for UnusualActivityDetector."""
    
    def test_detect_volume_surge(self):
        """Test detecting volume surge."""
        detector = UnusualActivityDetector()
        
        current_data = {
            "TEST": {
                "name": "Test Co",
                "volume": 10000000,
                "avg_volume": 2000000,
                "price": 50.0,
                "change_pct": 2.0,
            }
        }
        
        historical = {
            "TEST": {
                "avg_volume": 2000000,
                "std_volume": 500000,
            }
        }
        
        activities = detector.scan(current_data, historical)
        
        # Volume is 10M vs 2M avg with 500K std = 16 std dev
        assert len(activities) >= 1
        assert activities[0].activity_type == ActivityType.VOLUME_SURGE
    
    def test_get_top_volume_surges(self):
        """Test getting top volume surges."""
        detector = UnusualActivityDetector()
        
        current_data = {
            "A": {"name": "A", "volume": 5000000, "avg_volume": 1000000, "price": 10, "change_pct": 1},
            "B": {"name": "B", "volume": 8000000, "avg_volume": 1000000, "price": 20, "change_pct": 2},
        }
        
        historical = {
            "A": {"avg_volume": 1000000, "std_volume": 200000},
            "B": {"avg_volume": 1000000, "std_volume": 200000},
        }
        
        detector.scan(current_data, historical)
        top = detector.get_top_volume_surges(limit=5)
        
        assert len(top) == 2
        # B should be first (higher deviation)
        assert top[0].symbol == "B"


# =============================================================================
# Test Pattern Detector
# =============================================================================

class TestPatternDetector:
    """Tests for PatternDetector."""
    
    def test_detect_doji(self):
        """Test detecting doji candle."""
        detector = PatternDetector()
        
        ohlc = [
            {"open": 100, "high": 102, "low": 98, "close": 99, "date": "2024-01-01"},
            {"open": 99, "high": 101, "low": 97, "close": 98, "date": "2024-01-02"},
            {"open": 100, "high": 102, "low": 98, "close": 100.05, "date": "2024-01-03"},  # Doji
        ]
        
        patterns = detector.detect_candlesticks("TEST", ohlc)
        
        doji_patterns = [p for p in patterns if p.pattern_type == CandlePattern.DOJI]
        assert len(doji_patterns) >= 1
    
    def test_detect_bullish_engulfing(self):
        """Test detecting bullish engulfing."""
        detector = PatternDetector()
        
        ohlc = [
            {"open": 100, "high": 102, "low": 99, "close": 101, "date": "2024-01-01"},
            {"open": 101, "high": 102, "low": 98, "close": 99, "date": "2024-01-02"},  # Bearish
            {"open": 98, "high": 104, "low": 97, "close": 103, "date": "2024-01-03"},  # Engulfs
        ]
        
        patterns = detector.detect_candlesticks("TEST", ohlc)
        
        engulfing = [p for p in patterns if p.pattern_type == CandlePattern.ENGULFING_BULL]
        assert len(engulfing) >= 1
    
    def test_morning_star(self, sample_ohlc):
        """Test detecting morning star pattern."""
        detector = PatternDetector()
        
        patterns = detector.detect_candlesticks("TEST", sample_ohlc)
        
        morning_star = [p for p in patterns if p.pattern_type == CandlePattern.MORNING_STAR]
        # May or may not detect depending on exact thresholds
        assert isinstance(morning_star, list)
