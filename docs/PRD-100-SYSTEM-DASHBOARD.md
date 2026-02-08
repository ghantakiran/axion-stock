# PRD-100: System Dashboard

## Overview
Unified system health monitoring dashboard with service health checks, resource metrics collection, data freshness tracking, anomaly detection, dependency monitoring, and threshold-based alerting across all platform components.

## Components

### 1. Health Checker (`src/system_dashboard/health.py`)
- **HealthChecker** — Pluggable health check framework
- Check individual services with response time, error rate, availability
- Automatic status classification: HEALTHY, DEGRADED, DOWN
- Check all 8 monitored services in parallel
- Custom health check registration via callable
- Data freshness tracking across 7 data sources with staleness detection
- External dependency health monitoring
- Full system snapshot capture combining services, metrics, freshness, dependencies
- Summary generation for dashboard display
- Snapshot history tracking

### 2. Metrics Collector (`src/system_dashboard/metrics.py`)
- **MetricsCollector** — Time-series metrics aggregation
- Record system metric snapshots (CPU, memory, disk, connections, response times)
- Counter and gauge primitives for custom metrics
- Rolling averages over configurable windows
- Percentile calculations (P50, P90, P95, P99)
- Anomaly detection using z-score standard deviation method
- Configurable max history (default 1440 = 24 hours at 1-min intervals)
- Sample history generation for demo

### 3. Alert Manager (`src/system_dashboard/alerts.py`)
- **SystemAlertManager** — Threshold-based system alerting
- CPU, memory, disk usage monitoring (warning + critical thresholds)
- API response time alerting
- Service health alerts (down/degraded)
- Data staleness alerts per source
- Alert lifecycle: create → acknowledge → resolve
- Active alert filtering by level
- Alert count aggregation
- Resolved alert cleanup

### 4. Configuration (`src/system_dashboard/config.py`)
- ServiceName (API, DATABASE, CACHE, DATA_PIPELINE, ML_SERVING, WEBSOCKET, BROKER, SCHEDULER)
- ServiceStatus (HEALTHY, DEGRADED, DOWN, UNKNOWN)
- HealthLevel (HEALTHY, WARNING, CRITICAL, DOWN)
- MetricType (COUNTER, GAUGE, HISTOGRAM, RATE)
- AlertThresholds with defaults: CPU 80%/95%, memory 80%/95%, disk 85%/95%, response 500ms/2000ms, error rate 1%/5%, data stale 60min
- SystemConfig with monitored services and data source lists

### 5. Models (`src/system_dashboard/models.py`)
- 7 dataclasses: ServiceHealth, SystemMetrics, DataFreshness, DependencyStatus, SystemAlert, HealthSnapshot, SystemSummary

## Database Tables
- `system_health_snapshots` — Periodic health check records (migration 100)
- `system_alert_log` — System alert history (migration 100)

## Dashboard
Streamlit dashboard (`app/pages/system_dashboard.py`) with 4 tabs: Overview, Services, Metrics, Alerts.

## Test Coverage
54 tests in `tests/test_system_dashboard.py` covering enums (4), configs (3), models (5), HealthChecker (14), MetricsCollector (11), SystemAlertManager (13), integration (2), module imports (1).
