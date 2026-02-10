"""Unit tests for PRD-70: Professional Reporting.

Tests cover:
- ReportGenerator format outputs (PDF, Excel, HTML)
- Report data structures
- Report scheduling
- Performance metrics
- ORM models
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch

from src.enterprise.reporting import (
    ReportGenerator,
    ReportScheduler,
    ReportData,
    PerformanceMetrics,
    AttributionData,
    ReportSection,
)
from src.enterprise.config import (
    ReportConfig,
    DEFAULT_REPORT_CONFIG,
    SubscriptionTier,
    SUBSCRIPTION_LIMITS,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def report_generator():
    """Create a ReportGenerator instance."""
    return ReportGenerator()


@pytest.fixture
def report_scheduler():
    """Create a ReportScheduler instance."""
    return ReportScheduler()


@pytest.fixture
def sample_report_data():
    """Create sample report data."""
    return ReportData(
        report_title="Q4 2025 Performance Report",
        client_name="John Smith",
        account_name="Personal Brokerage",
        period_start=date(2025, 10, 1),
        period_end=date(2025, 12, 31),
        metrics=PerformanceMetrics(
            total_return=0.186,
            period_return=0.084,
            benchmark_return=0.062,
            alpha=0.022,
            volatility=0.15,
            max_drawdown=-0.038,
            sharpe_ratio=1.67,
            sortino_ratio=2.1,
            total_trades=45,
            win_rate=0.58,
        ),
        attribution=AttributionData(
            total_allocation=0.004,
            total_selection=0.006,
            total_interaction=0.001,
            sector_attribution={
                "Technology": 0.015,
                "Healthcare": 0.003,
                "Financials": -0.002,
            },
        ),
        holdings=[
            {"symbol": "AAPL", "weight": 0.12, "return": 0.25, "pnl": 3200},
            {"symbol": "MSFT", "weight": 0.10, "return": 0.18, "pnl": 2100},
            {"symbol": "NVDA", "weight": 0.15, "return": 0.45, "pnl": 8500},
        ],
        trades=[
            {"date": "2025-12-15", "action": "BUY", "symbol": "AAPL", "shares": 50, "price": 195.50},
            {"date": "2025-12-10", "action": "SELL", "symbol": "TSLA", "shares": 20, "price": 245.00},
        ],
        var_95=5200.0,
        factor_exposures={
            "Value": 0.15,
            "Momentum": 0.35,
            "Quality": 0.25,
            "Growth": -0.10,
        },
    )


@pytest.fixture
def custom_config():
    """Create a custom report config."""
    return ReportConfig(
        company_name="Alpha Capital",
        output_dir="./test_reports",
        default_format="pdf",
    )


# =============================================================================
# Report Generation Tests
# =============================================================================


class TestReportGeneration:
    """Tests for report generation."""

    def test_generate_pdf_report(self, report_generator, sample_report_data):
        """Can generate PDF report."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="pdf",
        )

        assert content is not None
        assert len(content) > 0
        assert isinstance(content, bytes)

    def test_generate_excel_report(self, report_generator, sample_report_data):
        """Can generate Excel report."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="excel",
        )

        assert content is not None
        assert len(content) > 0
        assert isinstance(content, bytes)

    def test_generate_html_report(self, report_generator, sample_report_data):
        """Can generate HTML report."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="html",
        )

        assert content is not None
        assert len(content) > 0
        assert isinstance(content, bytes)
        # HTML should contain proper tags
        content_str = content.decode('utf-8')
        assert "<html>" in content_str
        assert "</html>" in content_str

    def test_invalid_format_raises_error(self, report_generator, sample_report_data):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError):
            report_generator.generate_quarterly_report(
                data=sample_report_data,
                format="invalid",
            )

    def test_pdf_contains_title(self, report_generator, sample_report_data):
        """PDF report contains title."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="pdf",
        )

        content_str = content.decode('utf-8')
        assert "Q4 2025 PERFORMANCE REPORT" in content_str.upper()

    def test_pdf_contains_client_name(self, report_generator, sample_report_data):
        """PDF report contains client name."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="pdf",
        )

        content_str = content.decode('utf-8')
        assert "John Smith" in content_str

    def test_pdf_contains_metrics(self, report_generator, sample_report_data):
        """PDF report contains performance metrics."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="pdf",
        )

        content_str = content.decode('utf-8')
        assert "8.4%" in content_str  # period return
        assert "1.67" in content_str  # sharpe ratio

    def test_pdf_contains_holdings(self, report_generator, sample_report_data):
        """PDF report contains holdings data."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="pdf",
        )

        content_str = content.decode('utf-8')
        assert "AAPL" in content_str
        assert "MSFT" in content_str
        assert "NVDA" in content_str

    def test_html_contains_styling(self, report_generator, sample_report_data):
        """HTML report contains CSS styling."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="html",
        )

        content_str = content.decode('utf-8')
        assert "<style>" in content_str
        assert "</style>" in content_str

    def test_excel_contains_summary(self, report_generator, sample_report_data):
        """Excel report contains summary section."""
        content = report_generator.generate_quarterly_report(
            data=sample_report_data,
            format="excel",
        )

        content_str = content.decode('utf-8')
        assert "PERFORMANCE SUMMARY" in content_str


# =============================================================================
# Report Data Tests
# =============================================================================


class TestReportData:
    """Tests for report data structures."""

    def test_report_data_defaults(self):
        """ReportData has sensible defaults."""
        data = ReportData()

        assert data.report_title == "Performance Report"
        assert data.client_name == ""
        assert isinstance(data.metrics, PerformanceMetrics)
        assert isinstance(data.holdings, list)
        assert isinstance(data.trades, list)

    def test_performance_metrics_defaults(self):
        """PerformanceMetrics has zero defaults."""
        metrics = PerformanceMetrics()

        assert metrics.total_return == 0.0
        assert metrics.period_return == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.total_trades == 0

    def test_attribution_data_defaults(self):
        """AttributionData has zero defaults."""
        attr = AttributionData()

        assert attr.total_allocation == 0.0
        assert attr.total_selection == 0.0
        assert attr.total_interaction == 0.0
        assert isinstance(attr.sector_attribution, dict)

    def test_report_section_creation(self):
        """Can create ReportSection."""
        section = ReportSection(
            title="Holdings Summary",
            content_type="table",
            content=[{"symbol": "AAPL", "weight": 0.12}],
            order=1,
        )

        assert section.title == "Holdings Summary"
        assert section.content_type == "table"
        assert section.order == 1

    def test_report_data_with_custom_sections(self):
        """ReportData can include custom sections."""
        section = ReportSection(
            title="Custom Analysis",
            content_type="text",
            content="This is custom analysis content.",
        )

        data = ReportData(
            report_title="Custom Report",
            custom_sections=[section],
        )

        assert len(data.custom_sections) == 1
        assert data.custom_sections[0].title == "Custom Analysis"


# =============================================================================
# Report Scheduling Tests
# =============================================================================


class TestReportScheduling:
    """Tests for report scheduling."""

    def test_schedule_report(self, report_scheduler):
        """Can schedule a report."""
        schedule_id = report_scheduler.schedule_report(
            user_id="user-001",
            account_id="acc-001",
            frequency="weekly",
            format="pdf",
            recipients=["john@example.com"],
        )

        assert schedule_id is not None
        assert schedule_id.startswith("sched_")

    def test_get_scheduled_reports(self, report_scheduler):
        """Can get scheduled reports for a user."""
        report_scheduler.schedule_report(
            user_id="user-001",
            account_id="acc-001",
            frequency="weekly",
        )
        report_scheduler.schedule_report(
            user_id="user-001",
            account_id="acc-002",
            frequency="monthly",
        )

        schedules = report_scheduler.get_scheduled_reports("user-001")
        assert len(schedules) == 2

    def test_scheduled_reports_isolated_by_user(self, report_scheduler):
        """Users only see their own schedules."""
        report_scheduler.schedule_report(
            user_id="user-001",
            account_id="acc-001",
            frequency="weekly",
        )
        report_scheduler.schedule_report(
            user_id="user-002",
            account_id="acc-002",
            frequency="monthly",
        )

        schedules = report_scheduler.get_scheduled_reports("user-001")
        assert len(schedules) == 1

    def test_cancel_schedule(self, report_scheduler):
        """Can cancel a scheduled report."""
        schedule_id = report_scheduler.schedule_report(
            user_id="user-001",
            account_id="acc-001",
            frequency="weekly",
        )

        success = report_scheduler.cancel_schedule(schedule_id)
        assert success is True

    def test_cancel_nonexistent_schedule(self, report_scheduler):
        """Canceling nonexistent schedule returns False."""
        success = report_scheduler.cancel_schedule("nonexistent")
        assert success is False

    def test_schedule_stores_recipients(self, report_scheduler):
        """Schedule stores recipient list."""
        recipients = ["john@example.com", "advisor@example.com"]

        report_scheduler.schedule_report(
            user_id="user-001",
            account_id="acc-001",
            frequency="weekly",
            recipients=recipients,
        )

        schedules = report_scheduler.get_scheduled_reports("user-001")
        assert schedules[0]["recipients"] == recipients

    def test_schedule_stores_format(self, report_scheduler):
        """Schedule stores output format."""
        report_scheduler.schedule_report(
            user_id="user-001",
            account_id="acc-001",
            frequency="weekly",
            format="excel",
        )

        schedules = report_scheduler.get_scheduled_reports("user-001")
        assert schedules[0]["format"] == "excel"


# =============================================================================
# Report Config Tests
# =============================================================================


class TestReportConfig:
    """Tests for report configuration."""

    def test_default_config(self):
        """Default config has sensible values."""
        config = DEFAULT_REPORT_CONFIG

        assert config.company_name == "Axion"
        assert config.default_format == "pdf"
        assert config.max_generation_time == 30

    def test_custom_config(self, custom_config):
        """Can create custom config."""
        assert custom_config.company_name == "Alpha Capital"
        assert custom_config.output_dir == "./test_reports"

    def test_report_generator_uses_config(self, custom_config, sample_report_data):
        """Report generator uses provided config."""
        generator = ReportGenerator(config=custom_config)

        content = generator.generate_quarterly_report(
            data=sample_report_data,
            format="pdf",
        )

        content_str = content.decode('utf-8')
        assert "Alpha Capital" in content_str


# =============================================================================
# Subscription Limits Tests
# =============================================================================


class TestReportingSubscriptionLimits:
    """Tests for subscription tier report limits."""

    def test_free_tier_no_custom_reports(self):
        """Free tier has no custom reports."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.FREE]
        assert limits["custom_reports"] is False

    def test_pro_tier_basic_reports(self):
        """Pro tier has basic custom reports."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.PRO]
        assert limits["custom_reports"] == "basic"

    def test_enterprise_tier_full_reports(self):
        """Enterprise tier has full custom reports."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.ENTERPRISE]
        assert limits["custom_reports"] == "full"

    def test_enterprise_has_white_label(self):
        """Enterprise tier has white-label support."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.ENTERPRISE]
        assert limits["white_label"] is True

    def test_pro_no_white_label(self):
        """Pro tier has no white-label support."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.PRO]
        assert limits["white_label"] is False


