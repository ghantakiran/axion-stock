# PRD-62: Advanced Charting

## Overview

Professional-grade interactive charting system with drawing tools, technical overlays, annotations, and saved layouts. Provides TradingView-like experience for technical analysis.

## Goals

1. Deliver smooth, responsive chart rendering
2. Support 50+ technical indicators
3. Enable drawing tools and annotations
4. Allow saving and sharing chart layouts
5. Support multiple timeframes and chart types

## Components

### 1. Chart Types
- Candlestick (default)
- OHLC bars
- Line chart
- Area chart
- Heikin-Ashi
- Renko
- Point & Figure

### 2. Timeframes
- 1m, 5m, 15m, 30m, 1h, 4h
- Daily, Weekly, Monthly
- Custom ranges

### 3. Technical Indicators
**Trend**: SMA, EMA, WMA, VWAP, Bollinger Bands, Ichimoku
**Momentum**: RSI, MACD, Stochastic, CCI, Williams %R, ROC
**Volume**: OBV, Volume Profile, A/D Line, CMF
**Volatility**: ATR, Keltner Channels, Donchian Channels
**Support/Resistance**: Pivot Points, Fibonacci

### 4. Drawing Tools
- Trend lines
- Horizontal/Vertical lines
- Channels (parallel, regression)
- Fibonacci retracement/extension
- Rectangles, circles, arrows
- Text annotations
- Price labels
- Measure tool

### 5. Chart Layouts
- Save/load layouts
- Multiple chart grids
- Template library
- Share layouts with others

### 6. Alerts from Chart
- Draw alert zones
- Click-to-set price alerts
- Indicator-based alerts

## Database Tables

### chart_layouts
- id, user_id, name, description
- chart_config (JSON), indicators, drawings
- is_template, is_public, created_at

### chart_drawings
- id, layout_id, symbol, drawing_type
- coordinates, style, properties
- created_at, updated_at

### chart_indicator_settings
- id, user_id, indicator_name
- default_params, color_scheme
- is_favorite

### chart_templates
- id, name, description, category
- config, thumbnail_url
- usage_count, created_by

## Technical Indicators Library

```python
# Trend Indicators
- SMA(period=20)
- EMA(period=12, 26)
- WMA(period=20)
- VWAP()
- Bollinger(period=20, std=2)
- Ichimoku(tenkan=9, kijun=26, senkou=52)

# Momentum Indicators
- RSI(period=14)
- MACD(fast=12, slow=26, signal=9)
- Stochastic(k=14, d=3)
- CCI(period=20)
- WilliamsR(period=14)
- ROC(period=12)

# Volume Indicators
- OBV()
- VolumeProfile(rows=24)
- ADLine()
- CMF(period=20)

# Volatility Indicators
- ATR(period=14)
- KeltnerChannel(period=20, mult=2)
- DonchianChannel(period=20)
```

## Drawing Tool Properties

```json
{
  "trendline": {
    "start": {"x": timestamp, "y": price},
    "end": {"x": timestamp, "y": price},
    "style": {
      "color": "#2196F3",
      "width": 2,
      "dash": "solid",
      "extend": "right"
    }
  },
  "fibonacci": {
    "start": {"x": timestamp, "y": price},
    "end": {"x": timestamp, "y": price},
    "levels": [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1],
    "style": {"colors": [...], "showLabels": true}
  }
}
```

## Success Metrics

| Metric | Target |
|--------|--------|
| Chart load time | < 500ms |
| Indicator calc time | < 100ms |
| Smooth pan/zoom | 60 FPS |
| Saved layouts | > 5 per user |

## Files

- `src/charting/config.py` - Configuration and enums
- `src/charting/models.py` - Data models
- `src/charting/indicators.py` - Technical indicators
- `src/charting/drawings.py` - Drawing tools
- `src/charting/layouts.py` - Layout management
- `src/charting/renderer.py` - Chart rendering
- `app/pages/charts.py` - Charting dashboard
