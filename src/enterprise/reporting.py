"""Professional Reporting System.

Generates comprehensive performance reports in PDF and Excel formats
with client-facing quality and white-label support.
"""

import io
import logging
from datetime import datetime, date
from typing import Optional, List, Any
from dataclasses import dataclass, field

from src.enterprise.config import ReportConfig, DEFAULT_REPORT_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    """A section of a report."""

    title: str
    content_type: str  # text, table, chart, metrics
    content: Any
    order: int = 0


@dataclass
class PerformanceMetrics:
    """Performance metrics for reporting."""

    # Returns
    total_return: float = 0.0
    period_return: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0

    # Risk
    volatility: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # Trading
    total_trades: int = 0
    win_rate: float = 0.0


@dataclass
class AttributionData:
    """Performance attribution data."""

    sector_attribution: dict = field(default_factory=dict)
    factor_attribution: dict = field(default_factory=dict)
    stock_attribution: List[dict] = field(default_factory=list)
    total_allocation: float = 0.0
    total_selection: float = 0.0
    total_interaction: float = 0.0


@dataclass
class ReportData:
    """Data for report generation."""

    # Header
    report_title: str = "Performance Report"
    client_name: str = ""
    account_name: str = ""
    period_start: date = field(default_factory=date.today)
    period_end: date = field(default_factory=date.today)

    # Performance
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    equity_curve: List[tuple] = field(default_factory=list)  # (date, value)
    monthly_returns: dict = field(default_factory=dict)  # year -> month -> return

    # Attribution
    attribution: AttributionData = field(default_factory=AttributionData)

    # Holdings
    holdings: List[dict] = field(default_factory=list)

    # Trades
    trades: List[dict] = field(default_factory=list)

    # Risk
    var_95: float = 0.0
    factor_exposures: dict = field(default_factory=dict)

    # Custom sections
    custom_sections: List[ReportSection] = field(default_factory=list)


