# PRD-86: Data Pipeline

## Overview
ETL data pipeline system with multi-source data ingestion, 3-tier caching (Redis/DB/API), data quality validation, scheduling, provider abstraction, and TimescaleDB time-series storage.

## Components

### 1. Data Service (`src/services/data_service.py`)
- **DataService** — Central async data access with 3-tier resolution
- Resolution order: Redis cache → PostgreSQL/TimescaleDB → External API
- Methods: get_universe(), get_prices(), get_fundamentals(), get_quote(), get_economic_indicator(), get_scores()
- Auto-persistence to DB and cache on fetch

### 2. Data Fetcher (`src/data_fetcher.py`)
- **download_price_data()** — OHLCV data with caching, batching, rate limiting
- **download_fundamentals()** — Fundamental metrics with field extraction
- **compute_price_returns()** — 6m/12m momentum returns
- **filter_universe()** — Price/market cap filtering
- Pickle-based file caching with TTL

### 3. Data Providers (`src/services/providers/`)
- **YFinanceProvider** — fetch_prices(), fetch_fundamentals(), get_quote()
- **PolygonProvider** — get_quote(), fetch_historical(), get_ticker_details()
- **FREDProvider** — fetch_series(), get_vix(), get_yield_curve_spread(), get_fed_funds_rate()

### 4. Data Quality (`src/quality/validators.py`)
- **PriceValidator** — OHLCV validation (empty, positive, OHLC consistency, extreme moves >50%, volume anomalies, stale data)
- **FundamentalValidator** — Market cap, completeness >50% nulls, PE sanity, ticker coverage
- **ValidationResult** — Structured results with severity levels

### 5. Caching (`src/cache/`)
- **RedisCache** — Async/sync dual access, DataFrame serialization, JSON storage, quote caching with TTL
- Cache key constants and TTL management

### 6. Scheduling
- **BotScheduler** (`src/bots/scheduler.py`) — Heap-based priority queue, market hours, US holidays 2024-2026
- **RebalanceScheduler** (`src/rebalancing/scheduler.py`) — Calendar/threshold/combined triggers
- **ExecutionScheduler** (`src/execution/scheduling.py`) — TWAP, VWAP, Implementation Shortfall

### 7. Sync Adapter (`src/services/sync_adapter.py`)
- **SyncDataService** — Backward-compatible sync wrapper around async DataService

### 8. Database Models (`src/db/models.py`)
- **Instrument** — Tradeable instruments with GICS classification
- **PriceBar** — OHLCV time-series (TimescaleDB hypertable)
- **Financial** — Fundamental data snapshots
- **FactorScore** — Pre-computed factor scores
- **EconomicIndicator** — FRED macro data
- **MarketRegime** — Regime classifications

### 9. ML Training Pipeline (`src/ml/training/pipeline.py`)
- **TrainingPipeline** — Orchestrates feature engineering, walk-forward validation, model training, evaluation, storage

## Database Tables
- Core schema (migration 001), TimescaleDB hypertables (002), continuous aggregates (003)
- Factor engine v2 (004), execution (005), risk (006), ML (007)
- `pipeline_run_log` — Pipeline execution tracking with status/timing (migration 086)
- `data_quality_metrics` — Data quality metric snapshots (migration 086)

## Dashboards
- Risk monitoring integrated into `app/pages/risk.py`
- Bot management in `app/pages/bots.py` (if exists)

## Test Coverage
50+ passing tests in `tests/test_data_service.py` covering:
- Settings, Redis cache, price/fundamental validators, sync adapter, FRED provider, Polygon provider
- 5 pre-existing ORM failures (Instrument table duplicate, unrelated to pipeline logic)
- Additional tests in `tests/test_bots.py` for bot scheduling