# =============================================================================
# ORM Model Tests
# =============================================================================


class TestReportingORMModels:
    """Tests for ORM model definitions."""

    def test_report_template_model(self):
        """ReportTemplateRecord model has required fields."""
        from src.db.models import ReportTemplateRecord

        columns = {c.name for c in ReportTemplateRecord.__table__.columns}
        assert "id" in columns
        assert "owner_id" in columns
        assert "name" in columns
        assert "report_type" in columns
        assert "sections" in columns
        assert "logo_url" in columns
        assert "company_name" in columns

    def test_generated_report_model(self):
        """GeneratedReportRecord model has required fields."""
        from src.db.models import GeneratedReportRecord

        columns = {c.name for c in GeneratedReportRecord.__table__.columns}
        assert "id" in columns
        assert "user_id" in columns
        assert "title" in columns
        assert "report_type" in columns
        assert "format" in columns
        assert "period_start" in columns
        assert "period_end" in columns
        assert "status" in columns
        assert "file_path" in columns

    def test_scheduled_report_model(self):
        """ScheduledReportRecord model has required fields."""
        from src.db.models import ScheduledReportRecord

        columns = {c.name for c in ScheduledReportRecord.__table__.columns}
        assert "id" in columns
        assert "user_id" in columns
        assert "name" in columns
        assert "frequency" in columns
        assert "recipients" in columns
        assert "is_active" in columns
        assert "next_run_at" in columns

    def test_report_distribution_model(self):
        """ReportDistributionRecord model has required fields."""
        from src.db.models import ReportDistributionRecord

        columns = {c.name for c in ReportDistributionRecord.__table__.columns}
        assert "id" in columns
        assert "report_id" in columns
        assert "recipient_email" in columns
        assert "status" in columns
        assert "sent_at" in columns

    def test_report_section_model(self):
        """ReportSectionRecord model has required fields."""
        from src.db.models import ReportSectionRecord

        columns = {c.name for c in ReportSectionRecord.__table__.columns}
        assert "id" in columns
        assert "template_id" in columns
        assert "name" in columns
        assert "section_type" in columns
        assert "order_index" in columns

    def test_report_branding_model(self):
        """ReportBrandingRecord model has required fields."""
        from src.db.models import ReportBrandingRecord

        columns = {c.name for c in ReportBrandingRecord.__table__.columns}
        assert "id" in columns
        assert "user_id" in columns
        assert "company_name" in columns
        assert "logo_url" in columns
        assert "primary_color" in columns
        assert "disclaimer" in columns


