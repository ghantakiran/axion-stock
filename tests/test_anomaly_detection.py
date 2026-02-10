"""Tests for PRD-128: Real-Time Anomaly Detection Engine."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from src.anomaly_detection.config import (
    AnomalyType,
    DetectionMethod,
    AnomalySeverity,
    AnomalyStatus,
    DetectorConfig,
    AnomalyConfig,
    DEFAULT_ZSCORE_THRESHOLD,
    DEFAULT_IQR_MULTIPLIER,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_MIN_SAMPLES,
    DEFAULT_SENSITIVITY,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_MAX_ANOMALIES_PER_HOUR,
)
from src.anomaly_detection.detector import (
    DataPoint,
    AnomalyResult,
    DetectorEngine,
    _mean,
    _std,
    _median,
    _quartiles,
    _score_to_severity,
)
from src.anomaly_detection.stream import (
    StreamConfig,
    StreamMonitor,
)
from src.anomaly_detection.patterns import (
    TradingPattern,
    PatternAnomaly,
    PatternAnalyzer,
)
from src.anomaly_detection.manager import (
    AnomalyRecord,
    AnomalyManager,
)


# ── Config / Enum Tests ──────────────────────────────────────────────


class TestAnomalyDetectionEnums:
    """Tests for all enum types."""

    def test_anomaly_type_values(self):
        assert len(AnomalyType) == 7
        assert AnomalyType.PRICE_SPIKE.value == "price_spike"
        assert AnomalyType.VOLUME_SURGE.value == "volume_surge"
        assert AnomalyType.LATENCY_SPIKE.value == "latency_spike"
        assert AnomalyType.ERROR_BURST.value == "error_burst"
        assert AnomalyType.PATTERN_BREAK.value == "pattern_break"
        assert AnomalyType.DATA_DRIFT.value == "data_drift"
        assert AnomalyType.OUTLIER.value == "outlier"

    def test_detection_method_values(self):
        assert len(DetectionMethod) == 6
        assert DetectionMethod.ZSCORE.value == "zscore"
        assert DetectionMethod.IQR.value == "iqr"
        assert DetectionMethod.ISOLATION_FOREST.value == "isolation_forest"
        assert DetectionMethod.MOVING_AVERAGE.value == "moving_average"
        assert DetectionMethod.PERCENTILE.value == "percentile"
        assert DetectionMethod.CUSTOM.value == "custom"

    def test_anomaly_severity_values(self):
        assert len(AnomalySeverity) == 4
        assert AnomalySeverity.LOW.value == "low"
        assert AnomalySeverity.MEDIUM.value == "medium"
        assert AnomalySeverity.HIGH.value == "high"
        assert AnomalySeverity.CRITICAL.value == "critical"

    def test_anomaly_status_values(self):
        assert len(AnomalyStatus) == 5
        assert AnomalyStatus.DETECTED.value == "detected"
        assert AnomalyStatus.CONFIRMED.value == "confirmed"
        assert AnomalyStatus.INVESTIGATING.value == "investigating"
        assert AnomalyStatus.RESOLVED.value == "resolved"
        assert AnomalyStatus.FALSE_POSITIVE.value == "false_positive"


class TestAnomalyDetectionConfigs:
    """Tests for dataclass configurations."""

    def test_detector_config_defaults(self):
        cfg = DetectorConfig()
        assert cfg.method == DetectionMethod.ZSCORE
        assert cfg.threshold == DEFAULT_ZSCORE_THRESHOLD
        assert cfg.window_size == DEFAULT_WINDOW_SIZE
        assert cfg.min_samples == DEFAULT_MIN_SAMPLES
        assert cfg.sensitivity == DEFAULT_SENSITIVITY

    def test_detector_config_custom(self):
        cfg = DetectorConfig(
            method=DetectionMethod.IQR,
            threshold=2.0,
            window_size=100,
            min_samples=20,
            sensitivity=0.8,
        )
        assert cfg.method == DetectionMethod.IQR
        assert cfg.threshold == 2.0
        assert cfg.window_size == 100
        assert cfg.min_samples == 20

    def test_anomaly_config_defaults(self):
        cfg = AnomalyConfig()
        assert len(cfg.detectors) == 1
        assert cfg.alert_on_severity == AnomalySeverity.MEDIUM
        assert cfg.cooldown_seconds == DEFAULT_COOLDOWN_SECONDS
        assert cfg.max_anomalies_per_hour == DEFAULT_MAX_ANOMALIES_PER_HOUR

    def test_anomaly_config_multiple_detectors(self):
        cfg = AnomalyConfig(
            detectors=[
                DetectorConfig(method=DetectionMethod.ZSCORE),
                DetectorConfig(method=DetectionMethod.IQR),
            ]
        )
        assert len(cfg.detectors) == 2


# ── Detector Engine Tests ────────────────────────────────────────────


class TestHelperFunctions:
    """Tests for internal math helpers."""

    def test_mean_empty(self):
        assert _mean([]) == 0.0

    def test_mean_single(self):
        assert _mean([5.0]) == 5.0

    def test_mean_normal(self):
        assert _mean([1.0, 2.0, 3.0, 4.0, 5.0]) == 3.0

    def test_std_empty(self):
        assert _std([]) == 0.0

    def test_std_single(self):
        assert _std([5.0]) == 0.0

    def test_std_normal(self):
        result = _std([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert abs(result - 2.0) < 0.2

    def test_median_odd(self):
        assert _median([1.0, 3.0, 5.0]) == 3.0

    def test_median_even(self):
        assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5

    def test_median_empty(self):
        assert _median([]) == 0.0

    def test_quartiles(self):
        q1, q3 = _quartiles([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        assert q1 < q3

    def test_quartiles_small(self):
        q1, q3 = _quartiles([1.0, 2.0, 3.0])
        assert q1 == 1.0
        assert q3 == 3.0

    def test_score_to_severity_low(self):
        assert _score_to_severity(1.0) == AnomalySeverity.LOW

    def test_score_to_severity_medium(self):
        assert _score_to_severity(3.0) == AnomalySeverity.MEDIUM

    def test_score_to_severity_high(self):
        assert _score_to_severity(4.0) == AnomalySeverity.HIGH

    def test_score_to_severity_critical(self):
        assert _score_to_severity(5.0) == AnomalySeverity.CRITICAL


class TestDataPoint:
    """Tests for DataPoint dataclass."""

    def test_default_creation(self):
        dp = DataPoint()
        assert dp.value == 0.0
        assert dp.metric_name == ""
        assert isinstance(dp.timestamp, datetime)
        assert dp.tags == {}

    def test_custom_creation(self):
        ts = datetime(2024, 6, 1, tzinfo=timezone.utc)
        dp = DataPoint(timestamp=ts, value=42.5, metric_name="cpu", tags={"host": "a"})
        assert dp.value == 42.5
        assert dp.metric_name == "cpu"
        assert dp.tags["host"] == "a"


class TestAnomalyResult:
    """Tests for AnomalyResult dataclass."""

    def test_default_creation(self):
        r = AnomalyResult()
        assert len(r.anomaly_id) == 16
        assert r.is_anomaly is False
        assert r.score == 0.0
        assert r.severity == AnomalySeverity.LOW

    def test_custom_creation(self):
        dp = DataPoint(value=100.0, metric_name="latency")
        r = AnomalyResult(
            data_point=dp,
            method=DetectionMethod.IQR,
            score=4.5,
            severity=AnomalySeverity.HIGH,
            is_anomaly=True,
        )
        assert r.is_anomaly is True
        assert r.method == DetectionMethod.IQR
        assert r.score == 4.5


class TestDetectorEngine:
    """Tests for the main DetectorEngine class."""

    def setup_method(self):
        self.engine = DetectorEngine()

    def test_detect_zscore_empty(self):
        assert self.engine.detect_zscore([]) == []

    def test_detect_zscore_single(self):
        assert self.engine.detect_zscore([5.0]) == []

    def test_detect_zscore_no_anomaly(self):
        values = [10.0, 10.1, 9.9, 10.0, 10.2, 9.8, 10.0]
        assert self.engine.detect_zscore(values, threshold=3.0) == []

    def test_detect_zscore_with_anomaly(self):
        values = [10.0] * 20 + [50.0]
        indices = self.engine.detect_zscore(values, threshold=3.0)
        assert 20 in indices

    def test_detect_zscore_constant_values(self):
        values = [5.0] * 10
        assert self.engine.detect_zscore(values) == []

    def test_detect_iqr_empty(self):
        assert self.engine.detect_iqr([]) == []

    def test_detect_iqr_small(self):
        assert self.engine.detect_iqr([1.0, 2.0, 3.0]) == []

    def test_detect_iqr_no_anomaly(self):
        values = [10.0, 10.5, 11.0, 10.2, 10.8, 10.1, 10.9, 10.3]
        assert self.engine.detect_iqr(values) == []

    def test_detect_iqr_with_anomaly(self):
        values = [10.0, 10.1, 10.0, 9.9, 10.0, 10.1, 9.8, 100.0]
        indices = self.engine.detect_iqr(values, multiplier=1.5)
        assert 7 in indices

    def test_detect_isolation_forest_empty(self):
        assert self.engine.detect_isolation_forest([]) == []

    def test_detect_isolation_forest_small(self):
        assert self.engine.detect_isolation_forest([1.0, 2.0]) == []

    def test_detect_isolation_forest_finds_outlier(self):
        values = [10.0] * 19 + [100.0]
        indices = self.engine.detect_isolation_forest(values, contamination=0.1)
        assert 19 in indices

    def test_detect_isolation_forest_constant(self):
        values = [5.0] * 20
        assert self.engine.detect_isolation_forest(values) == []

    def test_detect_moving_average_empty(self):
        assert self.engine.detect_moving_average([], window=5) == []

    def test_detect_moving_average_short(self):
        assert self.engine.detect_moving_average([1.0, 2.0], window=5) == []

    def test_detect_moving_average_no_anomaly(self):
        values = [10.0] * 20
        assert self.engine.detect_moving_average(values, window=5, threshold=2.0) == []

    def test_detect_moving_average_with_anomaly(self):
        # Use slightly varied values so std != 0 in the rolling window
        values = [10.0, 10.1, 9.9, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8,
                  10.0, 10.1, 9.9, 10.2, 9.8, 50.0]
        indices = self.engine.detect_moving_average(values, window=5, threshold=2.0)
        assert 15 in indices

    def test_add_data_point_insufficient_data(self):
        engine = DetectorEngine(AnomalyConfig(
            detectors=[DetectorConfig(min_samples=10)]
        ))
        dp = DataPoint(value=10.0, metric_name="test")
        assert engine.add_data_point(dp) is None

    def test_add_data_point_normal(self):
        engine = DetectorEngine(AnomalyConfig(
            detectors=[DetectorConfig(min_samples=5, threshold=3.0)]
        ))
        # Use varied values so std is non-trivial
        base_values = [10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.2, 9.8, 10.0]
        for v in base_values:
            dp = DataPoint(value=v, metric_name="m1")
            engine.add_data_point(dp)
        normal = DataPoint(value=10.1, metric_name="m1")
        result = engine.add_data_point(normal)
        assert result is None

    def test_add_data_point_anomalous(self):
        engine = DetectorEngine(AnomalyConfig(
            detectors=[DetectorConfig(min_samples=5, threshold=2.0)]
        ))
        for i in range(15):
            dp = DataPoint(value=10.0, metric_name="m1")
            engine.add_data_point(dp)
        anomalous = DataPoint(value=100.0, metric_name="m1")
        result = engine.add_data_point(anomalous)
        assert result is not None
        assert result.is_anomaly is True
        assert result.score > 2.0

    def test_batch_detect(self):
        engine = DetectorEngine(AnomalyConfig(
            detectors=[DetectorConfig(min_samples=5, threshold=2.0)]
        ))
        points = [DataPoint(value=10.0, metric_name="b1") for _ in range(15)]
        points.append(DataPoint(value=100.0, metric_name="b1"))
        results = engine.batch_detect(points)
        assert len(results) >= 1
        assert all(r.is_anomaly for r in results)

    def test_get_baseline_empty(self):
        baseline = self.engine.get_baseline("nonexistent")
        assert baseline["count"] == 0

    def test_get_baseline_with_data(self):
        engine = DetectorEngine()
        for v in [10.0, 20.0, 30.0]:
            engine.add_data_point(DataPoint(value=v, metric_name="bl"))
        baseline = engine.get_baseline("bl")
        assert baseline["count"] == 3
        assert baseline["mean"] == 20.0
        assert baseline["min"] == 10.0
        assert baseline["max"] == 30.0

    def test_multiple_methods(self):
        engine = DetectorEngine(AnomalyConfig(
            detectors=[
                DetectorConfig(method=DetectionMethod.ZSCORE, min_samples=5, threshold=2.0),
                DetectorConfig(method=DetectionMethod.IQR, min_samples=5, threshold=1.5),
            ]
        ))
        for _ in range(15):
            engine.add_data_point(DataPoint(value=10.0, metric_name="mm"))
        result = engine.add_data_point(DataPoint(value=100.0, metric_name="mm"))
        assert result is not None
        assert result.is_anomaly


# ── Stream Monitor Tests ─────────────────────────────────────────────


class TestStreamMonitor:
    """Tests for stream monitoring lifecycle."""

    def setup_method(self):
        self.monitor = StreamMonitor()
        self.config = StreamConfig(
            metric_name="cpu_usage",
            detector_config=DetectorConfig(min_samples=5, threshold=2.0),
        )

    def test_register_stream(self):
        sid = self.monitor.register_stream(self.config)
        assert len(sid) == 16

    def test_ingest_unregistered_metric(self):
        result = self.monitor.ingest("unknown_metric", 42.0)
        assert result is None

    def test_ingest_normal_values(self):
        sid = self.monitor.register_stream(self.config)
        # Use varied values so std is non-trivial
        base_vals = [50.0, 50.3, 49.7, 50.1, 49.9, 50.2, 49.8, 50.1, 49.9, 50.0]
        for v in base_vals:
            self.monitor.ingest("cpu_usage", v)
        # A value well within the normal range should not trigger anomaly
        result = self.monitor.ingest("cpu_usage", 50.1)
        assert result is None

    def test_ingest_anomalous_value(self):
        sid = self.monitor.register_stream(self.config)
        for _ in range(15):
            self.monitor.ingest("cpu_usage", 50.0)
        result = self.monitor.ingest("cpu_usage", 200.0)
        assert result is not None
        assert result.is_anomaly

    def test_get_stream_status(self):
        sid = self.monitor.register_stream(self.config)
        self.monitor.ingest("cpu_usage", 50.0)
        status = self.monitor.get_stream_status(sid)
        assert status["stream_id"] == sid
        assert status["metric_name"] == "cpu_usage"
        assert status["data_count"] == 1
        assert status["paused"] is False

    def test_get_stream_status_not_found(self):
        status = self.monitor.get_stream_status("nonexistent")
        assert "error" in status

    def test_get_recent_anomalies_empty(self):
        sid = self.monitor.register_stream(self.config)
        anomalies = self.monitor.get_recent_anomalies(sid)
        assert anomalies == []

    def test_get_recent_anomalies_with_data(self):
        sid = self.monitor.register_stream(self.config)
        for _ in range(15):
            self.monitor.ingest("cpu_usage", 50.0)
        self.monitor.ingest("cpu_usage", 200.0)
        anomalies = self.monitor.get_recent_anomalies(sid, limit=5)
        assert len(anomalies) >= 1

    def test_get_recent_anomalies_nonexistent(self):
        assert self.monitor.get_recent_anomalies("nope") == []

    def test_pause_stream(self):
        sid = self.monitor.register_stream(self.config)
        self.monitor.pause_stream(sid)
        status = self.monitor.get_stream_status(sid)
        assert status["paused"] is True

    def test_pause_ignores_data(self):
        sid = self.monitor.register_stream(self.config)
        for _ in range(15):
            self.monitor.ingest("cpu_usage", 50.0)
        self.monitor.pause_stream(sid)
        result = self.monitor.ingest("cpu_usage", 500.0)
        assert result is None

    def test_resume_stream(self):
        sid = self.monitor.register_stream(self.config)
        self.monitor.pause_stream(sid)
        self.monitor.resume_stream(sid)
        status = self.monitor.get_stream_status(sid)
        assert status["paused"] is False

    def test_stream_statistics_empty(self):
        stats = self.monitor.stream_statistics()
        assert stats["total_streams"] == 0
        assert stats["active_streams"] == 0

    def test_stream_statistics_with_streams(self):
        self.monitor.register_stream(self.config)
        cfg2 = StreamConfig(metric_name="mem_usage")
        self.monitor.register_stream(cfg2)
        stats = self.monitor.stream_statistics()
        assert stats["total_streams"] == 2
        assert stats["active_streams"] == 2
        assert stats["paused_streams"] == 0

    def test_stream_statistics_with_paused(self):
        sid = self.monitor.register_stream(self.config)
        self.monitor.pause_stream(sid)
        stats = self.monitor.stream_statistics()
        assert stats["paused_streams"] == 1
        assert stats["active_streams"] == 0

    def test_ingest_with_custom_timestamp(self):
        sid = self.monitor.register_stream(self.config)
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.monitor.ingest("cpu_usage", 50.0, timestamp=ts)
        status = self.monitor.get_stream_status(sid)
        assert status["last_ingest_at"] == ts.isoformat()


# ── Pattern Analyzer Tests ───────────────────────────────────────────


class TestPatternAnalyzer:
    """Tests for trading pattern anomaly detection."""

    def setup_method(self):
        self.analyzer = PatternAnalyzer(zscore_threshold=2.0)

    def test_volume_pattern_too_short(self):
        anomalies = self.analyzer.analyze_volume_pattern("AAPL", [100.0, 200.0])
        assert anomalies == []

    def test_volume_pattern_no_anomaly(self):
        volumes = [100.0, 101.0, 99.0, 100.5, 100.2, 99.8, 100.0]
        anomalies = self.analyzer.analyze_volume_pattern("AAPL", volumes)
        assert len(anomalies) == 0

    def test_volume_pattern_with_anomaly(self):
        volumes = [100.0] * 20 + [500.0]
        anomalies = self.analyzer.analyze_volume_pattern("AAPL", volumes)
        assert len(anomalies) >= 1
        assert anomalies[0].deviation_score > 2.0
        assert anomalies[0].pattern.pattern_type == "volume_anomaly"

    def test_volume_pattern_constant(self):
        volumes = [100.0] * 10
        anomalies = self.analyzer.analyze_volume_pattern("AAPL", volumes)
        assert anomalies == []

    def test_price_pattern_too_short(self):
        anomalies = self.analyzer.analyze_price_pattern("AAPL", [100.0, 101.0])
        assert anomalies == []

    def test_price_pattern_no_anomaly(self):
        prices = [100.0, 100.1, 100.2, 100.1, 100.0, 100.1, 100.2]
        anomalies = self.analyzer.analyze_price_pattern("AAPL", prices)
        assert len(anomalies) == 0

    def test_price_pattern_with_spike(self):
        prices = [100.0, 100.1, 100.0, 99.9, 100.0, 100.1, 99.9, 100.0, 100.0, 100.1, 130.0, 100.0]
        anomalies = self.analyzer.analyze_price_pattern("AAPL", prices)
        assert len(anomalies) >= 1

    def test_price_pattern_constant(self):
        prices = [100.0] * 10
        anomalies = self.analyzer.analyze_price_pattern("AAPL", prices)
        assert anomalies == []

    def test_detect_regime_change_short_series(self):
        series = [1.0] * 5
        result = self.analyzer.detect_regime_change(series, window=10)
        assert result == []

    def test_detect_regime_change_no_change(self):
        series = [10.0] * 40
        result = self.analyzer.detect_regime_change(series, window=10)
        assert result == []

    def test_detect_regime_change_with_shift(self):
        import random
        random.seed(42)
        # Use slight variation so std != 0
        series = [10.0 + random.gauss(0, 0.5) for _ in range(30)] + \
                 [50.0 + random.gauss(0, 0.5) for _ in range(30)]
        result = self.analyzer.detect_regime_change(series, window=10)
        assert len(result) >= 1
        # Change should be detected near index 30
        assert any(20 <= idx <= 40 for idx in result)

    def test_compare_to_baseline_zero_baseline(self):
        score = self.analyzer.compare_to_baseline(10.0, 0.0)
        assert score == float("inf")

    def test_compare_to_baseline_zero_both(self):
        score = self.analyzer.compare_to_baseline(0.0, 0.0)
        assert score == 0.0

    def test_compare_to_baseline_normal(self):
        score = self.analyzer.compare_to_baseline(120.0, 100.0)
        assert score == 0.2

    def test_compare_to_baseline_equal(self):
        score = self.analyzer.compare_to_baseline(100.0, 100.0)
        assert score == 0.0

    def test_get_pattern_history_empty(self):
        history = self.analyzer.get_pattern_history("XYZ")
        assert history == []

    def test_get_pattern_history_after_detection(self):
        volumes = [100.0] * 20 + [500.0]
        self.analyzer.analyze_volume_pattern("TSLA", volumes)
        history = self.analyzer.get_pattern_history("TSLA")
        assert len(history) >= 1
        assert history[0].symbols == ["TSLA"]

    def test_pattern_dataclass_defaults(self):
        p = TradingPattern()
        assert len(p.pattern_id) == 16
        assert p.pattern_type == ""
        assert p.symbols == []

    def test_pattern_anomaly_dataclass(self):
        pa = PatternAnomaly(deviation_score=3.5, expected=100.0, actual=200.0)
        assert pa.deviation_score == 3.5
        assert len(pa.anomaly_id) == 16


# ── Anomaly Manager Tests ───────────────────────────────────────────


class TestAnomalyManager:
    """Tests for anomaly lifecycle management."""

    def setup_method(self):
        self.manager = AnomalyManager()
        self.sample_result = AnomalyResult(
            data_point=DataPoint(value=100.0, metric_name="cpu"),
            method=DetectionMethod.ZSCORE,
            score=4.5,
            severity=AnomalySeverity.HIGH,
            is_anomaly=True,
        )

    def test_record_anomaly(self):
        record = self.manager.record_anomaly(self.sample_result)
        assert len(record.record_id) == 16
        assert record.status == AnomalyStatus.DETECTED
        assert record.anomaly_result == self.sample_result

    def test_update_status(self):
        record = self.manager.record_anomaly(self.sample_result)
        updated = self.manager.update_status(
            record.record_id, AnomalyStatus.INVESTIGATING, "Checking"
        )
        assert updated.status == AnomalyStatus.INVESTIGATING
        assert updated.notes == "Checking"

    def test_update_status_resolved_sets_timestamp(self):
        record = self.manager.record_anomaly(self.sample_result)
        updated = self.manager.update_status(
            record.record_id, AnomalyStatus.RESOLVED, "Fixed"
        )
        assert updated.status == AnomalyStatus.RESOLVED
        assert updated.resolved_at is not None

    def test_update_status_not_found(self):
        with pytest.raises(KeyError):
            self.manager.update_status("nonexistent", AnomalyStatus.RESOLVED)

    def test_get_open_anomalies(self):
        r1 = self.manager.record_anomaly(self.sample_result)
        r2 = self.manager.record_anomaly(self.sample_result)
        self.manager.update_status(r1.record_id, AnomalyStatus.RESOLVED)
        open_list = self.manager.get_open_anomalies()
        assert len(open_list) == 1
        assert open_list[0].record_id == r2.record_id

    def test_get_open_anomalies_excludes_false_positive(self):
        r1 = self.manager.record_anomaly(self.sample_result)
        self.manager.mark_false_positive(r1.record_id, "Not real")
        open_list = self.manager.get_open_anomalies()
        assert len(open_list) == 0

    def test_mark_false_positive(self):
        record = self.manager.record_anomaly(self.sample_result)
        fp = self.manager.mark_false_positive(record.record_id, "Test noise")
        assert fp.status == AnomalyStatus.FALSE_POSITIVE
        assert fp.notes == "Test noise"
        assert fp.resolved_at is not None

    def test_mark_false_positive_not_found(self):
        with pytest.raises(KeyError):
            self.manager.mark_false_positive("nonexistent")

    def test_anomaly_statistics_empty(self):
        stats = self.manager.anomaly_statistics()
        assert stats["total"] == 0
        assert stats["open"] == 0
        assert stats["resolved"] == 0
        assert stats["false_positives"] == 0

    def test_anomaly_statistics_mixed(self):
        r1 = self.manager.record_anomaly(self.sample_result)
        r2 = self.manager.record_anomaly(self.sample_result)
        r3 = self.manager.record_anomaly(self.sample_result)
        self.manager.update_status(r1.record_id, AnomalyStatus.RESOLVED)
        self.manager.mark_false_positive(r2.record_id, "noise")
        stats = self.manager.anomaly_statistics()
        assert stats["total"] == 3
        assert stats["open"] == 1
        assert stats["resolved"] == 1
        assert stats["false_positives"] == 1

    def test_anomaly_statistics_with_period(self):
        r1 = self.manager.record_anomaly(self.sample_result)
        # Backdate one record
        r1.created_at = datetime.now(timezone.utc) - timedelta(days=30)
        r2 = self.manager.record_anomaly(self.sample_result)
        stats = self.manager.anomaly_statistics(period=timedelta(days=7))
        assert stats["total"] == 1

    def test_severity_distribution_empty(self):
        dist = self.manager.severity_distribution()
        assert dist == {}

    def test_severity_distribution(self):
        self.manager.record_anomaly(self.sample_result)
        low_result = AnomalyResult(
            severity=AnomalySeverity.LOW,
            is_anomaly=True,
        )
        self.manager.record_anomaly(low_result)
        self.manager.record_anomaly(self.sample_result)
        dist = self.manager.severity_distribution()
        assert dist["high"] == 2
        assert dist["low"] == 1

    def test_top_anomalous_metrics_empty(self):
        top = self.manager.top_anomalous_metrics()
        assert top == []

    def test_top_anomalous_metrics(self):
        for _ in range(3):
            r = AnomalyResult(
                data_point=DataPoint(value=1.0, metric_name="cpu"),
                is_anomaly=True,
            )
            self.manager.record_anomaly(r)
        for _ in range(5):
            r = AnomalyResult(
                data_point=DataPoint(value=1.0, metric_name="memory"),
                is_anomaly=True,
            )
            self.manager.record_anomaly(r)
        top = self.manager.top_anomalous_metrics(limit=2)
        assert len(top) == 2
        assert top[0]["metric_name"] == "memory"
        assert top[0]["anomaly_count"] == 5
        assert top[1]["metric_name"] == "cpu"
        assert top[1]["anomaly_count"] == 3

    def test_anomaly_record_dataclass(self):
        record = AnomalyRecord()
        assert len(record.record_id) == 16
        assert record.status == AnomalyStatus.DETECTED
        assert record.assigned_to is None
        assert record.notes == ""
        assert record.resolved_at is None

    def test_full_lifecycle(self):
        """Test a complete anomaly lifecycle: detect -> investigate -> resolve."""
        record = self.manager.record_anomaly(self.sample_result)
        assert record.status == AnomalyStatus.DETECTED

        self.manager.update_status(
            record.record_id, AnomalyStatus.CONFIRMED, "Confirmed by analysis"
        )
        assert record.status == AnomalyStatus.CONFIRMED

        self.manager.update_status(
            record.record_id, AnomalyStatus.INVESTIGATING, "Team assigned"
        )
        assert record.status == AnomalyStatus.INVESTIGATING

        self.manager.update_status(
            record.record_id, AnomalyStatus.RESOLVED, "Root cause fixed"
        )
        assert record.status == AnomalyStatus.RESOLVED
        assert record.resolved_at is not None

        open_list = self.manager.get_open_anomalies()
        assert len(open_list) == 0
