"""Tests for PRD-62: Advanced Charting."""

import pytest
from datetime import datetime, timezone, timedelta

from src.charting import (
    ChartType,
    Timeframe,
    DrawingType,
    IndicatorCategory,
    LineStyle,
    ChartConfig,
    DEFAULT_CHART_CONFIG,
    ChartLayout,
    Drawing,
    IndicatorConfig,
    ChartTemplate,
    OHLCV,
    IndicatorResult,
    IndicatorEngine,
    DrawingManager,
    LayoutManager,
)
from src.charting.models import Point, DrawingStyle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_ohlcv_data() -> list[OHLCV]:
    """Generate sample OHLCV data for testing."""
    data = []
    base_price = 100.0
    base_time = datetime.now(timezone.utc) - timedelta(days=100)

    for i in range(100):
        timestamp = base_time + timedelta(days=i)
        change = (i % 5 - 2) * 0.5
        open_price = base_price + change
        high_price = open_price + 2
        low_price = open_price - 1
        close_price = open_price + 1
        volume = 1000000 + i * 10000

        data.append(OHLCV(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        ))

        base_price = close_price

    return data


@pytest.fixture
def indicator_engine() -> IndicatorEngine:
    """Create an IndicatorEngine instance."""
    return IndicatorEngine()


@pytest.fixture
def drawing_manager() -> DrawingManager:
    """Create a DrawingManager instance."""
    return DrawingManager()


@pytest.fixture
def layout_manager() -> LayoutManager:
    """Create a LayoutManager instance."""
    return LayoutManager()


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------


class TestConfig:
    """Test configuration enums and defaults."""

    def test_chart_types(self):
        """Test ChartType enum values."""
        assert ChartType.CANDLESTICK.value == "candlestick"
        assert ChartType.LINE.value == "line"
        assert ChartType.HEIKIN_ASHI.value == "heikin_ashi"
        assert len(ChartType) == 7

    def test_timeframes(self):
        """Test Timeframe enum values."""
        assert Timeframe.M1.value == "1m"
        assert Timeframe.H1.value == "1h"
        assert Timeframe.D1.value == "1d"
        assert Timeframe.W1.value == "1w"
        assert len(Timeframe) == 9

    def test_drawing_types(self):
        """Test DrawingType enum values."""
        assert DrawingType.TRENDLINE.value == "trendline"
        assert DrawingType.FIBONACCI_RETRACEMENT.value == "fib_retracement"
        assert DrawingType.HORIZONTAL_LINE.value == "horizontal_line"
        assert len(DrawingType) >= 10

    def test_indicator_categories(self):
        """Test IndicatorCategory enum values."""
        assert IndicatorCategory.TREND.value == "trend"
        assert IndicatorCategory.MOMENTUM.value == "momentum"
        assert IndicatorCategory.VOLUME.value == "volume"
        assert len(IndicatorCategory) == 6

    def test_line_styles(self):
        """Test LineStyle enum values."""
        assert LineStyle.SOLID.value == "solid"
        assert LineStyle.DASHED.value == "dashed"
        assert LineStyle.DOTTED.value == "dotted"

    def test_default_chart_config(self):
        """Test default chart configuration."""
        config = DEFAULT_CHART_CONFIG
        assert config.default_chart_type == ChartType.CANDLESTICK
        assert config.default_timeframe == Timeframe.D1
        assert config.show_volume is True
        assert config.max_indicators == 10


# ---------------------------------------------------------------------------
# Models Tests
# ---------------------------------------------------------------------------


