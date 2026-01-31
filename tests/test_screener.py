"""Tests for Advanced Stock Screener."""

import pytest
from datetime import date

from src.screener import (
    # Config
    FilterCategory, DataType, Operator, Universe, AlertType,
    # Models
    FilterCondition, CustomFormula, Screen, ScreenMatch,
    # Core
    FilterRegistry, FILTER_REGISTRY, ExpressionParser,
    ScreenerEngine, ScreenManager,
    # Presets
    get_preset_screens, PRESET_SCREENS,
    # Alerts
    ScreenAlertManager,
    # Backtest
    ScreenBacktester, ScreenBacktestConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_stock_data():
    """Sample stock data for testing."""
    return {
        "AAPL": {
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "price": 185.0,
            "market_cap": 2.9e12,
            "pe_ratio": 28.0,
            "pb_ratio": 45.0,
            "ps_ratio": 7.5,
            "dividend_yield": 0.5,
            "revenue_growth": 0.08,
            "gross_margin": 45.0,
            "operating_margin": 30.0,
            "roe": 150.0,
            "roic": 45.0,
            "debt_to_equity": 1.5,
            "current_ratio": 1.0,
            "rsi_14": 55.0,
            "beta": 1.28,
        },
        "MSFT": {
            "name": "Microsoft Corporation",
            "sector": "Technology",
            "industry": "Software",
            "price": 378.0,
            "market_cap": 2.8e12,
            "pe_ratio": 35.0,
            "pb_ratio": 12.0,
            "ps_ratio": 12.0,
            "dividend_yield": 0.8,
            "revenue_growth": 0.12,
            "gross_margin": 69.0,
            "operating_margin": 42.0,
            "roe": 38.0,
            "roic": 28.0,
            "debt_to_equity": 0.3,
            "current_ratio": 1.8,
            "rsi_14": 62.0,
            "beta": 0.92,
        },
        "JNJ": {
            "name": "Johnson & Johnson",
            "sector": "Healthcare",
            "industry": "Pharmaceuticals",
            "price": 155.0,
            "market_cap": 380e9,
            "pe_ratio": 12.0,
            "pb_ratio": 5.5,
            "ps_ratio": 4.5,
            "dividend_yield": 3.0,
            "revenue_growth": 0.05,
            "gross_margin": 68.0,
            "operating_margin": 25.0,
            "roe": 20.0,
            "roic": 15.0,
            "debt_to_equity": 0.4,
            "current_ratio": 1.2,
            "rsi_14": 45.0,
            "beta": 0.55,
        },
        "XOM": {
            "name": "Exxon Mobil",
            "sector": "Energy",
            "industry": "Oil & Gas",
            "price": 105.0,
            "market_cap": 420e9,
            "pe_ratio": 8.0,
            "pb_ratio": 1.8,
            "ps_ratio": 1.2,
            "dividend_yield": 3.5,
            "revenue_growth": -0.05,
            "gross_margin": 35.0,
            "operating_margin": 15.0,
            "roe": 18.0,
            "roic": 12.0,
            "debt_to_equity": 0.2,
            "current_ratio": 1.4,
            "rsi_14": 38.0,
            "beta": 0.95,
        },
    }


@pytest.fixture
def value_screen():
    """Sample value screen."""
    return Screen(
        name="Test Value Screen",
        filters=[
            FilterCondition(filter_id="pe_ratio", operator=Operator.LT, value=15),
            FilterCondition(filter_id="dividend_yield", operator=Operator.GT, value=2.0),
        ],
    )


# =============================================================================
# Test Filter Registry
# =============================================================================

class TestFilterRegistry:
    """Tests for FilterRegistry."""
    
    def test_get_all_filters(self):
        """Test getting all filters."""
        filters = FILTER_REGISTRY.get_all_filters()
        assert len(filters) >= 50  # Should have 50+ filters
    
    def test_get_filter(self):
        """Test getting a specific filter."""
        pe_filter = FILTER_REGISTRY.get_filter("pe_ratio")
        assert pe_filter is not None
        assert pe_filter.name == "P/E Ratio"
        assert pe_filter.category == FilterCategory.VALUATION
    
    def test_get_filters_by_category(self):
        """Test getting filters by category."""
        valuation_filters = FILTER_REGISTRY.get_filters_by_category(FilterCategory.VALUATION)
        assert len(valuation_filters) >= 5
        assert all(f.category == FilterCategory.VALUATION for f in valuation_filters)
    
    def test_search_filters(self):
        """Test searching filters."""
        results = FILTER_REGISTRY.search_filters("margin")
        assert len(results) >= 3  # gross, operating, net margin


# =============================================================================
# Test Expression Parser
# =============================================================================

class TestExpressionParser:
    """Tests for ExpressionParser."""
    
    def test_arithmetic(self):
        """Test arithmetic operations."""
        parser = ExpressionParser()
        
        assert parser.evaluate("2 + 3", {}) == 5
        assert parser.evaluate("10 - 4", {}) == 6
        assert parser.evaluate("3 * 4", {}) == 12
        assert parser.evaluate("15 / 3", {}) == 5
        assert parser.evaluate("2 ^ 3", {}) == 8
    
    def test_comparison(self):
        """Test comparison operations."""
        parser = ExpressionParser()
        
        assert parser.evaluate("5 > 3", {}) is True
        assert parser.evaluate("3 < 5", {}) is True
        assert parser.evaluate("5 >= 5", {}) is True
        assert parser.evaluate("5 == 5", {}) is True
        assert parser.evaluate("5 != 3", {}) is True
    
    def test_logical(self):
        """Test logical operations."""
        parser = ExpressionParser()
        
        assert parser.evaluate("true and true", {}) is True
        assert parser.evaluate("true and false", {}) is False
        assert parser.evaluate("true or false", {}) is True
        assert parser.evaluate("not false", {}) is True
    
    def test_variables(self):
        """Test variable substitution."""
        parser = ExpressionParser()
        
        result = parser.evaluate("pe_ratio < 20", {"pe_ratio": 15})
        assert result is True
        
        result = parser.evaluate("pe_ratio < 20 and roe > 10", {"pe_ratio": 15, "roe": 20})
        assert result is True
    
    def test_functions(self):
        """Test function calls."""
        parser = ExpressionParser()
        
        assert parser.evaluate("abs(-5)", {}) == 5
        assert parser.evaluate("min(3, 5)", {}) == 3
        assert parser.evaluate("max(3, 5)", {}) == 5
        assert parser.evaluate("sqrt(16)", {}) == 4
    
    def test_complex_expression(self):
        """Test complex expressions."""
        parser = ExpressionParser()
        
        expr = "(pe_ratio < 20 and roe > 15) or dividend_yield > 5"
        result = parser.evaluate(expr, {"pe_ratio": 15, "roe": 20, "dividend_yield": 3})
        assert result is True
    
    def test_get_variables(self):
        """Test extracting variables from expression."""
        parser = ExpressionParser()
        
        variables = parser.get_variables("pe_ratio < 20 and revenue_growth > 0.1")
        assert "pe_ratio" in variables
        assert "revenue_growth" in variables
    
    def test_validate(self):
        """Test expression validation."""
        parser = ExpressionParser()
        
        is_valid, error = parser.validate("pe_ratio < 20")
        assert is_valid is True
        
        is_valid, error = parser.validate("pe_ratio <")
        assert is_valid is False


# =============================================================================
# Test Filter Condition
# =============================================================================

class TestFilterCondition:
    """Tests for FilterCondition."""
    
    def test_evaluate_gte(self):
        """Test greater than or equal."""
        cond = FilterCondition(filter_id="pe_ratio", operator=Operator.GTE, value=10)
        assert cond.evaluate(15) is True
        assert cond.evaluate(10) is True
        assert cond.evaluate(5) is False
    
    def test_evaluate_between(self):
        """Test between operator."""
        cond = FilterCondition(filter_id="pe_ratio", operator=Operator.BETWEEN, value=10, value2=20)
        assert cond.evaluate(15) is True
        assert cond.evaluate(10) is True
        assert cond.evaluate(20) is True
        assert cond.evaluate(5) is False
        assert cond.evaluate(25) is False
    
    def test_evaluate_in(self):
        """Test in operator."""
        cond = FilterCondition(filter_id="sector", operator=Operator.IN, value=["Technology", "Healthcare"])
        assert cond.evaluate("Technology") is True
        assert cond.evaluate("Energy") is False


# =============================================================================
# Test Screener Engine
# =============================================================================

class TestScreenerEngine:
    """Tests for ScreenerEngine."""
    
    def test_run_screen(self, sample_stock_data, value_screen):
        """Test running a screen."""
        engine = ScreenerEngine()
        result = engine.run_screen(value_screen, sample_stock_data)
        
        assert result.total_universe == 4
        assert result.matches >= 1
        
        # JNJ and XOM should match (low PE, high dividend)
        symbols = [m.symbol for m in result.stocks]
        assert "JNJ" in symbols or "XOM" in symbols
    
    def test_filter_by_sector(self, sample_stock_data):
        """Test filtering by sector."""
        screen = Screen(
            name="Tech Screen",
            sectors=["Technology"],
            filters=[],
        )
        
        engine = ScreenerEngine()
        result = engine.run_screen(screen, sample_stock_data)
        
        assert result.matches == 2  # AAPL and MSFT
        symbols = [m.symbol for m in result.stocks]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
    
    def test_filter_by_market_cap(self, sample_stock_data):
        """Test filtering by market cap."""
        screen = Screen(
            name="Large Cap",
            market_cap_min=1e12,
            filters=[],
        )
        
        engine = ScreenerEngine()
        result = engine.run_screen(screen, sample_stock_data)
        
        assert result.matches == 2  # AAPL and MSFT have >$1T market cap
    
    def test_custom_formula(self, sample_stock_data):
        """Test custom formula filtering."""
        screen = Screen(
            name="Custom",
            filters=[],
            custom_formulas=[
                CustomFormula(
                    name="Quality",
                    expression="roe > 20 and debt_to_equity < 1",
                )
            ],
        )
        
        engine = ScreenerEngine()
        result = engine.run_screen(screen, sample_stock_data)
        
        # MSFT should match
        symbols = [m.symbol for m in result.stocks]
        assert "MSFT" in symbols
    
    def test_validate_screen(self):
        """Test screen validation."""
        engine = ScreenerEngine()
        
        # Valid screen
        screen = Screen(
            name="Valid",
            filters=[
                FilterCondition(filter_id="pe_ratio", operator=Operator.LT, value=20),
            ],
        )
        is_valid, errors = engine.validate_screen(screen)
        assert is_valid is True
        
        # Invalid filter
        screen = Screen(
            name="Invalid",
            filters=[
                FilterCondition(filter_id="invalid_filter", operator=Operator.LT, value=20),
            ],
        )
        is_valid, errors = engine.validate_screen(screen)
        assert is_valid is False


# =============================================================================
# Test Preset Screens
# =============================================================================

class TestPresetScreens:
    """Tests for preset screens."""
    
    def test_get_preset_screens(self):
        """Test getting preset screens."""
        presets = get_preset_screens()
        assert len(presets) >= 10
    
    def test_preset_registry(self):
        """Test preset screen registry."""
        assert "preset_deep_value" in PRESET_SCREENS
        assert "preset_buffett" in PRESET_SCREENS
        assert "preset_high_growth" in PRESET_SCREENS
    
    def test_run_preset_screen(self, sample_stock_data):
        """Test running a preset screen."""
        engine = ScreenerEngine()
        
        # Run deep value screen
        screen = PRESET_SCREENS["preset_deep_value"]
        result = engine.run_screen(screen, sample_stock_data)
        
        # Should find at least XOM (PE < 10, Div > 2%)
        assert result.matches >= 1


# =============================================================================
# Test Screen Manager
# =============================================================================

class TestScreenManager:
    """Tests for ScreenManager."""
    
    def test_save_and_get(self, value_screen):
        """Test saving and retrieving screens."""
        manager = ScreenManager()
        
        screen_id = manager.save_screen(value_screen)
        retrieved = manager.get_screen(screen_id)
        
        assert retrieved is not None
        assert retrieved.name == value_screen.name
    
    def test_delete(self, value_screen):
        """Test deleting screens."""
        manager = ScreenManager()
        
        screen_id = manager.save_screen(value_screen)
        assert manager.delete_screen(screen_id) is True
        assert manager.get_screen(screen_id) is None
    
    def test_duplicate(self, value_screen):
        """Test duplicating screens."""
        manager = ScreenManager()
        
        manager.save_screen(value_screen)
        duplicate = manager.duplicate_screen(value_screen.screen_id, "Copy of Screen")
        
        assert duplicate is not None
        assert duplicate.name == "Copy of Screen"
        assert duplicate.screen_id != value_screen.screen_id


# =============================================================================
# Test Screen Alerts
# =============================================================================

class TestScreenAlertManager:
    """Tests for ScreenAlertManager."""
    
    def test_add_alert(self, value_screen):
        """Test adding an alert."""
        manager = ScreenAlertManager()
        
        alert = manager.add_alert(value_screen, AlertType.ENTRY)
        
        assert alert is not None
        assert alert.screen_id == value_screen.screen_id
        assert alert.alert_type == AlertType.ENTRY
    
    def test_check_alerts(self, value_screen, sample_stock_data):
        """Test checking alerts."""
        manager = ScreenAlertManager()
        
        # Add alert
        manager.add_alert(value_screen, AlertType.ENTRY)
        
        # First run - should trigger entry alert
        notifications = manager.check_alerts(sample_stock_data)
        assert len(notifications) >= 1
        
        # Second run with same data - no new entries
        notifications = manager.check_alerts(sample_stock_data)
        assert len(notifications) == 0


# =============================================================================
# Test Screen Backtester
# =============================================================================

class TestScreenBacktester:
    """Tests for ScreenBacktester."""
    
    def test_run_backtest(self, value_screen, sample_stock_data):
        """Test running a backtest."""
        # Create historical data (simplified)
        historical_data = {
            date(2024, 1, 1): sample_stock_data,
            date(2024, 1, 2): sample_stock_data,
            date(2024, 1, 3): sample_stock_data,
            date(2024, 1, 4): sample_stock_data,
            date(2024, 1, 5): sample_stock_data,
        }
        
        backtester = ScreenBacktester()
        result = backtester.run(value_screen, historical_data)
        
        assert result is not None
        assert result.screen_id == value_screen.screen_id
        assert len(result.equity_curve) > 0
