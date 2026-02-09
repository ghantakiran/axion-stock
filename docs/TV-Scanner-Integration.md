# TradingView Scanner Integration

## Overview

Live market screening powered by TradingView's screener API via the `tvscreener` Python library. No authentication required. Supports 6 asset classes with 13,000+ screening fields, 14 preset scans across 7 categories, custom scan builder, streaming mode, and cross-module bridge to Axion's scanner, screener, and EMA signal modules.

## Architecture

```
src/tv_scanner/
├── __init__.py       # Public API exports
├── config.py         # Enums (AssetClass, TVScanCategory, TVTimeInterval), field mappings, config
├── models.py         # Data models (TVPreset, TVScanResult, TVScanReport, TVFilterCriterion)
├── presets.py        # 14 pre-built scan configurations across 7 categories
├── engine.py         # TVScannerEngine — query builder, executor, result converter
└── bridge.py         # TVDataBridge — adapters for scanner/screener/EMA modules
```

## Asset Classes

| Asset Class | tvscreener Class | Field Enum |
|-------------|-----------------|------------|
| `STOCK` | `StockScreener` | `StockField` |
| `CRYPTO` | `CryptoScreener` | `CryptoField` |
| `FOREX` | `ForexScreener` | `ForexField` |
| `BOND` | `BondScreener` | `BondField` |
| `FUTURES` | `FuturesScreener` | `FuturesField` |
| `COIN` | `CoinScreener` | `CoinField` |

## Preset Scans (14)

### Momentum (4 presets)

| Preset ID | Description | Key Criteria |
|-----------|-------------|--------------|
| `momentum_breakout` | Stocks breaking out with strong momentum | Price > SMA50, RSI 50-70, RelVol >= 1.5x, Change > 2% |
| `rsi_oversold` | Oversold bounce candidates | RSI < 30, Volume >= 500K |
| `rsi_overbought` | Overbought for potential short/exit | RSI > 70, Volume >= 500K |
| `macd_bullish_cross` | Bullish MACD crossover | MACD > 0, Change > 0 |

### Value (1 preset)

| Preset ID | Description | Key Criteria |
|-----------|-------------|--------------|
| `undervalued_quality` | Quality value stocks | P/E 0-15, Cap >= $1B, Div Yield >= 1% |

### Dividend (1 preset)

| Preset ID | Description | Key Criteria |
|-----------|-------------|--------------|
| `high_dividend` | High-yield dividend stocks | Yield >= 4%, P/E 0-25 |

### Volume (2 presets)

| Preset ID | Description | Key Criteria |
|-----------|-------------|--------------|
| `volume_explosion` | 3x+ relative volume spike | RelVol >= 3x, Volume >= 1M, Change > 2% |
| `unusual_volume` | Institutional interest signal | RelVol >= 2x, Volume >= 500K |

### Technical (3 presets)

| Preset ID | Description | Key Criteria |
|-----------|-------------|--------------|
| `golden_cross` | SMA50 above SMA200 | SMA50 > 0, SMA200 > 0 |
| `above_all_smas` | Price above all major MAs | SMA20 > 0, SMA50 > 0, SMA200 > 0 |
| `bollinger_oversold` | Near lower Bollinger Band | RSI < 40, includes BB fields |

### Growth (1 preset)

| Preset ID | Description | Key Criteria |
|-----------|-------------|--------------|
| `earnings_momentum` | Positive EPS momentum | EPS > 0, Price > $10 |

### Crypto (2 presets)

| Preset ID | Description | Key Criteria |
|-----------|-------------|--------------|
| `crypto_momentum` | Crypto with RSI above 50 | RSI > 50, Change > 0 |
| `crypto_oversold` | Oversold crypto bounce | RSI < 30 |

## Signal Strength Scoring

Each `TVScanResult` receives a 0-100 `signal_strength` score computed from 4 weighted components:

| Component | Weight | Source | Mapping |
|-----------|--------|--------|---------|
| TV Rating | 40% | `Recommend.All` [-1, +1] | Normalized to [0, 40] |
| RSI Position | 20% | `RSI` deviation from 50 | abs(RSI - 50) / 50, capped at 1.0, scaled to [0, 20] |
| Relative Volume | 20% | `relative_volume_10d_calc` | Capped at 3x, scaled to [0, 20] |
| Price Momentum | 20% | `change_pct` | abs(change) / 10%, capped at 1.0, scaled to [0, 20] |