# =============================================================================
# Enum Tests
# =============================================================================


class TestReportingEnums:
    """Tests for enum definitions."""

    def test_report_type_enum(self):
        """ReportTypeEnum has all expected values."""
        from src.db.models import ReportTypeEnum

        values = {e.value for e in ReportTypeEnum}
        assert "performance" in values
        assert "holdings" in values
        assert "attribution" in values
        assert "trade_activity" in values
        assert "custom" in values

    def test_report_format_enum(self):
        """ReportFormatEnum has all expected values."""
        from src.db.models import ReportFormatEnum

        values = {e.value for e in ReportFormatEnum}
        assert "pdf" in values
        assert "excel" in values
        assert "html" in values

    def test_report_frequency_enum(self):
        """ReportFrequencyEnum has all expected values."""
        from src.db.models import ReportFrequencyEnum

        values = {e.value for e in ReportFrequencyEnum}
        assert "daily" in values
        assert "weekly" in values
        assert "monthly" in values
        assert "quarterly" in values

    def test_report_status_enum(self):
        """ReportStatusEnum has all expected values."""
        from src.db.models import ReportStatusEnum

        values = {e.value for e in ReportStatusEnum}
        assert "pending" in values
        assert "generating" in values
        assert "completed" in values
        assert "failed" in values
