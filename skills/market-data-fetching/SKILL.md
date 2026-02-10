---
name: market-data-fetching
description: Fetch market data (prices, quotes, fundamentals, economic indicators) via the Axion data layer. Use when you need to retrieve stock prices, real-time quotes, fundamental financial data, economic indicators from FRED, or factor scores. Covers the multi-layer resolution strategy (Redis cache, PostgreSQL/TimescaleDB, external API) and data quality validation.
metadata:
  author: axion-platform
  version: "1.0"
---

# Market Data Fetching

## When to use this skill

Use this skill when you need to:
- Fetch historical close prices for one or more tickers
- Get real-time stock quotes (price, volume, bid/ask)
- Retrieve fundamental data (PE, P/B, dividend yield, margins, etc.)
- Look up economic indicators from FRED (GDP, CPI, unemployment, etc.)
- Get the investable stock universe (S&P 500 tickers)
- Retrieve pre-computed factor scores (value, momentum, quality, growth)
- Validate price or fundamental data quality before using it downstream
- Detect gaps in price data (missing trading days)

## Step-by-step instructions

### 1. Initialize the DataService

```python
from src.services.data_service import DataService

svc = DataService()
```

All data flows through `DataService`. It resolves data in three layers:
1. **Redis cache** (hot, sub-millisecond)
2. **PostgreSQL / TimescaleDB** (warm, milliseconds)
3. **External API** (cold, seconds) -- writes back to DB and cache

### 2. Fetch data using the appropriate method

Each method is `async` and returns pandas DataFrames or dicts.

#### Get the stock universe
```python
tickers = await svc.get_universe(index="sp500")
# Returns: list[str], e.g. ["AAPL", "MSFT", "GOOGL", ...]
```

#### Get historical prices
```python
df = await svc.get_prices(tickers=["AAPL", "MSFT"], period="14mo")
# Returns: DataFrame[dates x tickers] with adjusted close prices
# Cache key: "axion:prices:bulk:all", TTL: 300s (5 min)
```

#### Get real-time quotes
```python
quote = await svc.get_quote(ticker="AAPL")
# Returns: {"ticker": "AAPL", "price": 185.50, "source": "polygon", ...}
# Cache key: "axion:quote:AAPL", TTL: 30s
```

#### Get fundamentals
```python
df = await svc.get_fundamentals(tickers=["AAPL", "MSFT"])
# Returns: DataFrame[tickers x 10 fields] indexed by ticker
# Fields: trailingPE, priceToBook, dividendYield, enterpriseToEbitda,
#          returnOnEquity, debtToEquity, revenueGrowth, earningsGrowth,
#          marketCap, currentPrice
# Cache key: "axion:fundamentals:all", TTL: 4 hours
```

#### Get economic indicators
```python
series = await svc.get_economic_indicator(series_id="GDP", start="2020-01-01")
# Returns: pd.Series with DatetimeIndex and float values
# Cache key: "axion:economic:GDP", TTL: 1 hour
```

#### Get factor scores
```python
scores = await svc.get_scores(tickers=["AAPL", "MSFT"])
# Returns: DataFrame[tickers x 5 columns]: value, momentum, quality, growth, composite
# Cache key: "axion:scores:all", TTL: 1 hour
```

### 3. Validate data quality

```python
from src.quality.validators import PriceValidator, FundamentalValidator, ValidationResult

# Validate price data
validator = PriceValidator()
results: list[ValidationResult] = validator.validate_ohlcv(price_df, ticker="AAPL")

for r in results:
    if not r.passed:
        print(f"[{r.severity}] {r.check_name}: {r.message}")
```

Price validation checks:
- `positive_prices` -- no zero or negative close prices (critical)
- `ohlc_consistency` -- low <= open/close <= high (error)
- `extreme_moves` -- flags days with >50% move (warning)
- `volume_anomaly` -- flags volume >10x the 20-day average (info)
- `stale_prices` -- flags 5+ consecutive identical closes (warning)

```python
# Validate fundamental data
fv = FundamentalValidator()
results = fv.validate(fundamentals_df)
# Checks: positive_market_cap, data_completeness, pe_sanity, universe_coverage
```

### 4. Detect data gaps

```python
from src.quality.gap_detector import GapDetector, Gap

detector = GapDetector()
gaps: list[Gap] = detector.detect_gaps(price_df, ticker="AAPL", max_gap_days=5)

for gap in gaps:
    print(f"{gap.ticker}: missing {gap.missing_date} ({gap.gap_type})")

# Summarize across all tickers
all_gaps = {"AAPL": gaps_aapl, "MSFT": gaps_msft}
summary_df = detector.summarize_gaps(all_gaps)
```

### 5. Use the Redis cache directly (advanced)

```python
from src.cache.redis_client import cache  # Module-level singleton

# Async operations
df = await cache.get_dataframe("axion:prices:bulk:all")
await cache.set_dataframe("axion:prices:bulk:all", df, ttl=300)

data = await cache.get_json("axion:universe:sp500")
await cache.set_json("axion:universe:sp500", data, ttl=86400)

quote = await cache.get_quote("AAPL")
await cache.set_quote("AAPL", quote_dict)

# Sync operations (backward compatibility)
df = cache.get_dataframe_sync("axion:scores:all")
cache.set_json_sync("axion:session:abc123", session_data, ttl=28800)

# Invalidate cache
deleted = await cache.invalidate_pattern("axion:prices:*")
```

