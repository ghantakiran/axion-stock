"""Tests for PRD-97: GIPS-Compliant Performance Reporting."""

import math
from datetime import date, datetime
from unittest.mock import patch

import pytest

from src.performance_report.config import (
    ReturnMethod,
    FeeType,
    CompositeMembership,
    DispersionMethod,
    ReportPeriod,
    GIPSConfig,
    CompositeConfig,
    FeeSchedule,
    LARGE_CASH_FLOW_PCT,
    MIN_HISTORY_YEARS,
    MIN_PORTFOLIOS_DISPERSION,
)
from src.performance_report.models import (
    CompositeDefinition,
    CompositeReturn,
    CompositePeriod,
    DispersionResult,
    GIPSDisclosure,
    ComplianceCheck,
    ComplianceReport,
    GIPSPresentation,
    PortfolioAssignment,
    PerformanceRecord,
)
from src.performance_report.composite import CompositeManager
from src.performance_report.calculator import GIPSCalculator
from src.performance_report.dispersion import DispersionCalculator
from src.performance_report.compliance import ComplianceValidator
from src.performance_report.generator import GIPSReportGenerator


# ── Config Tests ──────────────────────────────────────────────────────


class TestEnums:
    def test_return_methods(self):
        assert len(ReturnMethod) == 4
        assert ReturnMethod.TIME_WEIGHTED.value == "time_weighted"
        assert ReturnMethod.DAILY_VALUATION.value == "daily_valuation"

    def test_fee_types(self):
        assert len(FeeType) == 3
        assert FeeType.BOTH.value == "both"

    def test_composite_membership(self):
        assert len(CompositeMembership) == 3
        assert CompositeMembership.FULL_PERIOD.value == "full_period"

    def test_dispersion_methods(self):
        assert len(DispersionMethod) == 4
        assert DispersionMethod.ASSET_WEIGHTED_STD.value == "asset_weighted_std"

    def test_report_periods(self):
        assert len(ReportPeriod) == 4


class TestFeeSchedule:
    def test_default_tiers(self):
        fs = FeeSchedule()
        assert len(fs.tiers) == 4

    def test_fee_rate_lookup(self):
        fs = FeeSchedule()
        assert fs.get_fee_rate(500_000) == 0.01
        assert fs.get_fee_rate(2_000_000) == 0.0075
        assert fs.get_fee_rate(10_000_000) == 0.005
        assert fs.get_fee_rate(100_000_000) == 0.0035

    def test_custom_schedule(self):
        fs = FeeSchedule(tiers=[
            {"breakpoint": 1_000_000, "rate": 0.02},
            {"breakpoint": float("inf"), "rate": 0.01},
        ])
        assert fs.get_fee_rate(500_000) == 0.02
        assert fs.get_fee_rate(5_000_000) == 0.01


class TestGIPSConfig:
    def test_defaults(self):
        cfg = GIPSConfig()
        assert cfg.return_method == ReturnMethod.DAILY_VALUATION
        assert cfg.fee_type == FeeType.BOTH
        assert cfg.include_3yr_std_dev is True
        assert cfg.verification_status == "Not Verified"

    def test_custom_config(self):
        cfg = GIPSConfig(firm_name="Acme Capital", total_firm_assets=500_000_000)
        assert cfg.firm_name == "Acme Capital"
        assert cfg.total_firm_assets == 500_000_000


# ── Model Tests ───────────────────────────────────────────────────────


class TestPortfolioAssignment:
    def test_creation(self):
        pa = PortfolioAssignment(
            portfolio_id="P1", composite_id="C1",
            join_date=date(2020, 1, 1), market_value=1_000_000,
        )
        assert pa.is_active
        assert pa.leave_date is None

    def test_deactivate(self):
        pa = PortfolioAssignment(
            portfolio_id="P1", composite_id="C1",
            join_date=date(2020, 1, 1),
        )
        pa.is_active = False
        pa.leave_date = date(2023, 6, 30)
        assert not pa.is_active


class TestPerformanceRecord:
    def test_creation(self):
        pr = PerformanceRecord(
            portfolio_id="P1",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            gross_return=0.12,
            net_return=0.11,
            beginning_value=1_000_000,
            ending_value=1_120_000,
        )
        assert pr.gross_return == 0.12
        assert pr.ending_value == 1_120_000


