"""Drawing tools for charting."""

from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict
import math

from src.charting.config import DrawingType, LineStyle
from src.charting.models import Drawing, DrawingStyle, Point


class DrawingManager:
    """Manages chart drawings."""
    
    def __init__(self):
        # layout_id -> list of drawings
        self._drawings: dict[str, list[Drawing]] = defaultdict(list)
    
    def create_trendline(
        self,
        symbol: str,
        start: tuple[datetime, float],
        end: tuple[datetime, float],
        color: str = "#2196F3",
        line_width: int = 1,
        extend_right: bool = False,
        extend_left: bool = False,
    ) -> Drawing:
        """Create a trendline."""
        drawing = Drawing(
            drawing_type=DrawingType.TRENDLINE,
            symbol=symbol,
            style=DrawingStyle(color=color, line_width=line_width),
            properties={
                "extend_right": extend_right,
                "extend_left": extend_left,
            },
        )
        drawing.add_point(start[0], start[1])
        drawing.add_point(end[0], end[1])
        return drawing
    
    def create_horizontal_line(
        self,
        symbol: str,
        price: float,
        color: str = "#FF9800",
        line_width: int = 1,
        line_style: LineStyle = LineStyle.SOLID,
    ) -> Drawing:
        """Create a horizontal line."""
        drawing = Drawing(
            drawing_type=DrawingType.HORIZONTAL_LINE,
            symbol=symbol,
            style=DrawingStyle(
                color=color,
                line_width=line_width,
                line_style=line_style,
            ),
        )
        drawing.add_point(datetime.now(timezone.utc), price)
        return drawing
    
    def create_vertical_line(
        self,
        symbol: str,
        timestamp: datetime,
        color: str = "#9C27B0",
        line_width: int = 1,
    ) -> Drawing:
        """Create a vertical line."""
        drawing = Drawing(
            drawing_type=DrawingType.VERTICAL_LINE,
            symbol=symbol,
            style=DrawingStyle(color=color, line_width=line_width),
        )
        drawing.add_point(timestamp, 0)
        return drawing
    
    def create_fibonacci_retracement(
        self,
        symbol: str,
        start: tuple[datetime, float],
        end: tuple[datetime, float],
        levels: Optional[list[float]] = None,
        show_prices: bool = True,
        show_percentages: bool = True,
    ) -> Drawing:
        """Create a Fibonacci retracement."""
        if levels is None:
            levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        
        drawing = Drawing(
            drawing_type=DrawingType.FIBONACCI_RETRACEMENT,
            symbol=symbol,
            properties={
                "levels": levels,
                "show_prices": show_prices,
                "show_percentages": show_percentages,
            },
        )
        drawing.add_point(start[0], start[1])
        drawing.add_point(end[0], end[1])
        return drawing
    
    def create_rectangle(
        self,
        symbol: str,
        top_left: tuple[datetime, float],
        bottom_right: tuple[datetime, float],
        color: str = "#4CAF50",
        fill_opacity: float = 0.2,
    ) -> Drawing:
        """Create a rectangle."""
        drawing = Drawing(
            drawing_type=DrawingType.RECTANGLE,
            symbol=symbol,
            style=DrawingStyle(
                color=color,
                fill_color=color,
                fill_opacity=fill_opacity,
            ),
        )
        drawing.add_point(top_left[0], top_left[1])
        drawing.add_point(bottom_right[0], bottom_right[1])
        return drawing
    
    def create_text(
        self,
        symbol: str,
        position: tuple[datetime, float],
        text: str,
        font_size: int = 12,
        color: str = "#FFFFFF",
    ) -> Drawing:
        """Create a text annotation."""
        drawing = Drawing(
            drawing_type=DrawingType.TEXT,
            symbol=symbol,
            style=DrawingStyle(font_size=font_size, text_color=color),
            properties={"text": text},
            label=text,
        )
        drawing.add_point(position[0], position[1])
        return drawing
    
    def create_price_label(
        self,
        symbol: str,
        position: tuple[datetime, float],
        label: str = "",
        color: str = "#2196F3",
    ) -> Drawing:
        """Create a price label."""
        drawing = Drawing(
            drawing_type=DrawingType.PRICE_LABEL,
            symbol=symbol,
            style=DrawingStyle(color=color),
            label=label or f"${position[1]:.2f}",
        )
        drawing.add_point(position[0], position[1])
        return drawing
    
    def create_channel(
        self,
        symbol: str,
        start1: tuple[datetime, float],
        end1: tuple[datetime, float],
        start2: tuple[datetime, float],
        end2: tuple[datetime, float],
        color: str = "#2196F3",
        fill_opacity: float = 0.1,
    ) -> Drawing:
        """Create a parallel channel."""
        drawing = Drawing(
            drawing_type=DrawingType.CHANNEL,
            symbol=symbol,
            style=DrawingStyle(
                color=color,
                fill_color=color,
                fill_opacity=fill_opacity,
            ),
        )
        drawing.add_point(start1[0], start1[1])
        drawing.add_point(end1[0], end1[1])
        drawing.add_point(start2[0], start2[1])
        drawing.add_point(end2[0], end2[1])
        return drawing
    
    def create_arrow(
        self,
        symbol: str,
        start: tuple[datetime, float],
        end: tuple[datetime, float],
        color: str = "#F44336",
    ) -> Drawing:
        """Create an arrow."""
        drawing = Drawing(
            drawing_type=DrawingType.ARROW,
            symbol=symbol,
            style=DrawingStyle(color=color),
        )
        drawing.add_point(start[0], start[1])
        drawing.add_point(end[0], end[1])
        return drawing
    
    def add_drawing(self, layout_id: str, drawing: Drawing) -> None:
        """Add a drawing to a layout."""
        self._drawings[layout_id].append(drawing)
    
    def get_drawings(self, layout_id: str, symbol: Optional[str] = None) -> list[Drawing]:
        """Get drawings for a layout."""
        drawings = self._drawings.get(layout_id, [])
        if symbol:
            drawings = [d for d in drawings if d.symbol == symbol]
        return drawings
    
    def get_drawing(self, layout_id: str, drawing_id: str) -> Optional[Drawing]:
        """Get a specific drawing."""
        for drawing in self._drawings.get(layout_id, []):
            if drawing.drawing_id == drawing_id:
                return drawing
        return None
    
    def update_drawing(
        self,
        layout_id: str,
        drawing_id: str,
        points: Optional[list[tuple[datetime, float]]] = None,
        style: Optional[DrawingStyle] = None,
        properties: Optional[dict] = None,
    ) -> Optional[Drawing]:
        """Update a drawing."""
        drawing = self.get_drawing(layout_id, drawing_id)
        if not drawing:
            return None
        
        if points:
            drawing.points = [Point(p[0], p[1]) for p in points]
        if style:
            drawing.style = style
        if properties:
            drawing.properties.update(properties)
        
        return drawing
    
    def delete_drawing(self, layout_id: str, drawing_id: str) -> bool:
        """Delete a drawing."""
        drawings = self._drawings.get(layout_id, [])
        for i, drawing in enumerate(drawings):
            if drawing.drawing_id == drawing_id:
                drawings.pop(i)
                return True
        return False
    
    def clear_drawings(self, layout_id: str, symbol: Optional[str] = None) -> int:
        """Clear drawings for a layout."""
        if symbol:
            drawings = self._drawings.get(layout_id, [])
            original_count = len(drawings)
            self._drawings[layout_id] = [d for d in drawings if d.symbol != symbol]
            return original_count - len(self._drawings[layout_id])
        else:
            count = len(self._drawings.get(layout_id, []))
            self._drawings[layout_id] = []
            return count
    
    def duplicate_drawing(self, layout_id: str, drawing_id: str) -> Optional[Drawing]:
        """Duplicate a drawing."""
        original = self.get_drawing(layout_id, drawing_id)
        if not original:
            return None
        
        new_drawing = Drawing(
            drawing_type=original.drawing_type,
            symbol=original.symbol,
            points=[Point(p.timestamp, p.price) for p in original.points],
            style=DrawingStyle(
                color=original.style.color,
                line_width=original.style.line_width,
                line_style=original.style.line_style,
                fill_color=original.style.fill_color,
                fill_opacity=original.style.fill_opacity,
            ),
            properties=original.properties.copy(),
            label=original.label,
        )
        
        self.add_drawing(layout_id, new_drawing)
        return new_drawing
    
    def calculate_fib_levels(
        self,
        start_price: float,
        end_price: float,
        levels: Optional[list[float]] = None,
    ) -> dict[float, float]:
        """Calculate Fibonacci levels."""
        if levels is None:
            levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        
        diff = end_price - start_price
        return {level: start_price + diff * level for level in levels}
    
    def get_stats(self) -> dict:
        """Get drawing statistics."""
        total = sum(len(d) for d in self._drawings.values())
        by_type = defaultdict(int)
        
        for drawings in self._drawings.values():
            for drawing in drawings:
                by_type[drawing.drawing_type.value] += 1
        
        return {
            "total_drawings": total,
            "layouts_with_drawings": len(self._drawings),
            "by_type": dict(by_type),
        }
