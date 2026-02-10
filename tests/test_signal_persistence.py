"""Tests for Signal Persistence & Audit Trail (PRD-162).

9 test classes, ~55 tests covering models, store, recorder, query builder,
and module imports for the full signal pipeline audit trail.
"""

from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta, timezone

from src.signal_persistence.models import (
    ExecutionRecord,
    FusionRecord,
    PersistenceConfig,
    RiskDecisionRecord,
    SignalRecord,
    SignalStatus,
)
from src.signal_persistence.store import SignalStore
from src.signal_persistence.recorder import SignalRecorder
from src.signal_persistence.query import SignalQuery, SignalQueryBuilder


# ── Helpers ──────────────────────────────────────────────────────────


def _make_signal(
    source: str = "ema_cloud",
    ticker: str = "AAPL",
    direction: str = "bullish",
    strength: float = 75.0,
    confidence: float = 0.85,
    status: SignalStatus = SignalStatus.GENERATED,
    timestamp: datetime | None = None,
) -> SignalRecord:
    return SignalRecord(
        source=source,
        ticker=ticker,
        direction=direction,
        strength=strength,
        confidence=confidence,
        status=status,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


def _make_fusion(
    ticker: str = "AAPL",
    input_signal_ids: list[str] | None = None,
    direction: str = "bullish",
    composite_score: float = 72.0,
    confidence: float = 0.80,
    source_count: int = 3,
) -> FusionRecord:
    return FusionRecord(
        ticker=ticker,
        input_signal_ids=input_signal_ids or ["s1", "s2", "s3"],
        direction=direction,
        composite_score=composite_score,
        confidence=confidence,
        source_count=source_count,
        agreement_ratio=0.67,
    )


# ── TestSignalStatus ─────────────────────────────────────────────────


class TestSignalStatus(unittest.TestCase):
    """Tests for the SignalStatus enum."""

    def test_generated_value(self):
        self.assertEqual(SignalStatus.GENERATED.value, "generated")

    def test_executed_value(self):
        self.assertEqual(SignalStatus.EXECUTED.value, "executed")

    def test_expired_value(self):
        self.assertEqual(SignalStatus.EXPIRED.value, "expired")

    def test_all_statuses(self):
        expected = {
            "generated", "collected", "fused", "risk_approved",
            "risk_rejected", "executing", "executed", "expired", "cancelled",
        }
        actual = {s.value for s in SignalStatus}
        self.assertEqual(actual, expected)

    def test_string_comparison(self):
        self.assertEqual(SignalStatus.RISK_APPROVED, "risk_approved")
        self.assertEqual(SignalStatus.RISK_REJECTED, "risk_rejected")


# ── TestSignalRecord ─────────────────────────────────────────────────


class TestSignalRecord(unittest.TestCase):
    """Tests for the SignalRecord dataclass."""

    def test_creation(self):
        rec = SignalRecord(source="ema_cloud", ticker="AAPL", direction="bullish", strength=80.0)
        self.assertEqual(rec.source, "ema_cloud")
        self.assertEqual(rec.ticker, "AAPL")
        self.assertEqual(rec.direction, "bullish")
        self.assertEqual(rec.strength, 80.0)

    def test_defaults(self):
        rec = SignalRecord()
        self.assertEqual(rec.source, "")
        self.assertEqual(rec.direction, "neutral")
        self.assertEqual(rec.strength, 0.0)
        self.assertEqual(rec.confidence, 0.5)
        self.assertEqual(rec.status, SignalStatus.GENERATED)
        self.assertIsNone(rec.fusion_id)
        self.assertIsNone(rec.execution_id)

    def test_signal_id_generation(self):
        r1 = SignalRecord()
        r2 = SignalRecord()
        self.assertNotEqual(r1.signal_id, r2.signal_id)
        self.assertTrue(len(r1.signal_id) > 10)

    def test_timestamp_auto_set(self):
        rec = SignalRecord()
        self.assertIsInstance(rec.timestamp, datetime)
        self.assertIsNotNone(rec.timestamp.tzinfo)

    def test_to_dict(self):
        rec = _make_signal()
        d = rec.to_dict()
        self.assertEqual(d["source"], "ema_cloud")
        self.assertEqual(d["ticker"], "AAPL")
        self.assertEqual(d["direction"], "bullish")
        self.assertEqual(d["strength"], 75.0)
        self.assertEqual(d["status"], "generated")
        self.assertIn("signal_id", d)
        self.assertIn("timestamp", d)

    def test_to_dict_metadata(self):
        rec = SignalRecord(source_metadata={"model": "xgb", "version": 3})
        d = rec.to_dict()
        self.assertEqual(d["source_metadata"]["model"], "xgb")


# ── TestFusionRecord ─────────────────────────────────────────────────


class TestFusionRecord(unittest.TestCase):
    """Tests for the FusionRecord dataclass."""

    def test_creation(self):
        rec = _make_fusion()
        self.assertEqual(rec.ticker, "AAPL")
        self.assertEqual(rec.direction, "bullish")
        self.assertEqual(rec.composite_score, 72.0)
        self.assertEqual(rec.source_count, 3)

    def test_input_signal_ids_tracked(self):
        rec = _make_fusion(input_signal_ids=["sig-a", "sig-b"])
        self.assertEqual(len(rec.input_signal_ids), 2)
        self.assertIn("sig-a", rec.input_signal_ids)

    def test_to_dict(self):
        rec = _make_fusion()
        d = rec.to_dict()
        self.assertIn("fusion_id", d)
        self.assertEqual(d["ticker"], "AAPL")
        self.assertEqual(d["composite_score"], 72.0)
        self.assertIn("input_signal_ids", d)
        self.assertIn("timestamp", d)

    def test_unique_fusion_id(self):
        r1 = FusionRecord()
        r2 = FusionRecord()
        self.assertNotEqual(r1.fusion_id, r2.fusion_id)

    def test_source_weights_used(self):
        rec = FusionRecord(source_weights_used={"ema_cloud": 0.4, "social": 0.6})
        d = rec.to_dict()
        self.assertAlmostEqual(d["source_weights_used"]["ema_cloud"], 0.4, places=3)


# ── TestRiskDecisionRecord ───────────────────────────────────────────


class TestRiskDecisionRecord(unittest.TestCase):
    """Tests for the RiskDecisionRecord dataclass."""

    def test_creation(self):
        rec = RiskDecisionRecord(signal_id="sig-1", approved=True)
        self.assertEqual(rec.signal_id, "sig-1")
        self.assertTrue(rec.approved)

    def test_approved_variant(self):
        rec = RiskDecisionRecord(
            signal_id="sig-1",
            approved=True,
            checks_run=["daily_loss", "max_positions", "correlation"],
            checks_passed=["daily_loss", "max_positions", "correlation"],
        )
        self.assertTrue(rec.approved)
        self.assertEqual(len(rec.checks_passed), 3)
        self.assertEqual(len(rec.checks_failed), 0)
        self.assertIsNone(rec.rejection_reason)

    def test_rejected_variant(self):
        rec = RiskDecisionRecord(
            signal_id="sig-2",
            approved=False,
            rejection_reason="Daily loss limit exceeded",
            checks_run=["daily_loss"],
            checks_failed=[{"check": "daily_loss", "reason": "5.2% >= 5%"}],
        )
        self.assertFalse(rec.approved)
        self.assertIn("Daily loss", rec.rejection_reason)
        self.assertEqual(len(rec.checks_failed), 1)

    def test_to_dict(self):
        rec = RiskDecisionRecord(signal_id="sig-1", approved=True)
        d = rec.to_dict()
        self.assertIn("decision_id", d)
        self.assertEqual(d["signal_id"], "sig-1")
        self.assertTrue(d["approved"])


# ── TestExecutionRecord ──────────────────────────────────────────────


class TestExecutionRecord(unittest.TestCase):
    """Tests for the ExecutionRecord dataclass."""

    def test_creation(self):
        rec = ExecutionRecord(
            signal_id="sig-1", ticker="AAPL", direction="long",
            quantity=100, fill_price=185.50, requested_price=185.00,
        )
        self.assertEqual(rec.ticker, "AAPL")
        self.assertEqual(rec.quantity, 100)
        self.assertEqual(rec.fill_price, 185.50)

    def test_slippage_calculation(self):
        rec = ExecutionRecord(
            fill_price=185.75, requested_price=185.00, slippage=0.75,
        )
        self.assertAlmostEqual(rec.slippage, 0.75)

    def test_config_snapshot(self):
        rec = ExecutionRecord(
            config_snapshot={"max_position_pct": 5.0, "stop_loss": 3.0},
        )
        self.assertEqual(rec.config_snapshot["max_position_pct"], 5.0)

    def test_to_dict(self):
        rec = ExecutionRecord(
            signal_id="sig-1", ticker="NVDA", direction="long",
            quantity=50, fill_price=450.25, requested_price=450.00,
            broker="alpaca", status="filled",
        )
        d = rec.to_dict()
        self.assertEqual(d["ticker"], "NVDA")
        self.assertEqual(d["broker"], "alpaca")
        self.assertEqual(d["status"], "filled")
        self.assertIn("execution_id", d)

    def test_pending_no_fill_timestamp(self):
        rec = ExecutionRecord(status="pending")
        self.assertIsNone(rec.fill_timestamp)
        d = rec.to_dict()
        self.assertIsNone(d["fill_timestamp"])


# ── TestSignalStore ──────────────────────────────────────────────────


class TestSignalStore(unittest.TestCase):
    """Tests for the SignalStore in-memory persistence layer."""

    def setUp(self):
        self.store = SignalStore()

    def test_save_and_get_signal(self):
        sig = _make_signal()
        sid = self.store.save_signal(sig)
        retrieved = self.store.get_signal(sid)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.ticker, "AAPL")

    def test_get_nonexistent_signal(self):
        self.assertIsNone(self.store.get_signal("nonexistent-id"))

    def test_save_and_get_fusion(self):
        fus = _make_fusion()
        fid = self.store.save_fusion(fus)
        retrieved = self.store.get_fusion(fid)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.ticker, "AAPL")

    def test_save_and_get_decision(self):
        dec = RiskDecisionRecord(signal_id="sig-1", approved=True)
        did = self.store.save_decision(dec)
        retrieved = self.store.get_decision(did)
        self.assertIsNotNone(retrieved)
        self.assertTrue(retrieved.approved)

    def test_save_and_get_execution(self):
        exe = ExecutionRecord(
            signal_id="sig-1", ticker="TSLA", direction="long",
            quantity=25, fill_price=250.0,
        )
        eid = self.store.save_execution(exe)
        retrieved = self.store.get_execution(eid)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.ticker, "TSLA")

    def test_link_signal_to_fusion(self):
        sig = _make_signal()
        fus = _make_fusion()
        sid = self.store.save_signal(sig)
        fid = self.store.save_fusion(fus)
        result = self.store.link_signal_to_fusion(sid, fid)
        self.assertTrue(result)
        updated = self.store.get_signal(sid)
        self.assertEqual(updated.fusion_id, fid)
        self.assertEqual(updated.status, SignalStatus.FUSED)

    def test_link_signal_to_execution(self):
        sig = _make_signal()
        exe = ExecutionRecord(signal_id="x", ticker="AAPL")
        sid = self.store.save_signal(sig)
        eid = self.store.save_execution(exe)
        result = self.store.link_signal_to_execution(sid, eid)
        self.assertTrue(result)
        updated = self.store.get_signal(sid)
        self.assertEqual(updated.execution_id, eid)
        self.assertEqual(updated.status, SignalStatus.EXECUTED)

    def test_link_nonexistent_signal(self):
        self.assertFalse(self.store.link_signal_to_fusion("bad-id", "fid"))
        self.assertFalse(self.store.link_signal_to_execution("bad-id", "eid"))

    def test_get_full_trace(self):
        sig = _make_signal()
        sid = self.store.save_signal(sig)
        fus = _make_fusion(input_signal_ids=[sid])
        fid = self.store.save_fusion(fus)
        self.store.link_signal_to_fusion(sid, fid)
        dec = RiskDecisionRecord(signal_id=sid, approved=True)
        self.store.save_decision(dec)
        exe = ExecutionRecord(signal_id=sid, ticker="AAPL")
        eid = self.store.save_execution(exe)
        self.store.link_signal_to_execution(sid, eid)

        trace = self.store.get_full_trace(sid)
        self.assertIn("signal", trace)
        self.assertIn("fusion", trace)
        self.assertIn("risk_decisions", trace)
        self.assertIn("execution", trace)
        self.assertIsNotNone(trace["fusion"])
        self.assertEqual(len(trace["risk_decisions"]), 1)
        self.assertIsNotNone(trace["execution"])

    def test_get_full_trace_not_found(self):
        trace = self.store.get_full_trace("nonexistent")
        self.assertIn("error", trace)

    def test_expire_stale_signals(self):
        old_time = datetime.now(timezone.utc) - timedelta(seconds=600)
        sig = _make_signal(timestamp=old_time)
        self.store.save_signal(sig)
        config = PersistenceConfig(max_signal_age_seconds=300)
        self.store.config = config
        count = self.store.expire_stale_signals()
        self.assertEqual(count, 1)

    def test_expire_only_generated_status(self):
        old_time = datetime.now(timezone.utc) - timedelta(seconds=600)
        sig = _make_signal(timestamp=old_time, status=SignalStatus.EXECUTED)
        self.store.save_signal(sig)
        config = PersistenceConfig(max_signal_age_seconds=300)
        self.store.config = config
        count = self.store.expire_stale_signals()
        self.assertEqual(count, 0)

    def test_get_stats(self):
        self.store.save_signal(_make_signal(ticker="AAPL"))
        self.store.save_signal(_make_signal(ticker="NVDA", source="social"))
        self.store.save_fusion(_make_fusion())
        stats = self.store.get_stats()
        self.assertEqual(stats["total_signals"], 2)
        self.assertEqual(stats["total_fusions"], 1)
        self.assertEqual(stats["unique_tickers"], 2)
        self.assertEqual(stats["unique_sources"], 2)

    def test_get_signals_by_ticker(self):
        self.store.save_signal(_make_signal(ticker="AAPL"))
        self.store.save_signal(_make_signal(ticker="AAPL"))
        self.store.save_signal(_make_signal(ticker="NVDA"))
        results = self.store.get_signals_by_ticker("AAPL")
        self.assertEqual(len(results), 2)

    def test_get_signals_by_source(self):
        self.store.save_signal(_make_signal(source="ema_cloud"))
        self.store.save_signal(_make_signal(source="social"))
        results = self.store.get_signals_by_source("ema_cloud")
        self.assertEqual(len(results), 1)

    def test_get_signals_by_status(self):
        self.store.save_signal(_make_signal(status=SignalStatus.GENERATED))
        self.store.save_signal(_make_signal(status=SignalStatus.EXECUTED))
        results = self.store.get_signals_by_status(SignalStatus.GENERATED)
        self.assertEqual(len(results), 1)

    def test_update_signal_status(self):
        sig = _make_signal()
        sid = self.store.save_signal(sig)
        result = self.store.update_signal_status(sid, SignalStatus.COLLECTED)
        self.assertTrue(result)
        updated = self.store.get_signal(sid)
        self.assertEqual(updated.status, SignalStatus.COLLECTED)

    def test_update_nonexistent_signal_status(self):
        self.assertFalse(self.store.update_signal_status("bad-id", SignalStatus.EXPIRED))


