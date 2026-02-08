# PRD-128: Real-Time Anomaly Detection Engine

## Overview
Real-time anomaly detection engine that monitors market data feeds, trading patterns, and system metrics to identify unusual activity. Uses statistical methods (Z-score, IQR, isolation forest) for proactive alerting.

## Goals
1. Multi-method anomaly detection (statistical, ML-based, rule-based)
2. Real-time streaming anomaly detection for market data
3. Trading pattern anomaly detection (unusual volumes, price spikes, behavior)
4. System metric anomaly detection (latency, error rates, resource usage)
5. Anomaly scoring, classification, and alerting integration

## Components

### 1. Anomaly Config (`config.py`)
- AnomalyType enum: PRICE_SPIKE, VOLUME_SURGE, LATENCY_SPIKE, ERROR_BURST, PATTERN_BREAK, DATA_DRIFT, OUTLIER
- DetectionMethod enum: ZSCORE, IQR, ISOLATION_FOREST, MOVING_AVERAGE, PERCENTILE, CUSTOM
- AnomalySeverity enum: LOW, MEDIUM, HIGH, CRITICAL
- AnomalyStatus enum: DETECTED, CONFIRMED, INVESTIGATING, RESOLVED, FALSE_POSITIVE
- DetectorConfig dataclass (method, threshold, window_size, min_samples, sensitivity)
- AnomalyConfig dataclass (detectors, alert_on_severity, cooldown_seconds, max_anomalies_per_hour)

### 2. Detector Engine (`detector.py`)
- DataPoint dataclass (timestamp, value, metric_name, tags)
- AnomalyResult dataclass (anomaly_id, data_point, method, score, severity, is_anomaly, context)
- DetectorEngine class:
  - add_data_point(point) -> optional AnomalyResult
  - detect_zscore(values, threshold) -> list of indices
  - detect_iqr(values, multiplier) -> list of indices
  - detect_isolation_forest(values, contamination) -> list of indices
  - detect_moving_average(values, window, threshold) -> list of indices
  - batch_detect(data_points) -> list of AnomalyResult
  - get_baseline(metric_name) -> statistics

### 3. Stream Monitor (`stream.py`)
- StreamConfig dataclass (metric_name, detector_config, buffer_size, emit_interval)
- StreamMonitor class:
  - register_stream(config) -> stream_id
  - ingest(metric_name, value, timestamp) -> optional AnomalyResult
  - get_stream_status(stream_id) -> dict
  - get_recent_anomalies(stream_id, limit) -> list
  - pause_stream(stream_id) -> None
  - resume_stream(stream_id) -> None
  - stream_statistics() -> dict

### 4. Pattern Analyzer (`patterns.py`)
- TradingPattern dataclass (pattern_id, pattern_type, symbols, time_range, description)
- PatternAnomaly dataclass (anomaly_id, pattern, deviation_score, expected, actual)
- PatternAnalyzer class:
  - analyze_volume_pattern(symbol, volumes) -> list of PatternAnomaly
  - analyze_price_pattern(symbol, prices) -> list of PatternAnomaly
  - detect_regime_change(series, window) -> list of change points
  - compare_to_baseline(current, baseline) -> deviation score
  - get_pattern_history(symbol) -> list of patterns

### 5. Anomaly Manager (`manager.py`)
- AnomalyRecord dataclass (record_id, anomaly_result, status, assigned_to, notes, resolved_at)
- AnomalyManager class:
  - record_anomaly(result) -> AnomalyRecord
  - update_status(record_id, status, notes) -> AnomalyRecord
  - get_open_anomalies() -> list
  - mark_false_positive(record_id, reason) -> AnomalyRecord
  - anomaly_statistics(period) -> dict
  - severity_distribution() -> dict
  - top_anomalous_metrics(limit) -> list

## Database Tables
- `anomaly_records`: Detected anomalies with status
- `anomaly_baselines`: Metric baselines for detection

## Dashboard (4 tabs)
1. Anomaly Overview — active anomalies, severity distribution, trends
2. Stream Monitoring — live streams, detection status, recent detections
3. Pattern Analysis — trading pattern anomalies, volume/price deviations
4. Investigation — open investigations, false positive tracking

## Test Coverage
- Detector engine tests (all methods)
- Stream monitoring lifecycle tests
- Pattern analysis tests
- Manager workflow tests
- ~85+ tests