## Cross-Module Bridge

`TVDataBridge` provides 3 adapters for integrating scan results with other Axion modules:

| Method | Target Module | Output Format |
|--------|--------------|---------------|
| `to_scanner_format()` | `src/scanner/ScannerEngine` | `{symbol: {price, volume, rsi, signal_strength, ...}}` |
| `to_screener_format()` | `src/screener/ScreenerEngine` | `{symbol: {price, pe_ratio, sma_20, sma_50, sector, ...}}` |
| `to_ema_scan_list()` | `src/ema_signals/UniverseScanner` | `["AAPL", "MSFT", ...]` |

## Usage

### Run a preset scan

```python
from src.tv_scanner import TVScannerEngine, PRESET_TV_SCANS

engine = TVScannerEngine()
report = engine.run_preset("momentum_breakout")
for r in report.results:
    print(f"{r.symbol}: ${r.price} RSI={r.rsi} strength={r.signal_strength}")
```

### Custom scan

```python
from src.tv_scanner import TVScannerEngine, TVFilterCriterion, AssetClass

engine = TVScannerEngine()
report = engine.run_custom_scan(
    criteria=[
        TVFilterCriterion("RSI", "lt", 25),
        TVFilterCriterion("volume", "gte", 1_000_000),
    ],
    asset_class=AssetClass.STOCK,
    max_results=50,
)
```

### Streaming mode

```python
engine = TVScannerEngine()
preset = PRESET_TV_SCANS["volume_explosion"]
for report in engine.stream_scan(preset, interval_seconds=10, max_iterations=100):
    print(f"Found {report.total_results} stocks")
```

### Bridge to EMA signals

```python
from src.tv_scanner import TVScannerEngine, TVDataBridge

engine = TVScannerEngine()
report = engine.run_preset("momentum_breakout")
tickers = TVDataBridge.to_ema_scan_list(report)
# Feed tickers into EMA UniverseScanner
```

## Configuration

```python
from src.tv_scanner import TVScannerConfig, AssetClass

config = TVScannerConfig(
    default_asset_class=AssetClass.STOCK,
    max_results=150,
    cache_ttl_seconds=30,
    timeout_seconds=15,
    min_price=1.0,
    min_volume=100_000,
)
engine = TVScannerEngine(config)
```

## Field Mappings

The engine maps 30+ TradingView field names to Axion-friendly names:

| TV Field | Axion Name | Category |
|----------|-----------|----------|
| `close` | `price` | Price |
| `change` | `change_pct` | Price |
| `volume` | `volume` | Volume |
| `relative_volume_10d_calc` | `relative_volume` | Volume |
| `RSI` | `rsi` | Oscillators |
| `MACD.macd` / `MACD.signal` | `macd` / `macd_signal` | Oscillators |
| `SMA20` / `SMA50` / `SMA200` | `sma_20` / `sma_50` / `sma_200` | Moving Averages |
| `Recommend.All` | `tv_rating` | Composite |
| `market_cap_basic` | `market_cap` | Valuation |
| `price_earnings_ttm` | `pe_ratio` | Valuation |
| `dividend_yield_recent` | `dividend_yield` | Dividend |
| `Perf.W` / `Perf.1M` / `Perf.Y` | `perf_week` / `perf_month` / `perf_year` | Performance |

## Filter Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `gt` | Greater than | `TVFilterCriterion("RSI", "gt", 70)` |
| `lt` | Less than | `TVFilterCriterion("RSI", "lt", 30)` |
| `gte` | Greater than or equal | `TVFilterCriterion("volume", "gte", 500_000)` |
| `lte` | Less than or equal | `TVFilterCriterion("close", "lte", 100)` |
| `eq` | Equal | `TVFilterCriterion("sector", "eq", "Technology")` |
| `between` | Range (inclusive) | `TVFilterCriterion("RSI", "between", 40, 60)` |
| `isin` | In list | `TVFilterCriterion("sector", "isin", ["Tech", "Health"])` |

## Dependencies

- `tvscreener` — Python wrapper for TradingView's screener API (lazily imported)
- No API key or authentication required
- Results are cached with configurable TTL (default: 30 seconds)

## Dashboard

`app/pages/tv_scanner.py` — TradingView Scanner dashboard in the Trading & Execution section.

## Testing

`tests/test_tv_scanner.py` — Tests use mocked tvscreener responses (no live API calls).