## Code examples

### Full pipeline: universe, prices, fundamentals, validation

```python
import asyncio
from src.services.data_service import DataService
from src.quality.validators import PriceValidator, FundamentalValidator

async def fetch_and_validate():
    svc = DataService()

    # Step 1: Get universe
    tickers = await svc.get_universe()
    print(f"Universe: {len(tickers)} tickers")

    # Step 2: Fetch prices and fundamentals
    prices = await svc.get_prices(tickers, period="14mo")
    fundamentals = await svc.get_fundamentals(tickers)

    # Step 3: Validate
    pv = PriceValidator()
    fv = FundamentalValidator()

    for ticker in tickers[:10]:
        if ticker in prices.columns:
            ticker_df = prices[[ticker]].rename(columns={ticker: "close"})
            results = pv.validate_ohlcv(ticker_df, ticker)
            errors = [r for r in results if not r.passed]
            if errors:
                print(f"{ticker}: {len(errors)} validation issues")

    fund_results = fv.validate(fundamentals)
    for r in fund_results:
        print(f"  [{r.severity}] {r.check_name}: {r.message}")

    return prices, fundamentals

asyncio.run(fetch_and_validate())
```

### Economic indicator analysis

```python
async def macro_analysis():
    svc = DataService()

    gdp = await svc.get_economic_indicator("GDP", start="2020-01-01")
    cpi = await svc.get_economic_indicator("CPIAUCSL", start="2020-01-01")
    unemployment = await svc.get_economic_indicator("UNRATE", start="2020-01-01")

    print(f"GDP latest: {gdp.iloc[-1]:.1f}")
    print(f"CPI latest: {cpi.iloc[-1]:.1f}")
    print(f"Unemployment: {unemployment.iloc[-1]:.1f}%")
```

## Key classes and methods

### `DataService` (`src/services/data_service.py`)
| Method | Returns | Cache Key | TTL |
|--------|---------|-----------|-----|
| `get_universe(index)` | `list[str]` | `axion:universe:{index}` | 24h |
| `get_prices(tickers, period)` | `DataFrame` | `axion:prices:bulk:all` | 5min |
| `get_quote(ticker)` | `dict` | `axion:quote:{ticker}` | 30s |
| `get_fundamentals(tickers)` | `DataFrame` | `axion:fundamentals:all` | 4h |
| `get_economic_indicator(series_id, start)` | `pd.Series` | `axion:economic:{series_id}` | 1h |
| `get_scores(tickers)` | `DataFrame` | `axion:scores:all` | 1h |

### `RedisCache` (`src/cache/redis_client.py`)
- `get_dataframe(key)` / `set_dataframe(key, df, ttl)` -- pickled DataFrame storage
- `get_json(key)` / `set_json(key, data, ttl)` -- JSON storage
- `get_quote(ticker)` / `set_quote(ticker, data)` -- quote shortcuts
- `invalidate_pattern(pattern)` -- glob-based cache invalidation
- Sync variants: `get_dataframe_sync`, `set_dataframe_sync`, etc.

### `PriceValidator` (`src/quality/validators.py`)
- `validate_ohlcv(df, ticker)` -> `list[ValidationResult]`

### `FundamentalValidator` (`src/quality/validators.py`)
- `validate(df)` -> `list[ValidationResult]`

### `GapDetector` (`src/quality/gap_detector.py`)
- `detect_gaps(df, ticker, max_gap_days)` -> `list[Gap]`
- `summarize_gaps(all_gaps)` -> `pd.DataFrame`

### `ValidationResult` (`src/quality/validators.py`)
- Fields: `passed: bool`, `check_name: str`, `severity: str`, `message: str`, `details: dict`

## Common patterns

### Cache key conventions (`src/cache/keys.py`)
All keys are prefixed with `axion:`:
- `axion:quote:{ticker}` -- TTL 30s
- `axion:prices:{ticker}:{timeframe}` -- TTL 5min
- `axion:fundamentals:all` -- TTL 4h
- `axion:scores:all` -- TTL 1h
- `axion:universe:{index}` -- TTL 24h
- `axion:economic:{series_id}` -- TTL 1h
- `axion:session:{session_id}` -- TTL 8h

### Multi-layer resolution pattern
Every `DataService` method follows the same pattern:
1. Check Redis cache with key
2. If miss, query PostgreSQL/TimescaleDB
3. If miss, call external API (Polygon, YFinance, FRED)
4. On API success, write back to cache AND persist to DB asynchronously

### 90% coverage threshold
Price and fundamental fetches use a 90% coverage threshold: if Redis returns
data for at least 90% of requested tickers, it skips the database and API
layers. This avoids unnecessary round-trips for a few missing tickers.

### Fallback providers
- **Prices**: YFinance (`src/services/providers/yfinance_provider.py`)
- **Quotes**: Polygon first, YFinance fallback
- **Economic**: FRED API (`src/services/providers/fred_provider.py`)