class TestCompositeDefinition:
    def test_active_portfolios(self):
        cd = CompositeDefinition(
            composite_id="C1", name="Test", strategy="Equity",
            benchmark_name="SP500", inception_date=date(2020, 1, 1),
            creation_date=date(2020, 1, 1),
            portfolios=[
                PortfolioAssignment("P1", "C1", date(2020, 1, 1), is_active=True),
                PortfolioAssignment("P2", "C1", date(2020, 1, 1), is_active=False),
                PortfolioAssignment("P3", "C1", date(2021, 1, 1), is_active=True),
            ],
        )
        assert cd.n_portfolios == 2
        assert len(cd.active_portfolios) == 2


class TestCompositeReturn:
    def test_excess_returns(self):
        cr = CompositeReturn(
            composite_id="C1",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            gross_return=0.15,
            net_return=0.14,
            benchmark_return=0.10,
        )
        assert cr.excess_return_gross == pytest.approx(0.05)
        assert cr.excess_return_net == pytest.approx(0.04)


class TestGIPSPresentation:
    def test_cumulative_returns(self):
        periods = [
            CompositePeriod(year=2021, gross_return=0.10, benchmark_return=0.08),
            CompositePeriod(year=2022, gross_return=-0.05, benchmark_return=-0.03),
            CompositePeriod(year=2023, gross_return=0.15, benchmark_return=0.12),
        ]
        pres = GIPSPresentation(
            composite_name="Test", firm_name="Firm",
            benchmark_name="SP500", periods=periods,
        )
        assert pres.years_of_history == 3
        expected_gross = (1.10 * 0.95 * 1.15) - 1.0
        assert pres.cumulative_gross == pytest.approx(expected_gross, abs=1e-6)

    def test_empty_presentation(self):
        pres = GIPSPresentation(
            composite_name="Empty", firm_name="Firm", benchmark_name="SP500",
        )
        assert pres.cumulative_gross == 0.0
        assert pres.years_of_history == 0


class TestComplianceReport:
    def test_pass_rate(self):
        checks = [
            ComplianceCheck("R1", "Rule 1", passed=True),
            ComplianceCheck("R2", "Rule 2", passed=True),
            ComplianceCheck("R3", "Rule 3", passed=False, severity="error"),
            ComplianceCheck("R4", "Rule 4", passed=False, severity="warning"),
        ]
        report = ComplianceReport(composite_id="C1", checks=checks)
        assert report.pass_rate == 0.5
        assert len(report.errors) == 1
        assert len(report.warnings) == 1


# ── Composite Manager Tests ──────────────────────────────────────────


