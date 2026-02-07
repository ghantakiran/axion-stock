"""Layout management for charting."""

from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

from src.charting.config import ChartType, Timeframe
from src.charting.models import (
    ChartLayout,
    ChartTemplate,
    IndicatorConfig,
    Drawing,
)


class LayoutManager:
    """Manages chart layouts and templates."""

    def __init__(self):
        # user_id -> list of layouts
        self._layouts: dict[str, list[ChartLayout]] = defaultdict(list)
        # template_id -> template
        self._templates: dict[str, ChartTemplate] = {}
        # Built-in templates
        self._init_builtin_templates()

    def _init_builtin_templates(self) -> None:
        """Initialize built-in templates."""
        # Trend Following template
        self._templates["trend_following"] = ChartTemplate(
            template_id="trend_following",
            name="Trend Following",
            category="Trading",
            description="Moving averages and trend indicators",
            config={
                "chart_type": ChartType.CANDLESTICK.value,
                "timeframe": Timeframe.D1.value,
            },
            indicators=[
                {"name": "SMA", "params": {"period": 20}, "color": "#2196F3"},
                {"name": "SMA", "params": {"period": 50}, "color": "#FF9800"},
                {"name": "SMA", "params": {"period": 200}, "color": "#F44336"},
                {"name": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
            ],
            is_featured=True,
        )

        # Momentum template
        self._templates["momentum"] = ChartTemplate(
            template_id="momentum",
            name="Momentum Analysis",
            category="Trading",
            description="RSI and Stochastic for momentum",
            config={
                "chart_type": ChartType.CANDLESTICK.value,
                "timeframe": Timeframe.H4.value,
            },
            indicators=[
                {"name": "RSI", "params": {"period": 14}},
                {"name": "STOCH", "params": {"k": 14, "d": 3}},
                {"name": "BB", "params": {"period": 20, "std": 2.0}},
            ],
            is_featured=True,
        )

        # Scalping template
        self._templates["scalping"] = ChartTemplate(
            template_id="scalping",
            name="Scalping Setup",
            category="Trading",
            description="Fast timeframe with volume",
            config={
                "chart_type": ChartType.CANDLESTICK.value,
                "timeframe": Timeframe.M5.value,
            },
            indicators=[
                {"name": "EMA", "params": {"period": 9}, "color": "#2196F3"},
                {"name": "EMA", "params": {"period": 21}, "color": "#FF9800"},
                {"name": "VWAP", "params": {}},
                {"name": "ATR", "params": {"period": 14}},
            ],
            is_featured=True,
        )

        # Volatility template
        self._templates["volatility"] = ChartTemplate(
            template_id="volatility",
            name="Volatility Analysis",
            category="Analysis",
            description="Bollinger Bands and ATR",
            config={
                "chart_type": ChartType.CANDLESTICK.value,
                "timeframe": Timeframe.D1.value,
            },
            indicators=[
                {"name": "BB", "params": {"period": 20, "std": 2.0}},
                {"name": "ATR", "params": {"period": 14}},
                {"name": "KC", "params": {"period": 20, "mult": 2.0}},
            ],
            is_featured=False,
        )

        # Volume Analysis template
        self._templates["volume_analysis"] = ChartTemplate(
            template_id="volume_analysis",
            name="Volume Analysis",
            category="Analysis",
            description="OBV and volume indicators",
            config={
                "chart_type": ChartType.CANDLESTICK.value,
                "timeframe": Timeframe.D1.value,
            },
            indicators=[
                {"name": "OBV", "params": {}},
                {"name": "VWAP", "params": {}},
                {"name": "CMF", "params": {"period": 20}},
            ],
            is_featured=False,
        )

    # Layout Management

    def create_layout(
        self,
        user_id: str,
        name: str,
        symbol: Optional[str] = None,
        timeframe: Timeframe = Timeframe.D1,
        chart_type: ChartType = ChartType.CANDLESTICK,
        description: str = "",
    ) -> ChartLayout:
        """Create a new chart layout."""
        layout = ChartLayout(
            user_id=user_id,
            name=name,
            symbol=symbol,
            timeframe=timeframe,
            chart_type=chart_type,
            description=description,
        )
        self._layouts[user_id].append(layout)
        return layout

    def get_layout(self, user_id: str, layout_id: str) -> Optional[ChartLayout]:
        """Get a specific layout."""
        for layout in self._layouts.get(user_id, []):
            if layout.layout_id == layout_id:
                return layout
        return None

    def get_layouts(self, user_id: str) -> list[ChartLayout]:
        """Get all layouts for a user."""
        return self._layouts.get(user_id, [])

    def get_default_layout(self, user_id: str) -> Optional[ChartLayout]:
        """Get user's default layout."""
        for layout in self._layouts.get(user_id, []):
            if layout.is_default:
                return layout
        return None

    def set_default_layout(self, user_id: str, layout_id: str) -> bool:
        """Set a layout as default."""
        found = False
        for layout in self._layouts.get(user_id, []):
            if layout.layout_id == layout_id:
                layout.is_default = True
                found = True
            else:
                layout.is_default = False
        return found

    def update_layout(
        self,
        user_id: str,
        layout_id: str,
        name: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[Timeframe] = None,
        chart_type: Optional[ChartType] = None,
        chart_config: Optional[dict] = None,
    ) -> Optional[ChartLayout]:
        """Update a layout."""
        layout = self.get_layout(user_id, layout_id)
        if not layout:
            return None

        if name is not None:
            layout.name = name
        if symbol is not None:
            layout.symbol = symbol
        if timeframe is not None:
            layout.timeframe = timeframe
        if chart_type is not None:
            layout.chart_type = chart_type
        if chart_config is not None:
            layout.chart_config.update(chart_config)

        return layout

    def delete_layout(self, user_id: str, layout_id: str) -> bool:
        """Delete a layout."""
        layouts = self._layouts.get(user_id, [])
        for i, layout in enumerate(layouts):
            if layout.layout_id == layout_id:
                layouts.pop(i)
                return True
        return False

    def duplicate_layout(self, user_id: str, layout_id: str, new_name: str) -> Optional[ChartLayout]:
        """Duplicate a layout."""
        original = self.get_layout(user_id, layout_id)
        if not original:
            return None

        new_layout = ChartLayout(
            user_id=user_id,
            name=new_name,
            symbol=original.symbol,
            timeframe=original.timeframe,
            chart_type=original.chart_type,
            description=original.description,
            indicators=[
                IndicatorConfig(
                    indicator_id=ind.indicator_id,
                    name=ind.name,
                    params=ind.params.copy(),
                    color=ind.color,
                    secondary_color=ind.secondary_color,
                    line_style=ind.line_style,
                    line_width=ind.line_width,
                    is_visible=ind.is_visible,
                    panel_index=ind.panel_index,
                )
                for ind in original.indicators
            ],
            chart_config=original.chart_config.copy(),
        )

        self._layouts[user_id].append(new_layout)
        return new_layout

    # Indicator Management

    def add_indicator(
        self,
        user_id: str,
        layout_id: str,
        indicator_config: IndicatorConfig,
    ) -> bool:
        """Add an indicator to a layout."""
        layout = self.get_layout(user_id, layout_id)
        if not layout:
            return False

        layout.add_indicator(indicator_config)
        return True

    def remove_indicator(
        self,
        user_id: str,
        layout_id: str,
        indicator_id: str,
    ) -> bool:
        """Remove an indicator from a layout."""
        layout = self.get_layout(user_id, layout_id)
        if not layout:
            return False

        return layout.remove_indicator(indicator_id)

    def update_indicator(
        self,
        user_id: str,
        layout_id: str,
        indicator_id: str,
        params: Optional[dict] = None,
        color: Optional[str] = None,
        is_visible: Optional[bool] = None,
    ) -> bool:
        """Update an indicator."""
        layout = self.get_layout(user_id, layout_id)
        if not layout:
            return False

        for ind in layout.indicators:
            if ind.indicator_id == indicator_id:
                if params is not None:
                    ind.params.update(params)
                if color is not None:
                    ind.color = color
                if is_visible is not None:
                    ind.is_visible = is_visible
                return True

        return False

    # Drawing Management

    def add_drawing(
        self,
        user_id: str,
        layout_id: str,
        drawing: Drawing,
    ) -> bool:
        """Add a drawing to a layout."""
        layout = self.get_layout(user_id, layout_id)
        if not layout:
            return False

        layout.add_drawing(drawing)
        return True

    def remove_drawing(
        self,
        user_id: str,
        layout_id: str,
        drawing_id: str,
    ) -> bool:
        """Remove a drawing from a layout."""
        layout = self.get_layout(user_id, layout_id)
        if not layout:
            return False

        return layout.remove_drawing(drawing_id)

    # Template Management

    def get_template(self, template_id: str) -> Optional[ChartTemplate]:
        """Get a template."""
        return self._templates.get(template_id)

    def get_templates(self, category: Optional[str] = None) -> list[ChartTemplate]:
        """Get all templates, optionally filtered by category."""
        templates = list(self._templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates

    def get_featured_templates(self) -> list[ChartTemplate]:
        """Get featured templates."""
        return [t for t in self._templates.values() if t.is_featured]

    def create_template(
        self,
        name: str,
        category: str,
        config: dict,
        indicators: list[dict],
        description: str = "",
        created_by: Optional[str] = None,
    ) -> ChartTemplate:
        """Create a custom template."""
        template = ChartTemplate(
            name=name,
            category=category,
            config=config,
            indicators=indicators,
            description=description,
            created_by=created_by,
        )
        self._templates[template.template_id] = template
        return template

    def apply_template(
        self,
        user_id: str,
        layout_id: str,
        template_id: str,
    ) -> bool:
        """Apply a template to a layout."""
        layout = self.get_layout(user_id, layout_id)
        template = self.get_template(template_id)

        if not layout or not template:
            return False

        # Apply chart config
        if "chart_type" in template.config:
            layout.chart_type = ChartType(template.config["chart_type"])
        if "timeframe" in template.config:
            layout.timeframe = Timeframe(template.config["timeframe"])

        # Clear existing indicators and apply template indicators
        layout.indicators = []
        for ind_config in template.indicators:
            config = IndicatorConfig(
                indicator_id=f"{ind_config['name']}_{len(layout.indicators)}",
                name=ind_config["name"],
                params=ind_config.get("params", {}),
                color=ind_config.get("color", "#2196F3"),
            )
            layout.add_indicator(config)

        template.increment_usage()
        return True

    def rate_template(self, template_id: str, rating: float) -> bool:
        """Rate a template."""
        template = self.get_template(template_id)
        if not template:
            return False

        template.add_rating(rating)
        return True

    def save_layout_as_template(
        self,
        user_id: str,
        layout_id: str,
        template_name: str,
        category: str,
        description: str = "",
    ) -> Optional[ChartTemplate]:
        """Save a layout as a template."""
        layout = self.get_layout(user_id, layout_id)
        if not layout:
            return None

        config = {
            "chart_type": layout.chart_type.value,
            "timeframe": layout.timeframe.value,
        }

        indicators = [
            {
                "name": ind.name,
                "params": ind.params.copy(),
                "color": ind.color,
            }
            for ind in layout.indicators
        ]

        return self.create_template(
            name=template_name,
            category=category,
            config=config,
            indicators=indicators,
            description=description,
            created_by=user_id,
        )

    # Statistics

    def get_stats(self, user_id: Optional[str] = None) -> dict:
        """Get layout statistics."""
        if user_id:
            layouts = self._layouts.get(user_id, [])
            total_indicators = sum(len(l.indicators) for l in layouts)
            total_drawings = sum(len(l.drawings) for l in layouts)

            return {
                "total_layouts": len(layouts),
                "total_indicators": total_indicators,
                "total_drawings": total_drawings,
                "templates_used": len(set(
                    t.template_id for t in self._templates.values()
                    if t.usage_count > 0
                )),
            }
        else:
            total_layouts = sum(len(l) for l in self._layouts.values())
            return {
                "total_layouts": total_layouts,
                "total_users": len(self._layouts),
                "total_templates": len(self._templates),
                "featured_templates": len(self.get_featured_templates()),
            }
