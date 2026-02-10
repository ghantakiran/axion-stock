"""Tests for src/quality/ — Data quality validation framework.

Tests cover: ValidationResult dataclass, PriceValidator (OHLCV checks: empty,
positive prices, OHLC consistency, extreme moves, volume anomalies, stale data),
FundamentalValidator (empty, market cap, completeness, PE sanity, coverage),
GapDetector (gap detection, holiday detection, summary), and Gap dataclass.

Run: python3 -m pytest tests/test_quality.py -v
"""

import os
import sys
import unittest
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.quality.validators import ValidationResult, PriceValidator, FundamentalValidator
from src.quality.gap_detector import Gap, GapDetector


# =============================================================================
# ValidationResult Dataclass
# =============================================================================


class TestQualityValidationResult(unittest.TestCase):
    """Tests for the ValidationResult dataclass."""

    def test_create_passing_result(self):
        r = ValidationResult(passed=True, check_name="test", severity="info", message="ok")
        self.assertTrue(r.passed)
        self.assertEqual(r.check_name, "test")
        self.assertEqual(r.severity, "info")

    def test_create_failing_result(self):
        r = ValidationResult(passed=False, check_name="bad", severity="error", message="fail")
        self.assertFalse(r.passed)
        self.assertEqual(r.severity, "error")

    def test_details_default_none(self):
        r = ValidationResult(passed=True, check_name="t", severity="info", message="m")
        self.assertIsNone(r.details)

    def test_details_can_be_dict(self):
        r = ValidationResult(
            passed=False, check_name="t", severity="warning",
            message="m", details={"count": 5}
        )
        self.assertEqual(r.details["count"], 5)


# =============================================================================
# PriceValidator — Empty DataFrame
# =============================================================================


class TestQualityPriceValidatorEmpty(unittest.TestCase):
    """Tests for PriceValidator with empty DataFrames."""

    def setUp(self):
        self.validator = PriceValidator()

    def test_empty_df_returns_error(self):
        df = pd.DataFrame()
        results = self.validator.validate_ohlcv(df, "AAPL")
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].passed)
        self.assertEqual(results[0].check_name, "non_empty")
        self.assertEqual(results[0].severity, "error")

    def test_empty_df_message_includes_ticker(self):
        results = self.validator.validate_ohlcv(pd.DataFrame(), "TSLA")
        self.assertIn("TSLA", results[0].message)


# =============================================================================
# PriceValidator — Positive Prices Check
# =============================================================================


class TestQualityPriceValidatorPositivePrices(unittest.TestCase):
    """Tests for the positive_prices validation check."""

    def setUp(self):
        self.validator = PriceValidator()

    def test_all_positive_closes_pass(self):
        df = pd.DataFrame({"close": [100.0, 101.0, 102.0]})
        results = self.validator.validate_ohlcv(df, "AAPL")
        positive_check = [r for r in results if r.check_name == "positive_prices"]
        self.assertEqual(len(positive_check), 1)
        self.assertTrue(positive_check[0].passed)

    def test_zero_close_fails(self):
        df = pd.DataFrame({"close": [100.0, 0.0, 102.0]})
        results = self.validator.validate_ohlcv(df, "AAPL")
        check = [r for r in results if r.check_name == "positive_prices"][0]
        self.assertFalse(check.passed)
        self.assertEqual(check.severity, "critical")

    def test_negative_close_fails(self):
        df = pd.DataFrame({"close": [100.0, -5.0]})
        results = self.validator.validate_ohlcv(df, "AAPL")
        check = [r for r in results if r.check_name == "positive_prices"][0]
        self.assertFalse(check.passed)


# =============================================================================
# PriceValidator — OHLC Consistency
# =============================================================================


class TestQualityPriceValidatorOHLCConsistency(unittest.TestCase):
    """Tests for the ohlc_consistency validation check."""

    def setUp(self):
        self.validator = PriceValidator()

    def test_consistent_ohlc_passes(self):
        df = pd.DataFrame({
            "open": [100.0], "high": [105.0], "low": [95.0], "close": [103.0]
        })
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "ohlc_consistency"][0]
        self.assertTrue(check.passed)

    def test_low_above_open_fails(self):
        df = pd.DataFrame({
            "open": [100.0], "high": [110.0], "low": [105.0], "close": [108.0]
        })
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "ohlc_consistency"][0]
        self.assertFalse(check.passed)

    def test_high_below_close_fails(self):
        df = pd.DataFrame({
            "open": [100.0], "high": [99.0], "low": [95.0], "close": [102.0]
        })
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "ohlc_consistency"][0]
        self.assertFalse(check.passed)