class ReportGenerator:
    """Generates professional reports in various formats.

    Supports:
    - PDF reports with charts and tables
    - Excel exports with multiple sheets
    - HTML reports for web viewing
    - White-label customization
    """

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or DEFAULT_REPORT_CONFIG

    def generate_quarterly_report(
        self,
        data: ReportData,
        format: str = "pdf",
    ) -> bytes:
        """Generate a quarterly performance report.

        Args:
            data: Report data.
            format: Output format (pdf, excel, html).

        Returns:
            Report content as bytes.
        """
        if format == "pdf":
            return self._generate_pdf_report(data)
        elif format == "excel":
            return self._generate_excel_report(data)
        elif format == "html":
            return self._generate_html_report(data)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_pdf_report(self, data: ReportData) -> bytes:
        """Generate PDF report.

        Note: In production, use ReportLab or WeasyPrint.
        This generates a text representation that can be converted to PDF.
        """
        lines = []

        # Header
        lines.extend([
            "=" * 70,
            f"  {data.report_title.upper()}",
            f"  {data.period_start.strftime('%B %d, %Y')} - {data.period_end.strftime('%B %d, %Y')}",
            f"  Prepared for: {data.client_name}",
            f"  Account: {data.account_name}",
            "=" * 70,
            "",
        ])

        # Executive Summary
        m = data.metrics
        lines.extend([
            "EXECUTIVE SUMMARY",
            "-" * 50,
            f"Portfolio returned {m.period_return*100:+.1f}% vs benchmark {m.benchmark_return*100:+.1f}%",
            f"Alpha: {m.alpha*100:+.1f}%",
            f"Sharpe Ratio: {m.sharpe_ratio:.2f}",
            f"Max Drawdown: {m.max_drawdown*100:.1f}%",
            "",
        ])

        # Performance Attribution
        attr = data.attribution
        lines.extend([
            "PERFORMANCE ATTRIBUTION",
            "-" * 50,
            f"├── Sector Allocation:  {attr.total_allocation*100:+.1f}%",
            f"├── Stock Selection:    {attr.total_selection*100:+.1f}%",
            f"└── Interaction:        {attr.total_interaction*100:+.1f}%",
            "",
        ])

        # Sector Attribution Detail
        if attr.sector_attribution:
            lines.append("BY SECTOR:")
            for sector, contrib in sorted(
                attr.sector_attribution.items(),
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:5]:
                lines.append(f"    {sector:20s} {contrib*100:+.2f}%")
            lines.append("")

        # Holdings
        if data.holdings:
            lines.extend([
                "TOP HOLDINGS (as of period end)",
                "-" * 50,
                f"{'Symbol':<8} {'Weight':>8} {'Return':>10} {'P&L':>12}",
            ])

            for h in data.holdings[:10]:
                lines.append(
                    f"{h.get('symbol', ''):<8} "
                    f"{h.get('weight', 0)*100:>7.1f}% "
                    f"{h.get('return', 0)*100:>+9.1f}% "
                    f"${h.get('pnl', 0):>10,.0f}"
                )
            lines.append("")

        # Monthly Returns
        if data.monthly_returns:
            lines.extend([
                "MONTHLY RETURNS",
                "-" * 50,
                "     Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec",
            ])

            for year in sorted(data.monthly_returns.keys(), reverse=True):
                row = f"{year}"
                for month in range(1, 13):
                    ret = data.monthly_returns[year].get(month)
                    if ret is not None:
                        row += f" {ret*100:+5.1f}"
                    else:
                        row += "      "
                lines.append(row)
            lines.append("")

        # Risk Analysis
        lines.extend([
            "RISK ANALYSIS",
            "-" * 50,
            f"Volatility (Ann.):     {m.volatility*100:.1f}%",
            f"Max Drawdown:          {m.max_drawdown*100:.1f}%",
            f"Value at Risk (95%):   ${data.var_95:,.0f}",
            f"Sharpe Ratio:          {m.sharpe_ratio:.2f}",
            f"Sortino Ratio:         {m.sortino_ratio:.2f}",
            "",
        ])

        # Factor Exposures
        if data.factor_exposures:
            lines.append("FACTOR EXPOSURES:")
            for factor, exposure in data.factor_exposures.items():
                bar = "█" * int(abs(exposure) * 10)
                sign = "+" if exposure >= 0 else "-"
                lines.append(f"    {factor:15s} {sign}{bar} {exposure:+.2f}")
            lines.append("")

        # Trade Summary
        if data.trades:
            lines.extend([
                "TRADE ACTIVITY SUMMARY",
                "-" * 50,
                f"Total Trades:      {m.total_trades}",
                f"Win Rate:          {m.win_rate*100:.0f}%",
                "",
                "RECENT TRADES:",
            ])

            for trade in data.trades[:5]:
                lines.append(
                    f"    {trade.get('date', '')}: "
                    f"{trade.get('action', '')} {trade.get('shares', 0)} "
                    f"{trade.get('symbol', '')} @ ${trade.get('price', 0):.2f}"
                )
            lines.append("")

        # Custom sections
        for section in data.custom_sections:
            lines.extend([
                section.title.upper(),
                "-" * 50,
            ])
            if section.content_type == "text":
                lines.append(section.content)
            elif section.content_type == "metrics":
                for key, value in section.content.items():
                    lines.append(f"    {key}: {value}")
            lines.append("")

        # Footer
        lines.extend([
            "=" * 70,
            f"  Generated by {self.config.company_name}",
            f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 70,
        ])

        return "\n".join(lines).encode('utf-8')

    def _generate_excel_report(self, data: ReportData) -> bytes:
        """Generate Excel report.

        Returns CSV data that can be opened in Excel.
        In production, use openpyxl for proper Excel files.
        """
        output = io.StringIO()

        # Summary sheet (as CSV)
        output.write("PERFORMANCE SUMMARY\n")
        output.write(f"Report Period,{data.period_start},{data.period_end}\n")
        output.write(f"Client,{data.client_name}\n")
        output.write(f"Account,{data.account_name}\n")
        output.write("\n")

        m = data.metrics
        output.write("Metric,Value\n")
        output.write(f"Period Return,{m.period_return*100:.2f}%\n")
        output.write(f"Benchmark Return,{m.benchmark_return*100:.2f}%\n")
        output.write(f"Alpha,{m.alpha*100:.2f}%\n")
        output.write(f"Volatility,{m.volatility*100:.2f}%\n")
        output.write(f"Sharpe Ratio,{m.sharpe_ratio:.2f}\n")
        output.write(f"Max Drawdown,{m.max_drawdown*100:.2f}%\n")
        output.write("\n")

        # Holdings
        if data.holdings:
            output.write("HOLDINGS\n")
            output.write("Symbol,Weight,Return,P&L\n")
            for h in data.holdings:
                output.write(
                    f"{h.get('symbol', '')},"
                    f"{h.get('weight', 0)*100:.2f}%,"
                    f"{h.get('return', 0)*100:.2f}%,"
                    f"{h.get('pnl', 0):.2f}\n"
                )
            output.write("\n")

        # Trades
        if data.trades:
            output.write("TRADES\n")
            output.write("Date,Action,Symbol,Shares,Price\n")
            for t in data.trades:
                output.write(
                    f"{t.get('date', '')},"
                    f"{t.get('action', '')},"
                    f"{t.get('symbol', '')},"
                    f"{t.get('shares', 0)},"
                    f"{t.get('price', 0):.2f}\n"
                )

        return output.getvalue().encode('utf-8')

    def _generate_html_report(self, data: ReportData) -> bytes:
        """Generate HTML report."""
        m = data.metrics

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{data.report_title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .metric-label {{ font-size: 12px; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; }}
        .positive {{ color: #28a745; }}
        .negative {{ color: #dc3545; }}
        .footer {{ margin-top: 40px; text-align: center; color: #888; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>{data.report_title}</h1>
    <p><strong>Period:</strong> {data.period_start} to {data.period_end}<br>
       <strong>Client:</strong> {data.client_name}<br>
       <strong>Account:</strong> {data.account_name}</p>

    <h2>Performance Summary</h2>
    <div class="metrics">
        <div class="metric">
            <div class="metric-value {'positive' if m.period_return >= 0 else 'negative'}">{m.period_return*100:+.1f}%</div>
            <div class="metric-label">Period Return</div>
        </div>
        <div class="metric">
            <div class="metric-value {'positive' if m.alpha >= 0 else 'negative'}">{m.alpha*100:+.1f}%</div>
            <div class="metric-label">Alpha</div>
        </div>
        <div class="metric">
            <div class="metric-value">{m.sharpe_ratio:.2f}</div>
            <div class="metric-label">Sharpe Ratio</div>
        </div>
        <div class="metric">
            <div class="metric-value class="negative">{m.max_drawdown*100:.1f}%</div>
            <div class="metric-label">Max Drawdown</div>
        </div>
    </div>

    <h2>Attribution</h2>
    <table>
        <tr><th>Component</th><th>Contribution</th></tr>
        <tr><td>Sector Allocation</td><td>{data.attribution.total_allocation*100:+.2f}%</td></tr>
        <tr><td>Stock Selection</td><td>{data.attribution.total_selection*100:+.2f}%</td></tr>
        <tr><td>Interaction</td><td>{data.attribution.total_interaction*100:+.2f}%</td></tr>
    </table>

    <h2>Holdings</h2>
    <table>
        <tr><th>Symbol</th><th>Weight</th><th>Return</th><th>P&L</th></tr>
"""

        for h in data.holdings[:10]:
            ret = h.get('return', 0)
            ret_class = 'positive' if ret >= 0 else 'negative'
            html += f"""        <tr>
            <td>{h.get('symbol', '')}</td>
            <td>{h.get('weight', 0)*100:.1f}%</td>
            <td class="{ret_class}">{ret*100:+.1f}%</td>
            <td>${h.get('pnl', 0):,.0f}</td>
        </tr>
"""

        html += f"""    </table>

    <div class="footer">
        <p>Generated by {self.config.company_name} | {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>
</body>
</html>"""

        return html.encode('utf-8')


class ReportScheduler:
    """Schedules and manages automated report generation."""

    def __init__(self, generator: Optional[ReportGenerator] = None):
        self.generator = generator or ReportGenerator()
        self._scheduled_reports: List[dict] = []

    def schedule_report(
        self,
        user_id: str,
        account_id: str,
        frequency: str,  # daily, weekly, monthly, quarterly
        format: str = "pdf",
        recipients: Optional[List[str]] = None,
    ) -> str:
        """Schedule automated report generation.

        Args:
            user_id: User ID.
            account_id: Account ID.
            frequency: Report frequency.
            format: Output format.
            recipients: Email recipients.

        Returns:
            Schedule ID.
        """
        schedule_id = f"sched_{datetime.now().timestamp()}"

        self._scheduled_reports.append({
            "id": schedule_id,
            "user_id": user_id,
            "account_id": account_id,
            "frequency": frequency,
            "format": format,
            "recipients": recipients or [],
            "created_at": datetime.utcnow(),
            "last_run": None,
            "is_active": True,
        })

        logger.info(f"Report scheduled: {schedule_id} ({frequency})")
        return schedule_id

    def get_scheduled_reports(self, user_id: str) -> List[dict]:
        """Get all scheduled reports for a user."""
        return [
            r for r in self._scheduled_reports
            if r["user_id"] == user_id
        ]

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a scheduled report."""
        for report in self._scheduled_reports:
            if report["id"] == schedule_id:
                report["is_active"] = False
                return True
        return False
