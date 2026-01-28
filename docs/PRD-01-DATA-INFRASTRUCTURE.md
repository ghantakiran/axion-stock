# PRD-01: Data Infrastructure & Real-Time Pipeline

**Priority**: P0 | **Phase**: 1 | **Status**: Draft

---

## Problem Statement

Axion currently relies on Yahoo Finance with 24-hour pickle caching and batch scraping. This creates stale data, rate-limiting issues, and no real-time capabilities. A world-class algo platform requires sub-second data freshness, multi-source redundancy, and scalable storage.

---

## Goals

1. **Real-time market data** with <100ms latency for price updates
2. **Multi-source data pipeline** with automatic failover
3. **Persistent storage** replacing pickle files with a proper database
4. **Historical data depth** of 20+ years for robust backtesting
5. **Data quality** with validation, gap detection, and correction
6. **Scalable architecture** supporting 10,000+ instruments

---

## Non-Goals

- Building a proprietary exchange data feed
- Sub-microsecond HFT latency
- Tick-by-tick data storage (minute bars minimum)

---

## Current State

| Component | Current | Target |
|-----------|---------|--------|
| Data Source | Yahoo Finance only | Polygon + Yahoo + Alpha Vantage + FRED |
| Latency | 24-hour cache | <100ms streaming, 1-min batch |
| Storage | Pickle files | TimescaleDB + Redis + S3 |
| History | 14 months | 20+ years |
| Instruments | ~500 (S&P 500) | 8,000+ (US equities) |
| Data Types | OHLCV + basic fundamentals | + options, earnings, economic, sentiment |

---

## Detailed Requirements

### R1: Market Data Ingestion Service

#### R1.1: Real-Time Price Streaming
- **Primary**: Polygon.io WebSocket for real-time quotes and trades
- **Secondary**: Alpaca WebSocket (free tier, 15-min delay for free users)
- **Fallback**: Yahoo Finance polling (5-second intervals)

**Data Points Per Tick**:
```
{
  symbol: str,
  price: float,
  bid: float,
  ask: float,
  bid_size: int,
  ask_size: int,
  volume: int,
  timestamp: datetime (microsecond precision),
  exchange: str,
  conditions: list[str]
}
```

#### R1.2: OHLCV Bar Aggregation
- Aggregate ticks into 1-min, 5-min, 15-min, 1-hour, 1-day bars
- Use TWAP (time-weighted average price) for bar opens/closes
- Track VWAP per bar period
- Handle pre-market (4:00-9:30 ET) and after-hours (16:00-20:00 ET)

#### R1.3: Historical Data Backfill
- Backfill 20+ years of daily OHLCV from Polygon/Yahoo
- 5 years of minute-level data
- Corporate actions adjustment (splits, dividends)
- Store both adjusted and unadjusted prices
- Detect and handle delistings, mergers, ticker changes

### R2: Fundamental Data Pipeline

#### R2.1: Financial Statements
- Income statement (quarterly + annual, 10 years)
- Balance sheet (quarterly + annual, 10 years)
- Cash flow statement (quarterly + annual, 10 years)
- Source: SEC EDGAR XBRL filings + Financial Modeling Prep API

#### R2.2: Earnings Data
- EPS estimates (consensus, high, low)
- Revenue estimates
- Earnings surprise history (beat/miss %)
- Earnings date calendar
- Pre/post-announcement price reactions
- Source: Alpha Vantage Earnings API + Yahoo Finance

#### R2.3: Valuation Metrics
- Forward P/E (using consensus estimates)
- PEG ratio (P/E divided by growth rate)
- EV/EBITDA, EV/Revenue, EV/FCF
- Price/Sales, Price/Book, Price/Cash Flow
- Dividend yield, payout ratio, growth rate
- Calculated from financial statements + price data

#### R2.4: Ownership & Insider Data
- Institutional ownership % and top holders
- Insider transactions (buys, sells, grants)
- Short interest (shares short, days to cover, short % of float)
- Source: SEC Form 4 filings, FINRA short interest reports