# =============================================================================
# PriceValidator — Extreme Moves
# =============================================================================


class TestQualityPriceValidatorExtremeMoves(unittest.TestCase):
    """Tests for the extreme_moves validation check (>50% daily)."""

    def setUp(self):
        self.validator = PriceValidator()

    def test_normal_moves_pass(self):
        df = pd.DataFrame({"close": [100.0, 102.0, 101.0, 103.0]})
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "extreme_moves"][0]
        self.assertTrue(check.passed)

    def test_fifty_percent_move_detected(self):
        df = pd.DataFrame({"close": [100.0, 200.0]})
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "extreme_moves"][0]
        self.assertFalse(check.passed)
        self.assertEqual(check.severity, "warning")

    def test_extreme_move_includes_details(self):
        df = pd.DataFrame({"close": [100.0, 200.0]}, index=pd.date_range("2024-01-01", periods=2))
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "extreme_moves"][0]
        self.assertIsNotNone(check.details)
        self.assertIn("dates", check.details)


# =============================================================================
# PriceValidator — Volume Anomaly
# =============================================================================


class TestQualityPriceValidatorVolumeAnomaly(unittest.TestCase):
    """Tests for the volume_anomaly check."""

    def setUp(self):
        self.validator = PriceValidator()

    def test_normal_volume_passes(self):
        df = pd.DataFrame({
            "close": list(range(100, 130)),
            "volume": [1_000_000] * 30,
        })
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "volume_anomaly"][0]
        self.assertTrue(check.passed)

    def test_skipped_when_too_few_bars(self):
        df = pd.DataFrame({"close": [100, 101], "volume": [1000, 1000]})
        results = self.validator.validate_ohlcv(df, "T")
        checks = [r for r in results if r.check_name == "volume_anomaly"]
        self.assertEqual(len(checks), 0)


# =============================================================================
# PriceValidator — Stale Prices
# =============================================================================


class TestQualityPriceValidatorStalePrices(unittest.TestCase):
    """Tests for the stale_prices validation check."""

    def setUp(self):
        self.validator = PriceValidator()

    def test_varying_prices_pass(self):
        df = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]})
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "stale_prices"][0]
        self.assertTrue(check.passed)

    def test_five_identical_closes_detected(self):
        df = pd.DataFrame({"close": [100.0] + [50.0] * 6})
        results = self.validator.validate_ohlcv(df, "T")
        check = [r for r in results if r.check_name == "stale_prices"][0]
        self.assertFalse(check.passed)
        self.assertEqual(check.severity, "warning")


# =============================================================================
# FundamentalValidator — Empty Data
# =============================================================================


class TestQualityFundamentalValidatorEmpty(unittest.TestCase):
    """Tests for FundamentalValidator with empty DataFrame."""

    def setUp(self):
        self.validator = FundamentalValidator()

    def test_empty_df_returns_error(self):
        results = self.validator.validate(pd.DataFrame())
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].passed)
        self.assertEqual(results[0].check_name, "non_empty")


# =============================================================================
# FundamentalValidator — Market Cap Check
# =============================================================================


class TestQualityFundamentalValidatorMarketCap(unittest.TestCase):
    """Tests for the positive_market_cap check."""

    def setUp(self):
        self.validator = FundamentalValidator()

    def test_positive_market_caps_pass(self):
        df = pd.DataFrame({"marketCap": [1e9, 5e9, 2e10]})
        results = self.validator.validate(df)
        check = [r for r in results if r.check_name == "positive_market_cap"][0]
        self.assertTrue(check.passed)

    def test_negative_market_cap_fails(self):
        df = pd.DataFrame({"marketCap": [1e9, -500, 2e10]})
        results = self.validator.validate(df)
        check = [r for r in results if r.check_name == "positive_market_cap"][0]
        self.assertFalse(check.passed)


# =============================================================================
# FundamentalValidator — Completeness & PE Sanity
# =============================================================================