class TestCompositeManager:
    def test_create_composite(self):
        mgr = CompositeManager()
        comp = mgr.create_composite(
            name="US Equity", strategy="Large Cap",
            benchmark_name="SP500", inception_date=date(2020, 1, 1),
        )
        assert comp.name == "US Equity"
        assert comp.is_active
        assert mgr.get_composite(comp.composite_id) is not None

    def test_list_composites(self):
        mgr = CompositeManager()
        mgr.create_composite("A", "S1", "B1", date(2020, 1, 1))
        mgr.create_composite("B", "S2", "B2", date(2021, 1, 1))
        assert len(mgr.list_composites()) == 2

    def test_add_portfolio(self):
        mgr = CompositeManager(CompositeConfig(min_portfolio_size=100_000))
        comp = mgr.create_composite("Test", "Eq", "SP500", date(2020, 1, 1))

        result = mgr.add_portfolio(comp.composite_id, "P1", date(2020, 1, 1), 500_000)
        assert result is not None
        assert comp.n_portfolios == 1

    def test_add_portfolio_below_min_size(self):
        mgr = CompositeManager(CompositeConfig(min_portfolio_size=100_000))
        comp = mgr.create_composite("Test", "Eq", "SP500", date(2020, 1, 1))

        result = mgr.add_portfolio(comp.composite_id, "P1", date(2020, 1, 1), 50_000)
        assert result is None
        assert comp.n_portfolios == 0

    def test_remove_portfolio(self):
        mgr = CompositeManager()
        comp = mgr.create_composite("Test", "Eq", "SP500", date(2020, 1, 1))
        mgr.add_portfolio(comp.composite_id, "P1", date(2020, 1, 1), 500_000)

        removed = mgr.remove_portfolio(comp.composite_id, "P1", date(2023, 6, 30))
        assert removed
        assert comp.n_portfolios == 0

    def test_duplicate_portfolio_rejected(self):
        mgr = CompositeManager()
        comp = mgr.create_composite("Test", "Eq", "SP500", date(2020, 1, 1))
        mgr.add_portfolio(comp.composite_id, "P1", date(2020, 1, 1), 500_000)

        dup = mgr.add_portfolio(comp.composite_id, "P1", date(2020, 1, 1), 500_000)
        assert dup is None

    def test_calculate_composite_return(self):
        mgr = CompositeManager()
        comp = mgr.create_composite("Test", "Eq", "SP500", date(2020, 1, 1))
        mgr.add_portfolio(comp.composite_id, "P1", date(2020, 1, 1), 1_000_000)
        mgr.add_portfolio(comp.composite_id, "P2", date(2020, 1, 1), 2_000_000)

        records = [
            PerformanceRecord("P1", date(2023, 1, 1), date(2023, 12, 31),
                              gross_return=0.10, net_return=0.09,
                              beginning_value=1_000_000, ending_value=1_100_000),
            PerformanceRecord("P2", date(2023, 1, 1), date(2023, 12, 31),
                              gross_return=0.15, net_return=0.14,
                              beginning_value=2_000_000, ending_value=2_300_000),
        ]

        cr = mgr.calculate_composite_return(comp.composite_id, records, 0.12, 10_000_000)
        assert cr is not None
        # Asset-weighted: (0.10*1M + 0.15*2M) / 3M = 0.1333...
        assert cr.gross_return == pytest.approx(0.13333, abs=1e-3)
        assert cr.n_portfolios == 2

    def test_archive_composite(self):
        mgr = CompositeManager()
        comp = mgr.create_composite("Test", "Eq", "SP500", date(2020, 1, 1))
        mgr.add_portfolio(comp.composite_id, "P1", date(2020, 1, 1), 500_000)

        assert mgr.archive_composite(comp.composite_id)
        assert not comp.is_active

    def test_sample_composite(self):
        mgr = CompositeManager.generate_sample_composite()
        composites = mgr.list_composites()
        assert len(composites) == 1
        assert composites[0].n_portfolios > 0


# ── Calculator Tests ──────────────────────────────────────────────────


class TestGIPSCalculator:
    def test_time_weighted_return(self):
        calc = GIPSCalculator()
        # 1000 -> 1100 -> 1210 (10% each sub-period)
        twr = calc.time_weighted_return([1000, 1100, 1210])
        assert twr == pytest.approx(0.21, abs=1e-3)

    def test_twr_with_cash_flows(self):
        calc = GIPSCalculator()
        twr = calc.time_weighted_return([1000, 1100, 1320], [0, 100])
        # Period 1: (1100-1000)/1000 = 0.10
        # Period 2: (1320-1100-100)/(1100+100) = 120/1200 = 0.10
        assert twr == pytest.approx(0.21, abs=1e-3)

    def test_modified_dietz(self):
        calc = GIPSCalculator()
        ret = calc.modified_dietz_return(
            beginning_value=1_000_000,
            ending_value=1_150_000,
            cash_flows=[(100_000, 0.5)],  # 100K at midpoint
        )
        # (1150000 - 1000000 - 100000) / (1000000 + 50000) = 50000/1050000
        assert ret == pytest.approx(0.04762, abs=1e-3)

    def test_money_weighted_return(self):
        calc = GIPSCalculator()
        mwr = calc.money_weighted_return(
            beginning_value=1_000_000,
            ending_value=1_100_000,
            cash_flows=[],
            total_days=365,
        )
        assert mwr == pytest.approx(0.10, abs=0.02)

    def test_gross_to_net(self):
        calc = GIPSCalculator()
        net = calc.gross_to_net(0.10, 0.01, periods=1)
        assert net == pytest.approx(0.09)

    def test_net_to_gross(self):
        calc = GIPSCalculator()
        gross = calc.net_to_gross(0.09, 0.01, periods=1)
        assert gross == pytest.approx(0.10)

    def test_annualize_return(self):
        calc = GIPSCalculator()
        annual = calc.annualize_return(0.21, 2.0)
        # (1.21)^(1/2) - 1 = 0.1
        assert annual == pytest.approx(0.10, abs=1e-3)

    def test_annualized_std_dev(self):
        calc = GIPSCalculator()
        returns = [0.02, -0.01, 0.03, 0.01, -0.02, 0.02,
                   0.01, 0.03, -0.01, 0.02, 0.01, -0.01]
        std = calc.annualized_std_dev(returns, 12)
        assert std > 0

    def test_link_returns(self):
        calc = GIPSCalculator()
        linked = calc.link_returns([0.05, 0.03, -0.02])
        expected = (1.05 * 1.03 * 0.98) - 1.0
        assert linked == pytest.approx(expected, abs=1e-6)

    def test_large_cash_flow_detection(self):
        calc = GIPSCalculator()
        assert calc.handle_large_cash_flow(1_000_000, 150_000)  # 15% > 10%
        assert not calc.handle_large_cash_flow(1_000_000, 50_000)  # 5% < 10%

    def test_build_annual_periods(self):
        calc = GIPSCalculator()
        returns = GIPSCalculator.generate_sample_returns(3)
        periods = calc.build_annual_periods(returns)
        assert len(periods) == 3

    def test_sample_returns(self):
        returns = GIPSCalculator.generate_sample_returns(5)
        assert len(returns) == 60  # 5 years * 12 months