### R3: Alternative Data Pipeline

#### R3.1: Economic Indicators
- Fed Funds Rate, Treasury yields (2Y, 10Y, 30Y)
- CPI, PPI, PCE inflation data
- GDP, unemployment, non-farm payrolls
- ISM manufacturing/services PMI
- Consumer confidence, housing starts
- Source: FRED API (Federal Reserve Economic Data)

#### R3.2: Market Breadth
- Advance/Decline ratio
- New highs/lows
- VIX and VIX futures term structure
- Put/Call ratio (equity, index, total)
- Margin debt levels
- Source: CBOE, NYSE, calculated from universe data

#### R3.3: Sector & Industry Data
- GICS sector/industry classification
- Sector ETF performance (XLK, XLF, XLE, etc.)
- Industry rotation momentum
- Relative strength by sector
- Source: S&P GICS + ETF price data

### R4: Database Architecture

#### R4.1: TimescaleDB (Time-Series)
```sql
-- Hypertable for price data
CREATE TABLE ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      BIGINT,
    vwap        DOUBLE PRECISION,
    adj_close   DOUBLE PRECISION,
    bar_type    TEXT DEFAULT '1d'  -- 1m, 5m, 15m, 1h, 1d
);
SELECT create_hypertable('ohlcv', 'time');
CREATE INDEX idx_ohlcv_symbol ON ohlcv (symbol, time DESC);

-- Continuous aggregates for multi-timeframe
CREATE MATERIALIZED VIEW ohlcv_weekly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 week', time) AS bucket,
       symbol,
       first(open, time) AS open,
       max(high) AS high,
       min(low) AS low,
       last(close, time) AS close,
       sum(volume) AS volume
FROM ohlcv
WHERE bar_type = '1d'
GROUP BY bucket, symbol;
```

#### R4.2: PostgreSQL (Relational)
```sql
-- Stock universe
CREATE TABLE instruments (
    symbol          TEXT PRIMARY KEY,
    name            TEXT,
    sector          TEXT,
    industry        TEXT,
    market_cap      BIGINT,
    exchange        TEXT,
    ipo_date        DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    gics_sector     TEXT,
    gics_industry   TEXT
);

-- Financial statements
CREATE TABLE financials (
    symbol          TEXT REFERENCES instruments(symbol),
    period_end      DATE,
    period_type     TEXT,  -- 'quarterly', 'annual'
    statement_type  TEXT,  -- 'income', 'balance', 'cashflow'
    data            JSONB,
    filed_date      DATE,
    PRIMARY KEY (symbol, period_end, statement_type)
);

-- Factor scores (computed)
CREATE TABLE factor_scores (
    symbol          TEXT REFERENCES instruments(symbol),
    date            DATE,
    value_score     DOUBLE PRECISION,
    momentum_score  DOUBLE PRECISION,
    quality_score   DOUBLE PRECISION,
    growth_score    DOUBLE PRECISION,
    composite_score DOUBLE PRECISION,
    regime          TEXT,
    PRIMARY KEY (symbol, date)
);
```

#### R4.3: Redis (Hot Cache)
- Current quotes for all tracked symbols (TTL: 1 second)
- Factor scores for current day (TTL: 1 hour)
- User session data (TTL: 24 hours)
- Rate limiter counters (TTL: per-window)
- WebSocket subscription state

#### R4.4: Object Storage (S3/GCS)
- Raw API response archives (GZIP compressed)
- Backtest result artifacts
- ML model checkpoints
- Data quality audit logs

### R5: Data Quality Framework

#### R5.1: Validation Rules
- Price sanity checks (no negative prices, >100x daily moves flagged)
- Volume anomaly detection (>10x average flagged)
- Gap detection (missing trading days identified)
- Corporate action verification (splits cause expected price changes)
- Cross-source consistency (Yahoo vs Polygon within 0.1%)

#### R5.2: Data Reconciliation
- Daily reconciliation job comparing sources
- Automatic gap filling from secondary sources
- Alerting on unresolvable discrepancies
- Manual override capability with audit trail