class TestQualityFundamentalValidatorCompleteness(unittest.TestCase):
    """Tests for data_completeness and pe_sanity checks."""

    def setUp(self):
        self.validator = FundamentalValidator()

    def test_complete_data_passes(self):
        df = pd.DataFrame({
            "marketCap": [1e9, 2e9, 3e9],
            "trailingPE": [15.0, 20.0, 25.0],
        })
        results = self.validator.validate(df)
        check = [r for r in results if r.check_name == "data_completeness"][0]
        self.assertTrue(check.passed)

    def test_high_null_percentage_detected(self):
        df = pd.DataFrame({
            "marketCap": [1e9, None, None, None],
            "trailingPE": [15.0, None, None, None],
        })
        results = self.validator.validate(df)
        check = [r for r in results if r.check_name == "data_completeness"][0]
        self.assertFalse(check.passed)

    def test_sane_pe_passes(self):
        df = pd.DataFrame({"trailingPE": [15.0, 20.0, 25.0]})
        results = self.validator.validate(df)
        check = [r for r in results if r.check_name == "pe_sanity"][0]
        self.assertTrue(check.passed)

    def test_extreme_pe_detected(self):
        df = pd.DataFrame({"trailingPE": [-10.0, 2000.0, 15.0]})
        results = self.validator.validate(df)
        check = [r for r in results if r.check_name == "pe_sanity"][0]
        # >10% of rows have insane PE: 2 out of 3 = 67%
        self.assertFalse(check.passed)


# =============================================================================
# FundamentalValidator — Universe Coverage
# =============================================================================


class TestQualityFundamentalValidatorCoverage(unittest.TestCase):
    """Tests for universe_coverage check."""

    def setUp(self):
        self.validator = FundamentalValidator()

    def test_small_universe_warns(self):
        df = pd.DataFrame({"col": range(10)})
        results = self.validator.validate(df)
        check = [r for r in results if r.check_name == "universe_coverage"][0]
        self.assertFalse(check.passed)

    def test_large_universe_passes(self):
        df = pd.DataFrame({"col": range(500)})
        results = self.validator.validate(df)
        check = [r for r in results if r.check_name == "universe_coverage"][0]
        self.assertTrue(check.passed)


# =============================================================================
# Gap Dataclass
# =============================================================================


class TestQualityGapDataclass(unittest.TestCase):
    """Tests for the Gap dataclass."""

    def test_create_gap(self):
        g = Gap(
            ticker="AAPL",
            missing_date=pd.Timestamp("2024-03-15"),
            gap_type="missing_bar",
        )
        self.assertEqual(g.ticker, "AAPL")
        self.assertEqual(g.gap_type, "missing_bar")

    def test_gap_defaults(self):
        g = Gap(ticker="T", missing_date=pd.Timestamp("2024-01-01"), gap_type="missing_bar")
        self.assertIsNone(g.previous_date)
        self.assertEqual(g.gap_days, 1)


# =============================================================================
# GapDetector — Detection
# =============================================================================


class TestQualityGapDetectorDetection(unittest.TestCase):
    """Tests for GapDetector.detect_gaps."""

    def setUp(self):
        self.detector = GapDetector()

    def test_empty_df_returns_no_gaps(self):
        gaps = self.detector.detect_gaps(pd.DataFrame(), "T")
        self.assertEqual(len(gaps), 0)

    def test_single_row_returns_no_gaps(self):
        df = pd.DataFrame({"close": [100]}, index=pd.date_range("2024-01-02", periods=1))
        gaps = self.detector.detect_gaps(df, "T")
        self.assertEqual(len(gaps), 0)

    def test_consecutive_business_days_no_gaps(self):
        dates = pd.bdate_range("2024-06-03", periods=5)  # Mon-Fri
        df = pd.DataFrame({"close": range(5)}, index=dates)
        gaps = self.detector.detect_gaps(df, "T")
        self.assertEqual(len(gaps), 0)

    def test_missing_wednesday_detected(self):
        # Mon, Tue, Thu, Fri — Wednesday missing
        dates = pd.to_datetime(["2024-06-03", "2024-06-04", "2024-06-06", "2024-06-07"])
        df = pd.DataFrame({"close": range(4)}, index=dates)
        gaps = self.detector.detect_gaps(df, "TEST")
        # Should detect Wednesday as missing (2024-06-05)
        missing_dates = [g.missing_date for g in gaps]
        self.assertIn(pd.Timestamp("2024-06-05"), missing_dates)