# ── Dispersion Tests ──────────────────────────────────────────────────


class TestDispersionCalculator:
    def _make_records(self, returns, values=None):
        records = []
        for i, r in enumerate(returns):
            bv = values[i] if values else 1_000_000
            records.append(PerformanceRecord(
                portfolio_id=f"P{i}",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 12, 31),
                gross_return=r,
                beginning_value=bv,
                ending_value=bv * (1 + r),
            ))
        return records

    def test_equal_weighted_std(self):
        calc = DispersionCalculator(DispersionMethod.EQUAL_WEIGHTED_STD)
        records = self._make_records([0.10, 0.12, 0.08, 0.11, 0.09, 0.13])
        result = calc.calculate(records)
        assert result.value > 0
        assert result.is_meaningful
        assert result.n_portfolios == 6

    def test_asset_weighted_std(self):
        calc = DispersionCalculator(DispersionMethod.ASSET_WEIGHTED_STD)
        records = self._make_records(
            [0.10, 0.15, 0.08, 0.12, 0.09, 0.14],
            [1_000_000, 5_000_000, 2_000_000, 3_000_000, 1_500_000, 4_000_000],
        )
        result = calc.calculate(records)
        assert result.value > 0

    def test_high_low_range(self):
        calc = DispersionCalculator(DispersionMethod.HIGH_LOW_RANGE)
        records = self._make_records([0.05, 0.15, 0.10])
        result = calc.calculate(records)
        assert result.value == pytest.approx(0.10)
        assert result.high == 0.15
        assert result.low == 0.05

    def test_interquartile(self):
        calc = DispersionCalculator(DispersionMethod.INTERQUARTILE)
        records = self._make_records([0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25])
        result = calc.calculate(records)
        assert result.value > 0

    def test_too_few_portfolios(self):
        calc = DispersionCalculator()
        records = self._make_records([0.10, 0.12])
        result = calc.calculate(records)
        assert not result.is_meaningful

    def test_single_portfolio(self):
        calc = DispersionCalculator()
        records = self._make_records([0.10])
        result = calc.calculate(records)
        assert result.value == 0.0
        assert not result.is_meaningful

    def test_compare_methods(self):
        calc = DispersionCalculator()
        records = self._make_records([0.08, 0.10, 0.12, 0.14, 0.09, 0.11])
        results = calc.compare_methods(records)
        assert len(results) == 4
        assert all(isinstance(r, DispersionResult) for r in results)


# ── Compliance Tests ──────────────────────────────────────────────────