class TestModels:
    """Test data models."""

    def test_ohlcv(self):
        """Test OHLCV model."""
        now = datetime.now(timezone.utc)
        bar = OHLCV(
            timestamp=now,
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000000,
        )

        assert bar.open == 100.0
        assert bar.high == 105.0
        assert bar.low == 98.0
        assert bar.close == 103.0
        assert bar.volume == 1000000

        d = bar.to_dict()
        assert "timestamp" in d
        assert d["open"] == 100.0

    def test_point(self):
        """Test Point model."""
        now = datetime.now(timezone.utc)
        point = Point(timestamp=now, price=150.0)

        assert point.price == 150.0
        d = point.to_dict()
        assert d["price"] == 150.0

    def test_drawing_style(self):
        """Test DrawingStyle model."""
        style = DrawingStyle(
            color="#FF0000",
            line_width=2,
            line_style=LineStyle.DASHED,
            fill_color="#0000FF",
            fill_opacity=0.5,
        )

        assert style.color == "#FF0000"
        assert style.line_width == 2
        assert style.line_style == LineStyle.DASHED

        d = style.to_dict()
        assert d["color"] == "#FF0000"
        assert d["line_style"] == "dashed"

    def test_drawing(self):
        """Test Drawing model."""
        now = datetime.now(timezone.utc)
        drawing = Drawing(
            drawing_type=DrawingType.TRENDLINE,
            symbol="AAPL",
            label="Support Line",
        )

        drawing.add_point(now - timedelta(days=10), 140.0)
        drawing.add_point(now, 150.0)

        assert drawing.drawing_type == DrawingType.TRENDLINE
        assert drawing.symbol == "AAPL"
        assert len(drawing.points) == 2
        assert drawing.label == "Support Line"

        d = drawing.to_dict()
        assert d["symbol"] == "AAPL"
        assert len(d["points"]) == 2

    def test_drawing_move(self):
        """Test moving a drawing."""
        now = datetime.now(timezone.utc)
        drawing = Drawing(
            drawing_type=DrawingType.HORIZONTAL_LINE,
            symbol="AAPL",
        )
        drawing.add_point(now, 150.0)

        original_price = drawing.points[0].price
        drawing.move(0, 10.0)

        assert drawing.points[0].price == original_price + 10.0

    def test_indicator_config(self):
        """Test IndicatorConfig model."""
        config = IndicatorConfig(
            indicator_id="sma_1",
            name="SMA",
            params={"period": 20},
            color="#2196F3",
        )

        assert config.name == "SMA"
        assert config.params["period"] == 20

        d = config.to_dict()
        assert d["name"] == "SMA"

    def test_indicator_result(self):
        """Test IndicatorResult model."""
        now = datetime.now(timezone.utc)
        result = IndicatorResult(
            name="SMA",
            values={"sma": [100.0, 101.0, 102.0]},
            timestamps=[now - timedelta(days=2), now - timedelta(days=1), now],
            params={"period": 20},
            is_overlay=True,
        )

        assert result.name == "SMA"
        assert len(result.values["sma"]) == 3
        assert result.is_overlay is True

    def test_chart_layout(self):
        """Test ChartLayout model."""
        layout = ChartLayout(
            user_id="user_1",
            name="My Layout",
            symbol="AAPL",
            timeframe=Timeframe.D1,
            chart_type=ChartType.CANDLESTICK,
        )

        assert layout.name == "My Layout"
        assert layout.symbol == "AAPL"
        assert len(layout.indicators) == 0
        assert len(layout.drawings) == 0

        config = IndicatorConfig(
            indicator_id="sma_1",
            name="SMA",
            params={"period": 20},
        )
        layout.add_indicator(config)
        assert len(layout.indicators) == 1

        result = layout.remove_indicator("sma_1")
        assert result is True
        assert len(layout.indicators) == 0

    def test_chart_template(self):
        """Test ChartTemplate model."""
        template = ChartTemplate(
            name="Trend Following",
            category="Trading",
            config={"chart_type": "candlestick"},
            indicators=[{"name": "SMA", "params": {"period": 20}}],
        )

        assert template.name == "Trend Following"
        assert template.usage_count == 0

        template.increment_usage()
        assert template.usage_count == 1

        template.add_rating(4.0)
        template.add_rating(5.0)
        assert template.rating_count == 2
        assert template.rating == 4.5


# ---------------------------------------------------------------------------
# Indicator Engine Tests
# ---------------------------------------------------------------------------