#### R5.3: Monitoring
- Data freshness dashboards (staleness alerts >5 min)
- Source availability monitoring (uptime tracking)
- Ingestion throughput metrics (symbols/second)
- Storage growth projections

### R6: API Layer

#### R6.1: Internal Data API
```python
class DataService:
    async def get_quote(self, symbol: str) -> Quote
    async def get_ohlcv(self, symbol: str, start: date, end: date,
                        bar_type: str = '1d') -> pd.DataFrame
    async def get_fundamentals(self, symbol: str) -> Fundamentals
    async def get_earnings(self, symbol: str) -> EarningsCalendar
    async def get_economic(self, indicator: str, start: date) -> pd.Series
    async def get_factor_scores(self, symbol: str, date: date) -> FactorScores
    async def subscribe(self, symbols: list[str], callback: Callable)
    async def get_universe(self, index: str = 'sp500') -> list[str]
```

---

## Technical Approach

### Data Flow Architecture
```
External Sources          Ingestion Layer          Storage Layer
┌──────────┐              ┌──────────┐            ┌──────────┐
│ Polygon  │──WebSocket──▶│  Kafka   │──Stream──▶│TimescaleDB│
│  (RT)    │              │ Topics   │            └──────────┘
└──────────┘              └────┬─────┘                  │
┌──────────┐                   │              ┌──────────┐
│ Yahoo    │──Polling────▶│ Workers  │──Batch──▶│ Postgres │
│  (Batch) │              │ (Celery) │          └──────────┘
└──────────┘              └────┬─────┘                  │
┌──────────┐                   │              ┌──────────┐
│ FRED     │──Scheduled──▶│ Scheduler│──Cache──▶│  Redis   │
│  (Daily) │              │ (APSched)│          └──────────┘
└──────────┘              └──────────┘
```

### Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Message Queue | Apache Kafka | High throughput, replay capability |
| Task Queue | Celery + Redis | Python-native, proven at scale |
| Time-Series DB | TimescaleDB | PostgreSQL extension, SQL familiar |
| Cache | Redis | Sub-ms latency, pub/sub support |
| Scheduler | APScheduler | Python-native, cron + interval |
| Container | Docker Compose → K8s | Local dev → production scale |

---

## Migration Plan

### Step 1: Add PostgreSQL + TimescaleDB
- Docker Compose setup with Postgres + TimescaleDB
- Create schema migrations (Alembic)
- Dual-write: pickle + database during transition

### Step 2: Replace Pickle Cache
- Migrate data_fetcher.py to use database
- Redis for hot cache, DB for cold storage
- Remove pickle-based caching code

### Step 3: Add Polygon Real-Time
- WebSocket client for live quotes
- Fallback to Yahoo on Polygon outage
- Quote fan-out to subscribed clients

### Step 4: Backfill Historical Data
- 20-year daily data backfill job
- 5-year minute data backfill
- Reconciliation report

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Data latency | ~24 hours | <100ms (streaming) |
| History depth | 14 months | 20+ years |
| Instrument coverage | ~500 | 8,000+ |
| Data sources | 1 (Yahoo) | 4+ |
| Cache hit rate | N/A | >95% |
| Data freshness SLA | None | 99.9% within 5 min |

---

## Dependencies

- Polygon.io API key (Starter plan: $29/mo, Developer: $79/mo)
- Alpha Vantage API key (Premium: $49.99/mo)
- PostgreSQL + TimescaleDB instance
- Redis instance
- FRED API key (free)

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Polygon rate limits | Medium | High | Request batching, caching |
| Yahoo Finance blocks | High | Medium | Primary source migration |
| DB storage costs | Medium | Medium | Retention policies, archival |
| Data quality issues | High | High | Multi-source validation |
| WebSocket disconnects | Medium | Medium | Auto-reconnect with backfill |

---

*Owner: Backend Engineering Lead*
*Last Updated: January 2026*