# ── TestSignalRecorder ───────────────────────────────────────────────


class TestSignalRecorder(unittest.TestCase):
    """Tests for the SignalRecorder high-level API."""

    def setUp(self):
        self.recorder = SignalRecorder()

    def test_record_signal(self):
        sid = self.recorder.record_signal(
            source="ema_cloud", ticker="AAPL", direction="bullish", strength=78.0,
        )
        self.assertTrue(len(sid) > 10)
        sig = self.recorder.store.get_signal(sid)
        self.assertEqual(sig.ticker, "AAPL")

    def test_record_fusion_links_signals(self):
        s1 = self.recorder.record_signal("ema_cloud", "AAPL", "bullish", 80.0)
        s2 = self.recorder.record_signal("social", "AAPL", "bullish", 65.0)
        fid = self.recorder.record_fusion(
            ticker="AAPL", input_signal_ids=[s1, s2],
            direction="bullish", composite_score=72.0, confidence=0.8,
        )
        self.assertTrue(len(fid) > 10)
        sig1 = self.recorder.store.get_signal(s1)
        self.assertEqual(sig1.fusion_id, fid)
        self.assertEqual(sig1.status, SignalStatus.FUSED)

    def test_record_risk_decision_approved(self):
        sid = self.recorder.record_signal("ema_cloud", "AAPL", "bullish", 80.0)
        did = self.recorder.record_risk_decision(signal_id=sid, approved=True)
        self.assertTrue(len(did) > 10)
        sig = self.recorder.store.get_signal(sid)
        self.assertEqual(sig.status, SignalStatus.RISK_APPROVED)

    def test_record_risk_decision_rejected(self):
        sid = self.recorder.record_signal("ema_cloud", "AAPL", "bullish", 80.0)
        did = self.recorder.record_risk_decision(
            signal_id=sid, approved=False, rejection_reason="Too many positions",
        )
        sig = self.recorder.store.get_signal(sid)
        self.assertEqual(sig.status, SignalStatus.RISK_REJECTED)

    def test_record_execution(self):
        sid = self.recorder.record_signal("ema_cloud", "AAPL", "bullish", 80.0)
        eid = self.recorder.record_execution(
            signal_id=sid, ticker="AAPL", direction="long",
            quantity=100, fill_price=185.50, requested_price=185.00,
        )
        self.assertTrue(len(eid) > 10)
        sig = self.recorder.store.get_signal(sid)
        self.assertEqual(sig.execution_id, eid)
        self.assertEqual(sig.status, SignalStatus.EXECUTED)
        exe = self.recorder.store.get_execution(eid)
        self.assertAlmostEqual(exe.slippage, 0.50)

    def test_pipeline_trace(self):
        sid = self.recorder.record_signal("ema_cloud", "AAPL", "bullish", 80.0)
        fid = self.recorder.record_fusion(
            ticker="AAPL", input_signal_ids=[sid],
            direction="bullish", composite_score=70.0, confidence=0.75,
        )
        self.recorder.record_risk_decision(signal_id=sid, approved=True, fusion_id=fid)
        self.recorder.record_execution(
            signal_id=sid, ticker="AAPL", direction="long",
            quantity=100, fill_price=185.0, fusion_id=fid,
        )
        trace = self.recorder.get_pipeline_trace(sid)
        self.assertIsNotNone(trace["signal"])
        self.assertIsNotNone(trace["fusion"])
        self.assertIsNotNone(trace["execution"])

    def test_stats(self):
        self.recorder.record_signal("ema_cloud", "AAPL", "bullish", 80.0)
        self.recorder.record_signal("social", "NVDA", "bearish", 60.0)
        stats = self.recorder.get_stats()
        self.assertEqual(stats["total_signals"], 2)