class TestComplianceValidator:
    def _make_composite(self, n_portfolios=5, has_description=True):
        portfolios = [
            PortfolioAssignment(f"P{i}", "C1", date(2020, 1, 1), is_active=True)
            for i in range(n_portfolios)
        ]
        return CompositeDefinition(
            composite_id="C1",
            name="US Equity",
            strategy="Large Cap",
            benchmark_name="SP500",
            inception_date=date(2018, 1, 1),
            creation_date=date(2018, 1, 1),
            description="Large cap equity composite" if has_description else "",
            portfolios=portfolios,
        )

    def _make_periods(self, n_years=7, with_std=True, with_dispersion=True):
        periods = []
        for i in range(n_years):
            periods.append(CompositePeriod(
                year=2018 + i,
                gross_return=0.08 + i * 0.01,
                net_return=0.07 + i * 0.01,
                benchmark_return=0.07 + i * 0.005,
                n_portfolios=8,
                composite_assets=50_000_000 + i * 5_000_000,
                firm_assets=150_000_000 + i * 10_000_000,
                pct_firm_assets=33.3,
                dispersion=0.02 if with_dispersion else None,
                composite_3yr_std=0.15 if (with_std and i >= 2) else None,
                benchmark_3yr_std=0.14 if (with_std and i >= 2) else None,
            ))
        return periods

    def test_fully_compliant(self):
        validator = ComplianceValidator()
        composite = self._make_composite()
        periods = self._make_periods(7)

        report = validator.validate_composite(composite, periods)
        assert report.overall_compliant
        assert report.pass_rate > 0.8

    def test_missing_description(self):
        validator = ComplianceValidator()
        composite = self._make_composite(has_description=False)
        periods = self._make_periods()

        report = validator.validate_composite(composite, periods)
        # GIPS-1.1 should fail
        rule_11 = [c for c in report.checks if c.rule_id == "GIPS-1.1"]
        assert len(rule_11) == 1
        assert not rule_11[0].passed

    def test_insufficient_history(self):
        validator = ComplianceValidator()
        composite = self._make_composite()
        periods = self._make_periods(2)

        report = validator.validate_composite(composite, periods)
        history_check = [c for c in report.checks if c.rule_id == "GIPS-4.1"]
        assert not history_check[0].passed

    def test_missing_3yr_std(self):
        validator = ComplianceValidator()
        composite = self._make_composite()
        periods = self._make_periods(5, with_std=False)

        report = validator.validate_composite(composite, periods)
        std_check = [c for c in report.checks if c.rule_id == "GIPS-5.2"]
        assert not std_check[0].passed

    def test_generate_disclosures(self):
        validator = ComplianceValidator(GIPSConfig(firm_name="Acme Capital"))
        composite = self._make_composite()
        periods = self._make_periods()

        disclosures = validator.generate_disclosures(composite, periods)
        assert len(disclosures) >= 6
        categories = {d.category for d in disclosures}
        assert "firm_definition" in categories
        assert "compliance_claim" in categories
        assert "benchmark" in categories
        assert "fees" in categories

    def test_disclosure_text_contains_firm(self):
        validator = ComplianceValidator(GIPSConfig(firm_name="Acme Capital"))
        composite = self._make_composite()
        disclosures = validator.generate_disclosures(composite, [])

        firm_disc = [d for d in disclosures if d.category == "compliance_claim"][0]
        assert "Acme Capital" in firm_disc.text


# ── Generator Tests ───────────────────────────────────────────────────


