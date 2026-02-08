# PRD-103: Observability & Metrics Export

## Overview
Add Prometheus-compatible metrics export with key trading, system, and business metrics. Provides quantitative insight into platform health, performance, and trading activity.

## Components

### 1. Metrics Registry (`src/observability/registry.py`)
- **MetricsRegistry** — Central registry for all platform metrics
- Counter, Gauge, Histogram, Summary metric types
- Thread-safe metric updates
- Metric families with labels (service, endpoint, status)

### 2. Trading Metrics (`src/observability/trading.py`)
- orders_total (counter) — by status, broker, side
- order_latency_seconds (histogram) — execution time
- positions_active (gauge) — current open positions
- portfolio_value (gauge) — current portfolio NAV
- signals_generated (counter) — by strategy, direction
- slippage_bps (histogram) — execution quality

### 3. System Metrics (`src/observability/system.py`)
- api_requests_total (counter) — by method, path, status_code
- api_request_duration_seconds (histogram)
- db_query_duration_seconds (histogram) — by operation
- cache_hits_total / cache_misses_total (counter)
- websocket_connections_active (gauge)
- data_pipeline_lag_seconds (gauge) — by source

### 4. Prometheus Exporter (`src/observability/exporter.py`)
- /metrics endpoint in Prometheus text format
- Efficient serialization with prometheus_client library
- Optional push gateway support for batch jobs

### 5. Metric Decorators (`src/observability/decorators.py`)
- @track_latency — Automatically record function duration
- @count_calls — Increment counter on each call
- @track_errors — Count exceptions by type

### 6. Configuration (`src/observability/config.py`)
- MetricsConfig: enable/disable, port, path, push_gateway_url
- Default metric buckets for histograms

## Integration Points
- FastAPI middleware auto-records API request metrics
- Mount /metrics endpoint on the API
