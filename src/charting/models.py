"""Data models for Advanced Charting."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid

from src.charting.config import (
    ChartType,
    Timeframe,
    DrawingType,
    IndicatorCategory,
    LineStyle,
)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OHLCV:
    """OHLCV price bar."""
    
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass
class IndicatorResult:
    """Result from indicator calculation."""
    
    name: str
    values: dict[str, list[float]]  # Series name -> values
    timestamps: list[datetime]
    params: dict = field(default_factory=dict)
    is_overlay: bool = True
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "values": self.values,
            "timestamps": [t.isoformat() for t in self.timestamps],
            "params": self.params,
            "is_overlay": self.is_overlay,
        }


@dataclass
class IndicatorConfig:
    """Configuration for a chart indicator."""
    
    indicator_id: str
    name: str
    params: dict = field(default_factory=dict)
    color: str = "#2196F3"
    secondary_color: Optional[str] = None
    line_style: LineStyle = LineStyle.SOLID
    line_width: int = 1
    is_visible: bool = True
    panel_index: int = 0  # 0 = main chart, 1+ = separate panels
    
    def to_dict(self) -> dict:
        return {
            "indicator_id": self.indicator_id,
            "name": self.name,
            "params": self.params,
            "color": self.color,
            "secondary_color": self.secondary_color,
            "line_style": self.line_style.value,
            "line_width": self.line_width,
            "is_visible": self.is_visible,
            "panel_index": self.panel_index,
        }


@dataclass
class Point:
    """A point on the chart."""
    
    timestamp: datetime
    price: float
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
        }


@dataclass
class DrawingStyle:
    """Style for a drawing."""
    
    color: str = "#2196F3"
    line_width: int = 1
    line_style: LineStyle = LineStyle.SOLID
    fill_color: Optional[str] = None
    fill_opacity: float = 0.2
    font_size: int = 12
    text_color: str = "#FFFFFF"
    
    def to_dict(self) -> dict:
        return {
            "color": self.color,
            "line_width": self.line_width,
            "line_style": self.line_style.value,
            "fill_color": self.fill_color,
            "fill_opacity": self.fill_opacity,
            "font_size": self.font_size,
            "text_color": self.text_color,
        }


@dataclass
class Drawing:
    """A drawing on the chart."""
    
    drawing_type: DrawingType
    symbol: str
    points: list[Point] = field(default_factory=list)
    drawing_id: str = field(default_factory=_new_id)
    style: DrawingStyle = field(default_factory=DrawingStyle)
    properties: dict = field(default_factory=dict)
    label: str = ""
    notes: str = ""
    is_visible: bool = True
    is_locked: bool = False
    z_index: int = 0
    created_at: datetime = field(default_factory=_now)
    
    def add_point(self, timestamp: datetime, price: float) -> None:
        """Add a point to the drawing."""
        self.points.append(Point(timestamp, price))
    
    def move(self, delta_time: float, delta_price: float) -> None:
        """Move the entire drawing."""
        from datetime import timedelta
        for point in self.points:
            point.timestamp = point.timestamp + timedelta(seconds=delta_time)
            point.price += delta_price
    
    def to_dict(self) -> dict:
        return {
            "drawing_id": self.drawing_id,
            "drawing_type": self.drawing_type.value,
            "symbol": self.symbol,
            "points": [p.to_dict() for p in self.points],
            "style": self.style.to_dict(),
            "properties": self.properties,
            "label": self.label,
            "notes": self.notes,
            "is_visible": self.is_visible,
            "is_locked": self.is_locked,
            "z_index": self.z_index,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ChartLayout:
    """A saved chart layout."""
    
    user_id: str
    name: str
    layout_id: str = field(default_factory=_new_id)
    description: str = ""
    symbol: Optional[str] = None
    timeframe: Timeframe = Timeframe.D1
    chart_type: ChartType = ChartType.CANDLESTICK
    indicators: list[IndicatorConfig] = field(default_factory=list)
    drawings: list[Drawing] = field(default_factory=list)
    chart_config: dict = field(default_factory=dict)
    grid_layout: Optional[dict] = None
    is_template: bool = False
    is_public: bool = False
    is_default: bool = False
    view_count: int = 0
    copy_count: int = 0
    created_at: datetime = field(default_factory=_now)
    last_used_at: Optional[datetime] = None
    
    def add_indicator(self, config: IndicatorConfig) -> None:
        """Add an indicator to the layout."""
        self.indicators.append(config)
    
    def remove_indicator(self, indicator_id: str) -> bool:
        """Remove an indicator from the layout."""
        for i, ind in enumerate(self.indicators):
            if ind.indicator_id == indicator_id:
                self.indicators.pop(i)
                return True
        return False
    
    def add_drawing(self, drawing: Drawing) -> None:
        """Add a drawing to the layout."""
        self.drawings.append(drawing)
    
    def remove_drawing(self, drawing_id: str) -> bool:
        """Remove a drawing from the layout."""
        for i, d in enumerate(self.drawings):
            if d.drawing_id == drawing_id:
                self.drawings.pop(i)
                return True
        return False
    
    def mark_used(self) -> None:
        """Mark layout as recently used."""
        self.last_used_at = _now()
        self.view_count += 1
    
    def to_dict(self) -> dict:
        return {
            "layout_id": self.layout_id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "chart_type": self.chart_type.value,
            "indicators": [i.to_dict() for i in self.indicators],
            "drawings": [d.to_dict() for d in self.drawings],
            "chart_config": self.chart_config,
            "is_template": self.is_template,
            "is_public": self.is_public,
            "is_default": self.is_default,
            "view_count": self.view_count,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ChartTemplate:
    """A chart template."""
    
    name: str
    category: str
    config: dict
    template_id: str = field(default_factory=_new_id)
    description: str = ""
    indicators: list[dict] = field(default_factory=list)
    created_by: Optional[str] = None
    thumbnail_url: Optional[str] = None
    usage_count: int = 0
    rating: float = 0.0
    rating_count: int = 0
    is_featured: bool = False
    is_approved: bool = True
    created_at: datetime = field(default_factory=_now)
    
    def increment_usage(self) -> None:
        """Increment usage count."""
        self.usage_count += 1
    
    def add_rating(self, new_rating: float) -> None:
        """Add a rating."""
        total = self.rating * self.rating_count + new_rating
        self.rating_count += 1
        self.rating = total / self.rating_count
    
    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "indicators": self.indicators,
            "thumbnail_url": self.thumbnail_url,
            "usage_count": self.usage_count,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "is_featured": self.is_featured,
            "created_at": self.created_at.isoformat(),
        }