class TestIndicatorEngine:
    """Test indicator calculations."""

    def test_get_available_indicators(self, indicator_engine: IndicatorEngine):
        """Test getting available indicators."""
        indicators = indicator_engine.get_available_indicators()

        assert len(indicators) >= 10

        for ind in indicators:
            assert "id" in ind
            assert "name" in ind
            assert "category" in ind
            assert "params" in ind
            assert "overlay" in ind

    def test_get_indicators_by_category(self, indicator_engine: IndicatorEngine):
        """Test filtering indicators by category."""
        trend_indicators = indicator_engine.get_indicators_by_category(IndicatorCategory.TREND)

        assert len(trend_indicators) >= 3
        for ind in trend_indicators:
            assert ind["category"] == "trend"

    def test_calculate_sma(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test SMA calculation."""
        result = indicator_engine.calculate("SMA", sample_ohlcv_data, {"period": 20})

        assert result.name == "SMA"
        assert "sma" in result.values
        assert len(result.values["sma"]) == len(sample_ohlcv_data)
        assert result.is_overlay is True

        import math
        for i in range(19):
            assert math.isnan(result.values["sma"][i])

        assert not math.isnan(result.values["sma"][19])

    def test_calculate_ema(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test EMA calculation."""
        result = indicator_engine.calculate("EMA", sample_ohlcv_data, {"period": 10})

        assert result.name == "EMA"
        assert "ema" in result.values
        assert len(result.values["ema"]) == len(sample_ohlcv_data)

    def test_calculate_bb(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test Bollinger Bands calculation."""
        result = indicator_engine.calculate("BB", sample_ohlcv_data)

        assert "middle" in result.values
        assert "upper" in result.values
        assert "lower" in result.values

        import math
        for i in range(20, len(sample_ohlcv_data)):
            if not math.isnan(result.values["middle"][i]):
                assert result.values["upper"][i] > result.values["middle"][i]
                assert result.values["lower"][i] < result.values["middle"][i]

    def test_calculate_rsi(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test RSI calculation."""
        result = indicator_engine.calculate("RSI", sample_ohlcv_data, {"period": 14})

        assert result.name == "RSI"
        assert "rsi" in result.values
        assert result.is_overlay is False

        import math
        for val in result.values["rsi"]:
            if not math.isnan(val):
                assert 0 <= val <= 100

    def test_calculate_macd(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test MACD calculation."""
        result = indicator_engine.calculate("MACD", sample_ohlcv_data)

        assert "macd" in result.values
        assert "signal" in result.values
        assert "histogram" in result.values
        assert result.is_overlay is False

    def test_calculate_stoch(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test Stochastic calculation."""
        result = indicator_engine.calculate("STOCH", sample_ohlcv_data)

        assert "k" in result.values
        assert "d" in result.values

        import math
        for val in result.values["k"]:
            if not math.isnan(val):
                assert 0 <= val <= 100

    def test_calculate_atr(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test ATR calculation."""
        result = indicator_engine.calculate("ATR", sample_ohlcv_data, {"period": 14})

        assert "atr" in result.values

        import math
        for val in result.values["atr"]:
            if not math.isnan(val):
                assert val >= 0

    def test_calculate_obv(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test OBV calculation."""
        result = indicator_engine.calculate("OBV", sample_ohlcv_data)

        assert "obv" in result.values
        assert len(result.values["obv"]) == len(sample_ohlcv_data)
        assert result.values["obv"][0] == 0

    def test_calculate_vwap(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test VWAP calculation."""
        result = indicator_engine.calculate("VWAP", sample_ohlcv_data)

        assert "vwap" in result.values
        assert result.is_overlay is True

    def test_calculate_unknown_indicator(self, indicator_engine: IndicatorEngine, sample_ohlcv_data: list[OHLCV]):
        """Test calculating unknown indicator raises error."""
        with pytest.raises(ValueError, match="Unknown indicator"):
            indicator_engine.calculate("UNKNOWN", sample_ohlcv_data)


# ---------------------------------------------------------------------------
# Drawing Manager Tests
# ---------------------------------------------------------------------------


class TestDrawingManager:
    """Test drawing management."""

    def test_create_trendline(self, drawing_manager: DrawingManager):
        """Test creating a trendline."""
        now = datetime.now(timezone.utc)
        drawing = drawing_manager.create_trendline(
            symbol="AAPL",
            start=(now - timedelta(days=10), 140.0),
            end=(now, 150.0),
            color="#FF0000",
            line_width=2,
            extend_right=True,
        )

        assert drawing.drawing_type == DrawingType.TRENDLINE
        assert drawing.symbol == "AAPL"
        assert len(drawing.points) == 2
        assert drawing.style.color == "#FF0000"
        assert drawing.style.line_width == 2
        assert drawing.properties["extend_right"] is True

    def test_create_horizontal_line(self, drawing_manager: DrawingManager):
        """Test creating a horizontal line."""
        drawing = drawing_manager.create_horizontal_line(
            symbol="AAPL",
            price=150.0,
            color="#FF9800",
            line_style=LineStyle.DASHED,
        )

        assert drawing.drawing_type == DrawingType.HORIZONTAL_LINE
        assert drawing.points[0].price == 150.0
        assert drawing.style.line_style == LineStyle.DASHED

    def test_create_vertical_line(self, drawing_manager: DrawingManager):
        """Test creating a vertical line."""
        now = datetime.now(timezone.utc)
        drawing = drawing_manager.create_vertical_line(
            symbol="AAPL",
            timestamp=now,
            color="#9C27B0",
        )

        assert drawing.drawing_type == DrawingType.VERTICAL_LINE
        assert len(drawing.points) == 1

    def test_create_fibonacci_retracement(self, drawing_manager: DrawingManager):
        """Test creating Fibonacci retracement."""
        now = datetime.now(timezone.utc)
        drawing = drawing_manager.create_fibonacci_retracement(
            symbol="AAPL",
            start=(now - timedelta(days=30), 130.0),
            end=(now, 160.0),
            levels=[0, 0.236, 0.382, 0.5, 0.618, 1.0],
        )

        assert drawing.drawing_type == DrawingType.FIBONACCI_RETRACEMENT
        assert len(drawing.points) == 2
        assert drawing.properties["levels"] == [0, 0.236, 0.382, 0.5, 0.618, 1.0]

    def test_create_rectangle(self, drawing_manager: DrawingManager):
        """Test creating a rectangle."""
        now = datetime.now(timezone.utc)
        drawing = drawing_manager.create_rectangle(
            symbol="AAPL",
            top_left=(now - timedelta(days=10), 160.0),
            bottom_right=(now, 140.0),
            color="#4CAF50",
            fill_opacity=0.3,
        )

        assert drawing.drawing_type == DrawingType.RECTANGLE
        assert len(drawing.points) == 2
        assert drawing.style.fill_opacity == 0.3

    def test_create_text(self, drawing_manager: DrawingManager):
        """Test creating text annotation."""
        now = datetime.now(timezone.utc)
        drawing = drawing_manager.create_text(
            symbol="AAPL",
            position=(now, 150.0),
            text="Buy Signal",
            font_size=14,
        )

        assert drawing.drawing_type == DrawingType.TEXT
        assert drawing.properties["text"] == "Buy Signal"
        assert drawing.style.font_size == 14

    def test_create_channel(self, drawing_manager: DrawingManager):
        """Test creating a channel."""
        now = datetime.now(timezone.utc)
        drawing = drawing_manager.create_channel(
            symbol="AAPL",
            start1=(now - timedelta(days=20), 140.0),
            end1=(now, 150.0),
            start2=(now - timedelta(days=20), 145.0),
            end2=(now, 155.0),
        )

        assert drawing.drawing_type == DrawingType.CHANNEL
        assert len(drawing.points) == 4

    def test_create_arrow(self, drawing_manager: DrawingManager):
        """Test creating an arrow."""
        now = datetime.now(timezone.utc)
        drawing = drawing_manager.create_arrow(
            symbol="AAPL",
            start=(now - timedelta(days=5), 140.0),
            end=(now, 150.0),
        )

        assert drawing.drawing_type == DrawingType.ARROW
        assert len(drawing.points) == 2

    def test_add_and_get_drawings(self, drawing_manager: DrawingManager):
        """Test adding and getting drawings."""
        layout_id = "layout_1"

        drawing1 = drawing_manager.create_horizontal_line("AAPL", 150.0)
        drawing2 = drawing_manager.create_horizontal_line("AAPL", 145.0)
        drawing3 = drawing_manager.create_horizontal_line("MSFT", 300.0)

        drawing_manager.add_drawing(layout_id, drawing1)
        drawing_manager.add_drawing(layout_id, drawing2)
        drawing_manager.add_drawing(layout_id, drawing3)

        all_drawings = drawing_manager.get_drawings(layout_id)
        assert len(all_drawings) == 3

        aapl_drawings = drawing_manager.get_drawings(layout_id, symbol="AAPL")
        assert len(aapl_drawings) == 2

    def test_get_drawing(self, drawing_manager: DrawingManager):
        """Test getting a specific drawing."""
        layout_id = "layout_1"
        drawing = drawing_manager.create_horizontal_line("AAPL", 150.0)
        drawing_manager.add_drawing(layout_id, drawing)

        retrieved = drawing_manager.get_drawing(layout_id, drawing.drawing_id)
        assert retrieved is not None
        assert retrieved.drawing_id == drawing.drawing_id

        not_found = drawing_manager.get_drawing(layout_id, "non_existent")
        assert not_found is None

    def test_update_drawing(self, drawing_manager: DrawingManager):
        """Test updating a drawing."""
        layout_id = "layout_1"
        now = datetime.now(timezone.utc)
        drawing = drawing_manager.create_horizontal_line("AAPL", 150.0)
        drawing_manager.add_drawing(layout_id, drawing)

        new_points = [(now, 155.0)]
        updated = drawing_manager.update_drawing(
            layout_id,
            drawing.drawing_id,
            points=new_points,
        )

        assert updated is not None
        assert updated.points[0].price == 155.0

        new_style = DrawingStyle(color="#00FF00", line_width=3)
        updated = drawing_manager.update_drawing(
            layout_id,
            drawing.drawing_id,
            style=new_style,
        )
        assert updated.style.color == "#00FF00"

    def test_delete_drawing(self, drawing_manager: DrawingManager):
        """Test deleting a drawing."""
        layout_id = "layout_1"
        drawing = drawing_manager.create_horizontal_line("AAPL", 150.0)
        drawing_manager.add_drawing(layout_id, drawing)

        result = drawing_manager.delete_drawing(layout_id, drawing.drawing_id)
        assert result is True

        drawings = drawing_manager.get_drawings(layout_id)
        assert len(drawings) == 0

        result = drawing_manager.delete_drawing(layout_id, "non_existent")
        assert result is False

    def test_clear_drawings(self, drawing_manager: DrawingManager):
        """Test clearing drawings."""
        layout_id = "layout_1"

        drawing_manager.add_drawing(layout_id, drawing_manager.create_horizontal_line("AAPL", 150.0))
        drawing_manager.add_drawing(layout_id, drawing_manager.create_horizontal_line("AAPL", 145.0))
        drawing_manager.add_drawing(layout_id, drawing_manager.create_horizontal_line("MSFT", 300.0))

        cleared = drawing_manager.clear_drawings(layout_id, symbol="AAPL")
        assert cleared == 2

        remaining = drawing_manager.get_drawings(layout_id)
        assert len(remaining) == 1

        cleared = drawing_manager.clear_drawings(layout_id)
        assert cleared == 1

    def test_duplicate_drawing(self, drawing_manager: DrawingManager):
        """Test duplicating a drawing."""
        layout_id = "layout_1"
        original = drawing_manager.create_horizontal_line("AAPL", 150.0, color="#FF0000")
        drawing_manager.add_drawing(layout_id, original)

        duplicate = drawing_manager.duplicate_drawing(layout_id, original.drawing_id)

        assert duplicate is not None
        assert duplicate.drawing_id != original.drawing_id
        assert duplicate.style.color == original.style.color
        assert len(duplicate.points) == len(original.points)

    def test_calculate_fib_levels(self, drawing_manager: DrawingManager):
        """Test Fibonacci level calculation."""
        levels = drawing_manager.calculate_fib_levels(100.0, 200.0)

        assert 0 in levels
        assert 0.5 in levels
        assert 1.0 in levels

        assert levels[0] == 100.0
        assert levels[0.5] == 150.0
        assert levels[1.0] == 200.0

    def test_get_stats(self, drawing_manager: DrawingManager):
        """Test getting drawing statistics."""
        layout_id = "layout_1"

        drawing_manager.add_drawing(layout_id, drawing_manager.create_horizontal_line("AAPL", 150.0))
        drawing_manager.add_drawing(layout_id, drawing_manager.create_trendline(
            "AAPL",
            (datetime.now(timezone.utc), 140.0),
            (datetime.now(timezone.utc), 150.0),
        ))

        stats = drawing_manager.get_stats()

        assert stats["total_drawings"] == 2
        assert stats["layouts_with_drawings"] == 1
        assert "horizontal_line" in stats["by_type"]
        assert "trendline" in stats["by_type"]


# ---------------------------------------------------------------------------
# Layout Manager Tests
# ---------------------------------------------------------------------------


class TestLayoutManager:
    """Test layout management."""

    def test_create_layout(self, layout_manager: LayoutManager):
        """Test creating a layout."""
        layout = layout_manager.create_layout(
            user_id="user_1",
            name="My Layout",
            symbol="AAPL",
            timeframe=Timeframe.D1,
            chart_type=ChartType.CANDLESTICK,
        )

        assert layout.name == "My Layout"
        assert layout.symbol == "AAPL"
        assert layout.timeframe == Timeframe.D1

    def test_get_layout(self, layout_manager: LayoutManager):
        """Test getting a layout."""
        layout = layout_manager.create_layout(
            user_id="user_1",
            name="My Layout",
        )

        retrieved = layout_manager.get_layout("user_1", layout.layout_id)
        assert retrieved is not None
        assert retrieved.name == "My Layout"

        not_found = layout_manager.get_layout("user_1", "non_existent")
        assert not_found is None

    def test_get_layouts(self, layout_manager: LayoutManager):
        """Test getting all layouts for a user."""
        layout_manager.create_layout(user_id="user_1", name="Layout 1")
        layout_manager.create_layout(user_id="user_1", name="Layout 2")
        layout_manager.create_layout(user_id="user_2", name="Layout 3")

        user1_layouts = layout_manager.get_layouts("user_1")
        assert len(user1_layouts) == 2

        user2_layouts = layout_manager.get_layouts("user_2")
        assert len(user2_layouts) == 1

    def test_set_default_layout(self, layout_manager: LayoutManager):
        """Test setting a default layout."""
        layout1 = layout_manager.create_layout(user_id="user_1", name="Layout 1")
        layout2 = layout_manager.create_layout(user_id="user_1", name="Layout 2")

        result = layout_manager.set_default_layout("user_1", layout1.layout_id)
        assert result is True

        default = layout_manager.get_default_layout("user_1")
        assert default.layout_id == layout1.layout_id

        layout_manager.set_default_layout("user_1", layout2.layout_id)
        default = layout_manager.get_default_layout("user_1")
        assert default.layout_id == layout2.layout_id

        assert layout1.is_default is False

    def test_update_layout(self, layout_manager: LayoutManager):
        """Test updating a layout."""
        layout = layout_manager.create_layout(
            user_id="user_1",
            name="Original Name",
            symbol="AAPL",
        )

        updated = layout_manager.update_layout(
            "user_1",
            layout.layout_id,
            name="New Name",
            symbol="MSFT",
            timeframe=Timeframe.H1,
        )

        assert updated is not None
        assert updated.name == "New Name"
        assert updated.symbol == "MSFT"
        assert updated.timeframe == Timeframe.H1

    def test_delete_layout(self, layout_manager: LayoutManager):
        """Test deleting a layout."""
        layout = layout_manager.create_layout(user_id="user_1", name="To Delete")

        result = layout_manager.delete_layout("user_1", layout.layout_id)
        assert result is True

        layouts = layout_manager.get_layouts("user_1")
        assert len(layouts) == 0

        result = layout_manager.delete_layout("user_1", "non_existent")
        assert result is False

    def test_duplicate_layout(self, layout_manager: LayoutManager):
        """Test duplicating a layout."""
        original = layout_manager.create_layout(
            user_id="user_1",
            name="Original",
            symbol="AAPL",
        )

        config = IndicatorConfig(
            indicator_id="sma_1",
            name="SMA",
            params={"period": 20},
        )
        layout_manager.add_indicator("user_1", original.layout_id, config)

        duplicate = layout_manager.duplicate_layout(
            "user_1",
            original.layout_id,
            "Copy of Original",
        )

        assert duplicate is not None
        assert duplicate.name == "Copy of Original"
        assert duplicate.symbol == original.symbol
        assert len(duplicate.indicators) == 1

    def test_add_remove_indicator(self, layout_manager: LayoutManager):
        """Test adding and removing indicators from layout."""
        layout = layout_manager.create_layout(user_id="user_1", name="My Layout")

        config = IndicatorConfig(
            indicator_id="sma_1",
            name="SMA",
            params={"period": 20},
        )

        result = layout_manager.add_indicator("user_1", layout.layout_id, config)
        assert result is True
        assert len(layout.indicators) == 1

        result = layout_manager.remove_indicator("user_1", layout.layout_id, "sma_1")
        assert result is True
        assert len(layout.indicators) == 0

    def test_update_indicator(self, layout_manager: LayoutManager):
        """Test updating an indicator."""
        layout = layout_manager.create_layout(user_id="user_1", name="My Layout")

        config = IndicatorConfig(
            indicator_id="sma_1",
            name="SMA",
            params={"period": 20},
            color="#2196F3",
        )
        layout_manager.add_indicator("user_1", layout.layout_id, config)

        result = layout_manager.update_indicator(
            "user_1",
            layout.layout_id,
            "sma_1",
            params={"period": 50},
            color="#FF0000",
        )

        assert result is True
        assert layout.indicators[0].params["period"] == 50
        assert layout.indicators[0].color == "#FF0000"

    def test_add_remove_drawing(self, layout_manager: LayoutManager):
        """Test adding and removing drawings from layout."""
        layout = layout_manager.create_layout(user_id="user_1", name="My Layout")

        drawing = Drawing(
            drawing_type=DrawingType.HORIZONTAL_LINE,
            symbol="AAPL",
        )

        result = layout_manager.add_drawing("user_1", layout.layout_id, drawing)
        assert result is True
        assert len(layout.drawings) == 1

        result = layout_manager.remove_drawing("user_1", layout.layout_id, drawing.drawing_id)
        assert result is True
        assert len(layout.drawings) == 0

    def test_builtin_templates(self, layout_manager: LayoutManager):
        """Test built-in templates exist."""
        templates = layout_manager.get_templates()
        assert len(templates) >= 3

        featured = layout_manager.get_featured_templates()
        assert len(featured) >= 2

        trend = layout_manager.get_template("trend_following")
        assert trend is not None
        assert trend.name == "Trend Following"
        assert len(trend.indicators) >= 2

    def test_create_template(self, layout_manager: LayoutManager):
        """Test creating a custom template."""
        template = layout_manager.create_template(
            name="My Template",
            category="Custom",
            config={"chart_type": "candlestick"},
            indicators=[{"name": "RSI", "params": {"period": 14}}],
            description="My custom template",
            created_by="user_1",
        )

        assert template.name == "My Template"
        assert template.category == "Custom"
        assert len(template.indicators) == 1

    def test_apply_template(self, layout_manager: LayoutManager):
        """Test applying a template to a layout."""
        layout = layout_manager.create_layout(user_id="user_1", name="My Layout")

        result = layout_manager.apply_template(
            "user_1",
            layout.layout_id,
            "trend_following",
        )

        assert result is True
        assert len(layout.indicators) > 0

        template = layout_manager.get_template("trend_following")
        assert template.usage_count > 0

    def test_rate_template(self, layout_manager: LayoutManager):
        """Test rating a template."""
        template = layout_manager.get_template("trend_following")
        original_count = template.rating_count

        result = layout_manager.rate_template("trend_following", 5)
        assert result is True
        assert template.rating_count == original_count + 1

    def test_save_layout_as_template(self, layout_manager: LayoutManager):
        """Test saving a layout as a template."""
        layout = layout_manager.create_layout(
            user_id="user_1",
            name="My Layout",
            symbol="AAPL",
        )

        config = IndicatorConfig(
            indicator_id="rsi_1",
            name="RSI",
            params={"period": 14},
        )
        layout_manager.add_indicator("user_1", layout.layout_id, config)

        template = layout_manager.save_layout_as_template(
            "user_1",
            layout.layout_id,
            "My Saved Template",
            "Custom",
        )

        assert template is not None
        assert template.name == "My Saved Template"
        assert template.category == "Custom"
        assert len(template.indicators) == 1
        assert template.created_by == "user_1"

    def test_get_stats(self, layout_manager: LayoutManager):
        """Test getting layout statistics."""
        layout_manager.create_layout(user_id="user_1", name="Layout 1")
        layout_manager.create_layout(user_id="user_1", name="Layout 2")

        user_stats = layout_manager.get_stats("user_1")
        assert user_stats["total_layouts"] == 2

        global_stats = layout_manager.get_stats()
        assert global_stats["total_layouts"] >= 2
        assert global_stats["total_templates"] >= 3


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_workflow(
        self,
        indicator_engine: IndicatorEngine,
        drawing_manager: DrawingManager,
        layout_manager: LayoutManager,
        sample_ohlcv_data: list[OHLCV],
    ):
        """Test full charting workflow."""
        layout = layout_manager.create_layout(
            user_id="user_1",
            name="AAPL Analysis",
            symbol="AAPL",
            timeframe=Timeframe.D1,
        )

        sma_config = IndicatorConfig(
            indicator_id="sma_20",
            name="SMA",
            params={"period": 20},
        )
        layout_manager.add_indicator("user_1", layout.layout_id, sma_config)

        rsi_config = IndicatorConfig(
            indicator_id="rsi_14",
            name="RSI",
            params={"period": 14},
        )
        layout_manager.add_indicator("user_1", layout.layout_id, rsi_config)

        sma_result = indicator_engine.calculate("SMA", sample_ohlcv_data, {"period": 20})
        rsi_result = indicator_engine.calculate("RSI", sample_ohlcv_data, {"period": 14})

        assert len(sma_result.values["sma"]) == len(sample_ohlcv_data)
        assert len(rsi_result.values["rsi"]) == len(sample_ohlcv_data)

        now = datetime.now(timezone.utc)

        support_line = drawing_manager.create_horizontal_line(
            symbol="AAPL",
            price=sample_ohlcv_data[50].low,
            color="#00FF00",
        )
        drawing_manager.add_drawing(layout.layout_id, support_line)

        resistance_line = drawing_manager.create_horizontal_line(
            symbol="AAPL",
            price=sample_ohlcv_data[50].high,
            color="#FF0000",
        )
        drawing_manager.add_drawing(layout.layout_id, resistance_line)

        assert len(layout.indicators) == 2

        drawings = drawing_manager.get_drawings(layout.layout_id, "AAPL")
        assert len(drawings) == 2

        layout_manager.apply_template("user_1", layout.layout_id, "momentum")

        assert len(layout.indicators) > 0

        template = layout_manager.save_layout_as_template(
            "user_1",
            layout.layout_id,
            "My AAPL Setup",
            "Custom",
        )

        assert template is not None

        layout_manager.set_default_layout("user_1", layout.layout_id)
        default = layout_manager.get_default_layout("user_1")
        assert default.layout_id == layout.layout_id
