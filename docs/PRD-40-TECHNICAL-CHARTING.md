# PRD-40: Technical Charting

## Overview
Chart pattern detection, trend analysis, support/resistance identification,
and Fibonacci retracement/extension calculations for technical analysis.

## Components

### 1. Pattern Detector (`src/charting/patterns.py`)
- **Double top/bottom**: Peak/trough matching with neckline projection
- **Head and shoulders**: Three-peak pattern with shoulder symmetry
- **Triangles**: Ascending, descending, and symmetrical
- **Flags/wedges**: Consolidation patterns after strong moves
- Confidence scoring based on symmetry and volume

### 2. Trend Analyzer (`src/charting/trend.py`)
- **Linear regression**: Slope, R-squared for trend strength
- **Moving average alignment**: Short/medium/long MA positioning
- **MA crossovers**: Golden cross / death cross detection
- **ADX-style strength**: Trend strength measurement (0-100)

### 3. Support/Resistance Detector (`src/charting/support_resistance.py`)
- **Pivot-based levels**: Local min/max clustering
- **Touch counting**: How many times price tested a level
- **Level strength**: Weighted by recency and touch count
- **Zone detection**: Price zones rather than exact levels

### 4. Fibonacci Calculator (`src/charting/fibonacci.py`)
- **Retracements**: 23.6%, 38.2%, 50%, 61.8%, 78.6%
- **Extensions**: 100%, 127.2%, 161.8%, 200%, 261.8%
- **Swing detection**: Automatic swing high/low identification
- **Nearest level**: Find closest Fib level to current price

## Database Tables (Migration 026)
- `chart_patterns` — Detected pattern history
- `trend_analyses` — Trend assessments
- `sr_levels` — Support/resistance levels
- `fibonacci_analyses` — Fibonacci computations

## Dashboard (`app/pages/charting.py`)
4-tab layout: Patterns | Trends | Support/Resistance | Fibonacci