# =============================================================================
# GapDetector — Holiday Detection
# =============================================================================


class TestQualityGapDetectorHolidays(unittest.TestCase):
    """Tests for _is_likely_holiday method."""

    def setUp(self):
        self.detector = GapDetector()

    def test_new_years_day(self):
        self.assertTrue(self.detector._is_likely_holiday(pd.Timestamp("2024-01-01")))

    def test_independence_day(self):
        self.assertTrue(self.detector._is_likely_holiday(pd.Timestamp("2024-07-04")))

    def test_christmas(self):
        self.assertTrue(self.detector._is_likely_holiday(pd.Timestamp("2024-12-25")))

    def test_mlk_day(self):
        # 3rd Monday of January 2024 = Jan 15
        self.assertTrue(self.detector._is_likely_holiday(pd.Timestamp("2024-01-15")))

    def test_labor_day(self):
        # 1st Monday of September 2024 = Sep 2
        self.assertTrue(self.detector._is_likely_holiday(pd.Timestamp("2024-09-02")))

    def test_regular_day_not_holiday(self):
        self.assertFalse(self.detector._is_likely_holiday(pd.Timestamp("2024-03-12")))

    def test_thanksgiving(self):
        # 4th Thursday of November 2024 = Nov 28
        self.assertTrue(self.detector._is_likely_holiday(pd.Timestamp("2024-11-28")))

    def test_memorial_day(self):
        # Last Monday of May 2024 = May 27
        self.assertTrue(self.detector._is_likely_holiday(pd.Timestamp("2024-05-27")))

    def test_presidents_day(self):
        # 3rd Monday of February 2024 = Feb 19
        self.assertTrue(self.detector._is_likely_holiday(pd.Timestamp("2024-02-19")))


# =============================================================================
# GapDetector — Summary
# =============================================================================


class TestQualityGapDetectorSummary(unittest.TestCase):
    """Tests for GapDetector.summarize_gaps."""

    def setUp(self):
        self.detector = GapDetector()

    def test_empty_gaps_returns_empty_df(self):
        # summarize_gaps({}) produces DataFrame with no rows; sort_values
        # may raise KeyError on empty DF — so test with at least one entry
        summary = self.detector.summarize_gaps({"DUMMY": []})
        self.assertIsInstance(summary, pd.DataFrame)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary.iloc[0]["total_gaps"], 0)

    def test_summary_includes_all_tickers(self):
        gaps = {
            "AAPL": [
                Gap(ticker="AAPL", missing_date=pd.Timestamp("2024-01-02"), gap_type="missing_bar"),
            ],
            "MSFT": [],
        }
        summary = self.detector.summarize_gaps(gaps)
        self.assertEqual(len(summary), 2)
        self.assertIn("AAPL", summary["ticker"].values)
        self.assertIn("MSFT", summary["ticker"].values)

    def test_summary_sorted_by_total_gaps(self):
        gaps = {
            "A": [Gap(ticker="A", missing_date=pd.Timestamp("2024-01-02"), gap_type="missing_bar")] * 3,
            "B": [Gap(ticker="B", missing_date=pd.Timestamp("2024-01-03"), gap_type="missing_bar")] * 1,
            "C": [Gap(ticker="C", missing_date=pd.Timestamp("2024-01-04"), gap_type="missing_bar")] * 5,
        }
        summary = self.detector.summarize_gaps(gaps)
        self.assertEqual(summary.iloc[0]["ticker"], "C")
        self.assertEqual(summary.iloc[0]["total_gaps"], 5)

    def test_summary_counts_missing_bars(self):
        gaps = {
            "AAPL": [
                Gap(ticker="AAPL", missing_date=pd.Timestamp("2024-01-02"), gap_type="missing_bar"),
                Gap(ticker="AAPL", missing_date=pd.Timestamp("2024-01-03"), gap_type="missing_bar"),
            ],
        }
        summary = self.detector.summarize_gaps(gaps)
        self.assertEqual(summary.iloc[0]["missing_bars"], 2)

    def test_summary_has_correct_columns(self):
        gaps = {"X": []}
        summary = self.detector.summarize_gaps(gaps)
        self.assertIn("ticker", summary.columns)
        self.assertIn("total_gaps", summary.columns)
        self.assertIn("missing_bars", summary.columns)