# ── TestSignalQueryBuilder ───────────────────────────────────────────


class TestSignalQueryBuilder(unittest.TestCase):
    """Tests for the fluent SignalQueryBuilder."""

    def setUp(self):
        self.store = SignalStore()
        self.store.save_signal(_make_signal(ticker="AAPL", source="ema_cloud", direction="bullish", strength=80.0))
        self.store.save_signal(_make_signal(ticker="AAPL", source="social", direction="bearish", strength=55.0))
        self.store.save_signal(_make_signal(ticker="NVDA", source="ema_cloud", direction="bullish", strength=90.0))
        self.store.save_signal(_make_signal(ticker="TSLA", source="factor", direction="neutral", strength=40.0))

    def test_filter_by_ticker(self):
        result = SignalQueryBuilder(self.store).ticker("AAPL").execute()
        self.assertEqual(len(result.records), 2)

    def test_filter_by_source(self):
        result = SignalQueryBuilder(self.store).source("ema_cloud").execute()
        self.assertEqual(len(result.records), 2)

    def test_filter_by_direction(self):
        result = SignalQueryBuilder(self.store).direction("bullish").execute()
        self.assertEqual(len(result.records), 2)

    def test_filter_by_min_strength(self):
        result = SignalQueryBuilder(self.store).min_strength(70.0).execute()
        self.assertEqual(len(result.records), 2)

    def test_filter_by_status(self):
        result = SignalQueryBuilder(self.store).status(SignalStatus.GENERATED).execute()
        self.assertEqual(len(result.records), 4)

    def test_limit(self):
        result = SignalQueryBuilder(self.store).limit(2).execute()
        self.assertEqual(len(result.records), 2)

    def test_combined_filters(self):
        result = (
            SignalQueryBuilder(self.store)
            .ticker("AAPL")
            .source("ema_cloud")
            .direction("bullish")
            .execute()
        )
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].ticker, "AAPL")
        self.assertEqual(result.records[0].source, "ema_cloud")

    def test_since_minutes(self):
        result = SignalQueryBuilder(self.store).since_minutes(60).execute()
        self.assertEqual(len(result.records), 4)

    def test_signal_query_tickers(self):
        result = SignalQueryBuilder(self.store).execute()
        tickers = result.tickers
        self.assertIn("AAPL", tickers)
        self.assertIn("NVDA", tickers)

    def test_signal_query_sources(self):
        result = SignalQueryBuilder(self.store).execute()
        sources = result.sources
        self.assertIn("ema_cloud", sources)
        self.assertIn("social", sources)

    def test_to_dicts(self):
        result = SignalQueryBuilder(self.store).ticker("AAPL").execute()
        dicts = result.to_dicts()
        self.assertEqual(len(dicts), 2)
        self.assertIn("signal_id", dicts[0])

    def test_empty_query(self):
        result = SignalQueryBuilder(self.store).ticker("NONEXISTENT").execute()
        self.assertEqual(len(result.records), 0)


# ── TestModuleImports ────────────────────────────────────────────────


class TestSignalPersistenceModuleImports(unittest.TestCase):
    """Tests that all module exports are accessible."""

    def test_all_exports(self):
        import src.signal_persistence as sp
        expected = [
            "SignalRecord", "FusionRecord", "RiskDecisionRecord", "ExecutionRecord",
            "SignalStatus", "PersistenceConfig",
            "SignalStore", "SignalRecorder",
            "SignalQuery", "SignalQueryBuilder",
        ]
        for name in expected:
            self.assertTrue(hasattr(sp, name), f"Missing export: {name}")

    def test_key_classes_importable(self):
        from src.signal_persistence import SignalStore, SignalRecorder, SignalQueryBuilder
        self.assertIsNotNone(SignalStore)
        self.assertIsNotNone(SignalRecorder)
        self.assertIsNotNone(SignalQueryBuilder)


if __name__ == "__main__":
    unittest.main()