class TestGIPSReportGenerator:
    def _make_presentation_inputs(self):
        composite = CompositeDefinition(
            composite_id="C1", name="US Large Cap",
            strategy="Large Cap Growth", benchmark_name="Russell 1000 Growth",
            inception_date=date(2018, 1, 1), creation_date=date(2018, 1, 1),
            description="Large cap growth composite",
        )
        periods = [
            CompositePeriod(year=2020 + i, gross_return=0.10 + i * 0.02,
                            net_return=0.09 + i * 0.02,
                            benchmark_return=0.08 + i * 0.015,
                            n_portfolios=8, composite_assets=50_000_000 + i * 10_000_000,
                            firm_assets=200_000_000, pct_firm_assets=25 + i * 5,
                            dispersion=0.02, composite_3yr_std=0.15,
                            benchmark_3yr_std=0.14)
            for i in range(5)
        ]
        return composite, periods

    def test_generate_presentation(self):
        gen = GIPSReportGenerator(GIPSConfig(firm_name="Test Firm"))
        composite, periods = self._make_presentation_inputs()

        pres = gen.generate_presentation(composite, periods)
        assert pres.composite_name == "US Large Cap"
        assert pres.firm_name == "Test Firm"
        assert len(pres.periods) == 5
        assert len(pres.disclosures) > 0

    def test_format_table(self):
        gen = GIPSReportGenerator(GIPSConfig(firm_name="Test Firm"))
        composite, periods = self._make_presentation_inputs()
        pres = gen.generate_presentation(composite, periods)

        table = gen.format_presentation_table(pres)
        assert "Test Firm" in table
        assert "US Large Cap" in table
        assert "DISCLOSURES" in table
        assert "Compliance Status" in table

    def test_generate_summary(self):
        gen = GIPSReportGenerator()
        composite, periods = self._make_presentation_inputs()
        pres = gen.generate_presentation(composite, periods)

        summary = gen.generate_summary(pres)
        assert summary["years"] == 5
        assert summary["composite_name"] == "US Large Cap"
        assert "latest_gross" in summary
        assert "cumulative_gross" in summary
        assert "status" in summary

    def test_empty_summary(self):
        gen = GIPSReportGenerator()
        pres = GIPSPresentation(
            composite_name="Empty", firm_name="Firm", benchmark_name="SP500",
        )
        summary = gen.generate_summary(pres)
        assert summary["years"] == 0


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_end_to_end_workflow(self):
        """Full workflow: create composite -> add portfolios -> calculate -> report."""
        # 1. Create composite
        mgr = CompositeManager(CompositeConfig(min_portfolio_size=100_000))
        comp = mgr.create_composite(
            name="Global Equity",
            strategy="All Cap",
            benchmark_name="MSCI World",
            inception_date=date(2020, 1, 1),
        )

        # 2. Add portfolios
        for i in range(6):
            mgr.add_portfolio(comp.composite_id, f"P{i}", date(2020, 1, 1), 500_000 + i * 100_000)

        assert comp.n_portfolios == 6

        # 3. Calculate composite return
        records = [
            PerformanceRecord(
                f"P{i}", date(2023, 1, 1), date(2023, 12, 31),
                gross_return=0.08 + i * 0.02,
                net_return=0.07 + i * 0.02,
                beginning_value=500_000 + i * 100_000,
                ending_value=(500_000 + i * 100_000) * (1.08 + i * 0.02),
            )
            for i in range(6)
        ]

        cr = mgr.calculate_composite_return(comp.composite_id, records, 0.10, 10_000_000)
        assert cr is not None
        assert cr.n_portfolios == 6

        # 4. Dispersion
        disp_calc = DispersionCalculator()
        disp = disp_calc.calculate(records)
        assert disp.is_meaningful

        # 5. Compliance
        calc = GIPSCalculator()
        periods = [CompositePeriod(
            year=2023, gross_return=cr.gross_return, net_return=cr.net_return,
            benchmark_return=cr.benchmark_return, n_portfolios=cr.n_portfolios,
            composite_assets=cr.composite_assets, firm_assets=cr.firm_assets,
            pct_firm_assets=cr.pct_firm_assets, dispersion=disp.value,
        )]

        validator = ComplianceValidator()
        compliance = validator.validate_composite(comp, periods)
        assert isinstance(compliance, ComplianceReport)

        # 6. Generate presentation
        gen = GIPSReportGenerator()
        pres = gen.generate_presentation(comp, periods)
        assert pres.composite_name == "Global Equity"
        assert len(pres.disclosures) > 0

    def test_sample_data_pipeline(self):
        """Test with generated sample data."""
        mgr = CompositeManager.generate_sample_composite()
        comp = mgr.list_composites()[0]

        calc = GIPSCalculator()
        returns = GIPSCalculator.generate_sample_returns(5)
        periods = calc.build_annual_periods(returns)
        assert len(periods) == 5

        gen = GIPSReportGenerator(GIPSConfig(firm_name="Demo Firm"))
        pres = gen.generate_presentation(comp, periods)
        table = gen.format_presentation_table(pres)
        assert "Demo Firm" in table


# ── Module Import Test ────────────────────────────────────────────────


class TestModuleImports:
    def test_import_all(self):
        import src.performance_report as pr
        assert hasattr(pr, "CompositeManager")
        assert hasattr(pr, "GIPSCalculator")
        assert hasattr(pr, "DispersionCalculator")
        assert hasattr(pr, "ComplianceValidator")
        assert hasattr(pr, "GIPSReportGenerator")
        assert hasattr(pr, "ReturnMethod")
        assert hasattr(pr, "GIPSConfig")
        assert hasattr(pr, "CompositeDefinition")
        assert hasattr(pr, "GIPSPresentation")
