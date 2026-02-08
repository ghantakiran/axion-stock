# PRD-91: Advanced Stock Screener

## Overview
Advanced stock screening and scanning system with 100+ built-in filters, custom formula expressions, 18 preset screens, real-time pattern detection, unusual activity scanning, screen backtesting, and alert management.

## Components

### 1. Screener Engine (`src/screener/engine.py`)
- **ScreenerEngine** — Run screens against stock universe with filter evaluation
- **ScreenManager** — CRUD for saved screens (save, get, delete, duplicate, list)
- Sector/market cap/universe filtering, custom formula support
- Screen validation before execution

### 2. Filter Registry (`src/screener/filters.py`)
- **FilterRegistry** — 100+ built-in filters across 14 categories
- Valuation: PE, PB, PS, EV/EBITDA, PEG, FCF yield
- Growth: Revenue/EPS/earnings growth rates
- Profitability: ROE, ROA, ROIC, margins
- Financial Health: Current ratio, D/E, interest coverage
- Size: Market cap, enterprise value
- Dividends: Yield, payout ratio, growth
- Price: 52-week range, gap, change
- Moving Averages: SMA/EMA crosses, above/below
- Momentum: RSI, MACD, 6m/12m returns
- Volatility: Beta, realized vol, ATR
- Volume: Relative volume, average volume
- Analyst: Rating, target, revisions
- Institutional: Ownership, changes
- Short Interest: Short ratio, % float

### 3. Expression Parser (`src/screener/expression.py`)
- **ExpressionParser** — Custom formula evaluation
- Arithmetic (+, -, *, /), comparison (<, >, ==), logical (and, or, not)
- Functions: abs, max, min, avg, sqrt, log
- Variable extraction and validation

### 4. Preset Screens (`src/screener/presets.py`)
- 18 presets: Deep Value, Buffett Quality, High Growth, GARP, Momentum Leaders, Dividend Aristocrats, Low Volatility, Small Cap Value, Turnaround, Technical Breakout, Income, Micro Cap, Large Cap Growth, Quality at Reasonable Price, High Short Interest, Insider Buying, IPO Watch, ESG Leaders

### 5. Screen Alerts (`src/screener/alerts.py`)
- **ScreenAlertManager** — Entry/exit/count threshold alerts
- Notification generation on screen match changes

### 6. Screen Backtester (`src/screener/backtest.py`)
- **ScreenBacktester** — Historical performance testing
- Sharpe/Sortino ratios, max drawdown, win rate
- Configurable rebalance frequency and holding periods

### 7. Scanner Module (`src/scanner/`)
- **ScannerEngine** — Real-time market scanning with criteria evaluation
- **UnusualActivityDetector** — Volume surges, price anomalies
- **PatternDetector** — Candlestick patterns (Doji, Engulfing, Morning Star, Hammer, etc.)
- 10 preset scanners: Gap Up/Down, New High/Low, Volume Spike, RSI signals, MACD, Big Gainers/Losers

## Database Tables
- Existing screener/scanner tables in earlier migrations
- `saved_screen_results` — Cached screen results for comparison (migration 091)
- `scan_pattern_history` — Detected pattern history log (migration 091)

## Dashboards
- `app/pages/screener.py` — Screener dashboard with filters, presets, results
- `app/pages/scanner.py` — Scanner dashboard with real-time scans

## Test Coverage
47 tests across 2 test files:
- `tests/test_screener.py` — 29 tests (FilterRegistry, ExpressionParser, FilterCondition, ScreenerEngine, PresetScreens, ScreenManager, ScreenAlertManager, ScreenBacktester)
- `tests/test_scanner.py` — 18 tests (ScanCriterion, ScannerEngine, PresetScanners, UnusualActivityDetector, PatternDetector)
