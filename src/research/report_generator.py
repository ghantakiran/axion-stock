"""Report Generator Module.

Generates formatted research reports.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.research.config import (
    ResearchConfig,
    DEFAULT_RESEARCH_CONFIG,
    ReportType,
    OutputFormat,
    Rating,
)
from src.research.models import (
    ResearchReport,
    CompanyOverview,
    FinancialAnalysis,
    ValuationSummary,
    CompetitiveAnalysis,
    RiskAssessment,
    InvestmentThesis,
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates formatted research reports.
    
    Features:
    - Multiple output formats (HTML, Markdown, JSON)
    - Report templates (full, quick take, etc.)
    - Executive summary generation
    - Chart and table formatting
    
    Example:
        generator = ReportGenerator()
        report = generator.generate_report(symbol, analyses)
        html = generator.format_html(report)
    """
    
    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or DEFAULT_RESEARCH_CONFIG
        self._report_config = self.config.report
    
    def generate_report(
        self,
        symbol: str,
        company_name: str,
        current_price: float,
        overview: Optional[CompanyOverview] = None,
        financial: Optional[FinancialAnalysis] = None,
        valuation: Optional[ValuationSummary] = None,
        competitive: Optional[CompetitiveAnalysis] = None,
        risk: Optional[RiskAssessment] = None,
        thesis: Optional[InvestmentThesis] = None,
    ) -> ResearchReport:
        """Generate a research report.
        
        Args:
            symbol: Stock symbol.
            company_name: Company name.
            current_price: Current stock price.
            overview: Company overview.
            financial: Financial analysis.
            valuation: Valuation analysis.
            competitive: Competitive analysis.
            risk: Risk assessment.
            thesis: Investment thesis.
            
        Returns:
            ResearchReport object.
        """
        report = ResearchReport(
            symbol=symbol,
            company_name=company_name,
            report_type=self._report_config.report_type,
            current_price=current_price,
        )
        
        # Set valuation-related fields
        if valuation:
            report.price_target = valuation.fair_value
            report.confidence = valuation.confidence
        
        # Determine rating
        if valuation and risk:
            from src.research.thesis import ThesisGenerator
            gen = ThesisGenerator(self.config)
            report.rating = gen.determine_rating(
                valuation.upside_pct,
                valuation.confidence,
                risk.overall_risk_rating.value,
            )
        
        # Generate executive summary
        report.executive_summary = self._generate_executive_summary(
            symbol, company_name, report.rating, valuation, financial, thesis
        )
        
        # Key takeaways
        report.key_takeaways = self._generate_key_takeaways(
            valuation, financial, competitive, risk
        )
        
        # Attach analyses
        report.company_overview = overview
        report.financial_analysis = financial
        report.valuation = valuation
        report.competitive_analysis = competitive
        report.risk_assessment = risk
        report.investment_thesis = thesis
        
        return report
    
    def format_html(self, report: ResearchReport) -> str:
        """Format report as HTML.
        
        Args:
            report: Research report.
            
        Returns:
            HTML string.
        """
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{report.company_name} ({report.symbol}) Research Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }}
        h2 {{ color: #2c5282; margin-top: 30px; }}
        .rating {{ font-size: 24px; font-weight: bold; padding: 10px 20px; border-radius: 5px; display: inline-block; }}
        .strong_buy {{ background: #48bb78; color: white; }}
        .buy {{ background: #68d391; color: white; }}
        .hold {{ background: #ecc94b; color: black; }}
        .sell {{ background: #fc8181; color: white; }}
        .strong_sell {{ background: #e53e3e; color: white; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #1a365d; }}
        .metric-label {{ font-size: 12px; color: #718096; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: left; }}
        th {{ background: #f7fafc; }}
        .section {{ margin: 25px 0; }}
        .summary {{ background: #f7fafc; padding: 20px; border-radius: 5px; }}
        ul {{ margin: 10px 0; padding-left: 25px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #718096; }}
    </style>
</head>
<body>
    <h1>{report.company_name} ({report.symbol})</h1>
    
    <div class="rating {report.rating.value}">{report.rating.value.replace('_', ' ').upper()}</div>
    
    <div style="margin-top: 20px;">
        <div class="metric">
            <div class="metric-value">${report.current_price:.2f}</div>
            <div class="metric-label">Current Price</div>
        </div>
        <div class="metric">
            <div class="metric-value">${report.price_target:.2f}</div>
            <div class="metric-label">Price Target</div>
        </div>
        <div class="metric">
            <div class="metric-value">{report.upside_pct:.1f}%</div>
            <div class="metric-label">Upside</div>
        </div>
    </div>
    
    <div class="section summary">
        <h2>Executive Summary</h2>
        <p>{report.executive_summary}</p>
        
        <h3>Key Takeaways</h3>
        <ul>
            {''.join(f'<li>{t}</li>' for t in report.key_takeaways)}
        </ul>
    </div>
"""
        
        # Financial section
        if report.financial_analysis:
            fa = report.financial_analysis
            html += f"""
    <div class="section">
        <h2>Financial Analysis</h2>
        <table>
            <tr><th>Metric</th><th>Value</th><th>Assessment</th></tr>
            <tr><td>Revenue (TTM)</td><td>${fa.metrics.revenue_ttm/1e9:.1f}B</td><td>{fa.revenue_trend}</td></tr>
            <tr><td>Revenue Growth</td><td>{fa.metrics.revenue_growth_yoy:.1%}</td><td></td></tr>
            <tr><td>Gross Margin</td><td>{fa.metrics.gross_margin:.1%}</td><td></td></tr>
            <tr><td>Operating Margin</td><td>{fa.metrics.operating_margin:.1%}</td><td>{fa.margin_trend}</td></tr>
            <tr><td>ROE</td><td>{fa.metrics.roe:.1%}</td><td></td></tr>
            <tr><td>Debt/Equity</td><td>{fa.metrics.debt_to_equity:.2f}x</td><td></td></tr>
        </table>
        
        <h3>Financial Strengths</h3>
        <ul>{''.join(f'<li>{s}</li>' for s in fa.strengths[:5])}</ul>
        
        <h3>Financial Concerns</h3>
        <ul>{''.join(f'<li>{c}</li>' for c in fa.concerns[:5])}</ul>
    </div>
"""
        
        # Valuation section
        if report.valuation:
            val = report.valuation
            html += f"""
    <div class="section">
        <h2>Valuation</h2>
        <table>
            <tr><th>Method</th><th>Value</th></tr>
            <tr><td>DCF</td><td>${val.dcf_value:.2f}</td></tr>
            <tr><td>Comparable Analysis</td><td>${val.comparable_value:.2f}</td></tr>
            <tr><td><strong>Fair Value</strong></td><td><strong>${val.fair_value:.2f}</strong></td></tr>
        </table>
        <p>Valuation Range: ${val.valuation_range_low:.2f} - ${val.valuation_range_high:.2f}</p>
        <p>Confidence: {val.confidence:.0%}</p>
    </div>
"""
        
        # Competitive section
        if report.competitive_analysis:
            comp = report.competitive_analysis
            html += f"""
    <div class="section">
        <h2>Competitive Position</h2>
        <p><strong>Moat Rating:</strong> {comp.moat_rating.value.title()}</p>
        <p><strong>Moat Sources:</strong> {', '.join(comp.moat_sources) if comp.moat_sources else 'N/A'}</p>
        <p><strong>Market Position:</strong> {comp.market_position.title()}</p>
        
        <h3>SWOT Analysis</h3>
        <table>
            <tr><th>Strengths</th><th>Weaknesses</th></tr>
            <tr><td><ul>{''.join(f'<li>{s}</li>' for s in comp.strengths)}</ul></td>
                <td><ul>{''.join(f'<li>{w}</li>' for w in comp.weaknesses)}</ul></td></tr>
            <tr><th>Opportunities</th><th>Threats</th></tr>
            <tr><td><ul>{''.join(f'<li>{o}</li>' for o in comp.opportunities)}</ul></td>
                <td><ul>{''.join(f'<li>{t}</li>' for t in comp.threats)}</ul></td></tr>
        </table>
    </div>
"""
        
        # Risk section
        if report.risk_assessment:
            risk = report.risk_assessment
            html += f"""
    <div class="section">
        <h2>Risk Assessment</h2>
        <p><strong>Overall Risk:</strong> {risk.overall_risk_rating.value.replace('_', ' ').title()}</p>
        <p><strong>Risk Score:</strong> {risk.risk_score:.0f}/100</p>
        
        <h3>Key Risks</h3>
        <ul>{''.join(f'<li>{r}</li>' for r in risk.key_risks)}</ul>
    </div>
"""
        
        # Investment thesis
        if report.investment_thesis:
            thesis = report.investment_thesis
            html += f"""
    <div class="section">
        <h2>Investment Thesis</h2>
        
        <h3>Bull Case (${thesis.bull_price_target:.2f}, {thesis.bull_probability:.0%} probability)</h3>
        <p>{thesis.bull_case}</p>
        
        <h3>Base Case (${thesis.base_price_target:.2f}, {thesis.base_probability:.0%} probability)</h3>
        <p>{thesis.base_case}</p>
        
        <h3>Bear Case (${thesis.bear_price_target:.2f}, {thesis.bear_probability:.0%} probability)</h3>
        <p>{thesis.bear_case}</p>
        
        <h3>Reasons to Buy</h3>
        <ul>{''.join(f'<li>{r}</li>' for r in thesis.reasons_to_buy)}</ul>
        
        <h3>Reasons for Caution</h3>
        <ul>{''.join(f'<li>{r}</li>' for r in thesis.reasons_to_sell)}</ul>
    </div>
"""
        
        # Footer
        html += f"""
    <div class="footer">
        <p>Report generated on {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
        <p>Analyst: {report.analyst}</p>
        <p><em>This report is for informational purposes only and should not be construed as investment advice.</em></p>
    </div>
</body>
</html>
"""
        return html
    
    def format_markdown(self, report: ResearchReport) -> str:
        """Format report as Markdown.
        
        Args:
            report: Research report.
            
        Returns:
            Markdown string.
        """
        md = f"""# {report.company_name} ({report.symbol}) Research Report

**Rating: {report.rating.value.replace('_', ' ').upper()}**

| Metric | Value |
|--------|-------|
| Current Price | ${report.current_price:.2f} |
| Price Target | ${report.price_target:.2f} |
| Upside | {report.upside_pct:.1f}% |

## Executive Summary

{report.executive_summary}

### Key Takeaways
"""
        for t in report.key_takeaways:
            md += f"- {t}\n"
        
        if report.financial_analysis:
            fa = report.financial_analysis
            md += f"""
## Financial Analysis

| Metric | Value |
|--------|-------|
| Revenue (TTM) | ${fa.metrics.revenue_ttm/1e9:.1f}B |
| Revenue Growth | {fa.metrics.revenue_growth_yoy:.1%} |
| Operating Margin | {fa.metrics.operating_margin:.1%} |
| ROE | {fa.metrics.roe:.1%} |
| Debt/Equity | {fa.metrics.debt_to_equity:.2f}x |

### Strengths
"""
            for s in fa.strengths:
                md += f"- {s}\n"
            
            md += "\n### Concerns\n"
            for c in fa.concerns:
                md += f"- {c}\n"
        
        if report.valuation:
            val = report.valuation
            md += f"""
## Valuation

| Method | Value |
|--------|-------|
| DCF | ${val.dcf_value:.2f} |
| Comparable | ${val.comparable_value:.2f} |
| **Fair Value** | **${val.fair_value:.2f}** |

Range: ${val.valuation_range_low:.2f} - ${val.valuation_range_high:.2f}
"""
        
        if report.investment_thesis:
            thesis = report.investment_thesis
            md += f"""
## Investment Thesis

### Bull Case (${thesis.bull_price_target:.2f})
{thesis.bull_case}

### Base Case (${thesis.base_price_target:.2f})
{thesis.base_case}

### Bear Case (${thesis.bear_price_target:.2f})
{thesis.bear_case}
"""
        
        md += f"""
---
*Report generated: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*
*Analyst: {report.analyst}*
"""
        return md
    
    def _generate_executive_summary(
        self,
        symbol: str,
        company_name: str,
        rating: Rating,
        valuation: Optional[ValuationSummary],
        financial: Optional[FinancialAnalysis],
        thesis: Optional[InvestmentThesis],
    ) -> str:
        """Generate executive summary text."""
        parts = []
        
        # Rating statement
        rating_text = {
            Rating.STRONG_BUY: f"We rate {symbol} a Strong Buy",
            Rating.BUY: f"We rate {symbol} a Buy",
            Rating.HOLD: f"We rate {symbol} a Hold",
            Rating.SELL: f"We rate {symbol} a Sell",
            Rating.STRONG_SELL: f"We rate {symbol} a Strong Sell",
        }
        parts.append(rating_text.get(rating, f"We rate {symbol}"))
        
        # Price target
        if valuation and valuation.fair_value > 0:
            parts.append(
                f"with a price target of ${valuation.fair_value:.2f}, "
                f"representing {valuation.upside_pct:.0f}% upside from current levels"
            )
        
        # Key thesis point
        if thesis and thesis.reasons_to_buy:
            parts.append(f". The primary investment case centers on {thesis.reasons_to_buy[0].lower()}")
        
        # Financial highlight
        if financial:
            if financial.metrics.revenue_growth_yoy > 0.10:
                parts.append(
                    f". The company is growing revenue at {financial.metrics.revenue_growth_yoy:.0%}"
                )
            if financial.overall_financial_health > 60:
                parts.append(" with strong financial health")
        
        return "".join(parts) + "."
    
    def _generate_key_takeaways(
        self,
        valuation: Optional[ValuationSummary],
        financial: Optional[FinancialAnalysis],
        competitive: Optional[CompetitiveAnalysis],
        risk: Optional[RiskAssessment],
    ) -> list[str]:
        """Generate key takeaways list."""
        takeaways = []
        
        if valuation:
            if valuation.upside_pct > 15:
                takeaways.append(f"Attractively valued with {valuation.upside_pct:.0f}% upside to fair value")
            elif valuation.upside_pct < -10:
                takeaways.append(f"Appears overvalued with {abs(valuation.upside_pct):.0f}% downside risk")
        
        if financial:
            if financial.overall_financial_health > 65:
                takeaways.append("Strong financial health with quality earnings")
            if financial.metrics.fcf_margin > 0.15:
                takeaways.append("Excellent free cash flow generation")
        
        if competitive:
            if competitive.moat_rating.value == "wide":
                takeaways.append("Wide economic moat provides durable competitive advantage")
            elif competitive.moat_rating.value == "narrow":
                takeaways.append("Narrow moat offers some competitive protection")
        
        if risk:
            if risk.overall_risk_rating.value in ["high", "very_high"]:
                takeaways.append(f"Elevated risk profile warrants caution")
            if risk.key_risks:
                takeaways.append(f"Key risk to monitor: {risk.key_risks[0]}")
        
        return takeaways[:5]
