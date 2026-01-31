"""Tax Report Generation.

Generates IRS tax forms and summary reports for capital gains/losses.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import logging

from src.tax.config import (
    BasisReportingCategory,
    AdjustmentCode,
    HoldingPeriod,
    TaxConfig,
    DEFAULT_TAX_CONFIG,
)
from src.tax.models import (
    RealizedGain,
    WashSale,
    Form8949,
    Form8949Entry,
    ScheduleD,
    TaxSummaryReport,
    GainLossReport,
    TaxLot,
)
from src.tax.estimator import TaxEstimator

logger = logging.getLogger(__name__)


class TaxReportGenerator:
    """Generates tax reports and IRS forms.
    
    Produces:
    - Form 8949 (Sales and Other Dispositions of Capital Assets)
    - Schedule D (Capital Gains and Losses summary)
    - Annual tax summary reports
    - Gain/loss reports by period
    """
    
    def __init__(self, config: Optional[TaxConfig] = None):
        self.config = config or DEFAULT_TAX_CONFIG
        self.estimator = TaxEstimator(config)
    
    def generate_form_8949(
        self,
        realized_gains: list[RealizedGain],
        tax_year: int,
        name: str = "",
        ssn: str = "",
    ) -> Form8949:
        """Generate IRS Form 8949.
        
        Args:
            realized_gains: List of realized gains/losses.
            tax_year: Tax year for the form.
            name: Taxpayer name.
            ssn: Social Security Number (last 4 for display).
            
        Returns:
            Form8949 with all entries populated.
        """
        form = Form8949(
            tax_year=tax_year,
            name=name,
            ssn=ssn,
        )
        
        # Filter to the tax year
        year_gains = [g for g in realized_gains if g.sale_date.year == tax_year]
        
        for gain in year_gains:
            entry = self._create_8949_entry(gain)
            
            if gain.holding_period == HoldingPeriod.SHORT_TERM:
                form.short_term_entries.append(entry)
            else:
                form.long_term_entries.append(entry)
        
        # Sort entries by sale date
        form.short_term_entries.sort(key=lambda x: x.date_sold)
        form.long_term_entries.sort(key=lambda x: x.date_sold)
        
        return form
    
    def _create_8949_entry(self, gain: RealizedGain) -> Form8949Entry:
        """Create a Form 8949 line item from a realized gain."""
        # Description format: "100 sh AAPL"
        description = f"{gain.shares:.0f} sh {gain.symbol}"
        
        # Determine adjustment code and amount
        adjustment_code = None
        adjustment_amount = 0.0
        
        if gain.is_wash_sale and gain.disallowed_loss > 0:
            adjustment_code = AdjustmentCode.W.value
            adjustment_amount = gain.disallowed_loss
        
        # Calculate reported gain/loss (after adjustments)
        reported_gain = gain.gain_loss
        if adjustment_amount > 0:
            reported_gain = gain.gain_loss + adjustment_amount
        
        return Form8949Entry(
            description=description,
            date_acquired=gain.acquisition_date,
            date_sold=gain.sale_date,
            proceeds=gain.proceeds,
            cost_basis=gain.cost_basis,
            adjustment_code=adjustment_code,
            adjustment_amount=adjustment_amount,
            gain_loss=reported_gain,
            category=gain.basis_category,
        )
    
    def generate_schedule_d(
        self,
        form_8949: Form8949,
        short_term_carryover: float = 0.0,
        long_term_carryover: float = 0.0,
        k1_short_term: float = 0.0,
        k1_long_term: float = 0.0,
    ) -> ScheduleD:
        """Generate Schedule D from Form 8949 totals.
        
        Args:
            form_8949: Completed Form 8949.
            short_term_carryover: Prior year short-term loss carryover.
            long_term_carryover: Prior year long-term loss carryover.
            k1_short_term: Short-term from K-1s.
            k1_long_term: Long-term from K-1s.
            
        Returns:
            ScheduleD with summary totals.
        """
        schedule = ScheduleD(
            tax_year=form_8949.tax_year,
            short_term_from_8949=form_8949.short_term_gain_loss,
            short_term_from_k1=k1_short_term,
            short_term_carryover=short_term_carryover,
            long_term_from_8949=form_8949.long_term_gain_loss,
            long_term_from_k1=k1_long_term,
            long_term_carryover=long_term_carryover,
        )
        
        schedule.calculate_totals()
        return schedule
    
    def generate_gain_loss_report(
        self,
        realized_gains: list[RealizedGain],
        lots: list[TaxLot],
        current_prices: dict[str, float],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> GainLossReport:
        """Generate comprehensive gain/loss report.
        
        Args:
            realized_gains: Realized gains/losses.
            lots: Current tax lots (for unrealized).
            current_prices: Current market prices.
            start_date: Report start date.
            end_date: Report end date.
            
        Returns:
            GainLossReport with realized and unrealized totals.
        """
        end_date = end_date or date.today()
        start_date = start_date or date(end_date.year, 1, 1)
        
        report = GainLossReport(
            start_date=start_date,
            end_date=end_date,
        )
        
        # Realized gains/losses in period
        period_gains = [
            g for g in realized_gains
            if start_date <= g.sale_date <= end_date
        ]
        
        for gain in period_gains:
            if gain.holding_period == HoldingPeriod.SHORT_TERM:
                if gain.gain_loss >= 0:
                    report.short_term_realized_gains += gain.gain_loss
                else:
                    report.short_term_realized_losses += gain.gain_loss
            else:
                if gain.gain_loss >= 0:
                    report.long_term_realized_gains += gain.gain_loss
                else:
                    report.long_term_realized_losses += gain.gain_loss
            
            # Track wash sale disallowed
            if gain.is_wash_sale:
                report.disallowed_losses += gain.disallowed_loss
        
        # Unrealized gains/losses
        for lot in lots:
            if lot.remaining_shares <= 0:
                continue
            
            price = current_prices.get(lot.symbol, 0.0)
            if price == 0:
                continue
            
            ratio = lot.remaining_shares / lot.shares
            basis = lot.adjusted_basis * ratio
            value = lot.remaining_shares * price
            unrealized = value - basis
            
            if lot.holding_period == HoldingPeriod.SHORT_TERM:
                if unrealized >= 0:
                    report.short_term_unrealized_gains += unrealized
                else:
                    report.short_term_unrealized_losses += unrealized
            else:
                if unrealized >= 0:
                    report.long_term_unrealized_gains += unrealized
                else:
                    report.long_term_unrealized_losses += unrealized
        
        return report
    
    def generate_tax_summary(
        self,
        account_id: str,
        realized_gains: list[RealizedGain],
        wash_sales: list[WashSale],
        harvest_count: int = 0,
        harvested_losses: float = 0.0,
        dividends_qualified: float = 0.0,
        dividends_ordinary: float = 0.0,
        tax_year: Optional[int] = None,
    ) -> TaxSummaryReport:
        """Generate annual tax summary report.
        
        Args:
            account_id: Account identifier.
            realized_gains: All realized gains/losses.
            wash_sales: Wash sale records.
            harvest_count: Number of harvests executed.
            harvested_losses: Total losses harvested.
            dividends_qualified: Qualified dividends received.
            dividends_ordinary: Ordinary dividends received.
            tax_year: Tax year (defaults to current year).
            
        Returns:
            TaxSummaryReport with full summary.
        """
        tax_year = tax_year or date.today().year
        
        # Filter to tax year
        year_gains = [g for g in realized_gains if g.sale_date.year == tax_year]
        year_washes = [w for w in wash_sales if w.loss_sale_date.year == tax_year]
        
        # Calculate totals
        total_proceeds = sum(g.proceeds for g in year_gains)
        total_basis = sum(g.cost_basis for g in year_gains)
        
        short_term = sum(
            g.gain_loss for g in year_gains
            if g.holding_period == HoldingPeriod.SHORT_TERM
        )
        long_term = sum(
            g.gain_loss for g in year_gains
            if g.holding_period == HoldingPeriod.LONG_TERM
        )
        
        wash_disallowed = sum(w.disallowed_loss for w in year_washes)
        
        # Estimate tax liability
        estimate = self.estimator.estimate_liability(
            ordinary_income=self.config.tax_profile.estimated_ordinary_income,
            short_term_gains=short_term,
            long_term_gains=long_term,
        )
        
        # Estimate tax savings from harvesting
        harvest_savings = 0.0
        if harvested_losses > 0:
            # Rough estimate: harvested losses * marginal rate
            harvest_savings = harvested_losses * estimate.marginal_rate
        
        return TaxSummaryReport(
            tax_year=tax_year,
            account_id=account_id,
            total_proceeds=total_proceeds,
            total_cost_basis=total_basis,
            short_term_gain_loss=short_term,
            long_term_gain_loss=long_term,
            net_gain_loss=short_term + long_term,
            wash_sale_disallowed=wash_disallowed,
            wash_sale_count=len(year_washes),
            total_harvested_losses=harvested_losses,
            harvest_count=harvest_count,
            estimated_tax_savings=harvest_savings,
            qualified_dividends=dividends_qualified,
            ordinary_dividends=dividends_ordinary,
            estimated_tax_liability=estimate.total_tax,
            effective_rate=estimate.effective_rate,
        )
    
    def format_form_8949_text(self, form: Form8949) -> str:
        """Format Form 8949 as human-readable text."""
        lines = [
            f"Form 8949 - Sales and Other Dispositions of Capital Assets",
            f"Tax Year: {form.tax_year}",
            f"Name: {form.name}",
            "=" * 80,
            "",
            "PART I - SHORT-TERM (Held 1 year or less)",
            "-" * 80,
        ]
        
        if form.short_term_entries:
            lines.append(
                f"{'Description':<25} {'Acquired':<12} {'Sold':<12} "
                f"{'Proceeds':>12} {'Basis':>12} {'Adj':>8} {'Gain/Loss':>12}"
            )
            lines.append("-" * 80)
            
            for entry in form.short_term_entries:
                adj_str = f"{entry.adjustment_code or ''}{entry.adjustment_amount:>6.0f}" if entry.adjustment_amount else ""
                lines.append(
                    f"{entry.description:<25} {entry.date_acquired.strftime('%m/%d/%Y'):<12} "
                    f"{entry.date_sold.strftime('%m/%d/%Y'):<12} "
                    f"{entry.proceeds:>12,.2f} {entry.cost_basis:>12,.2f} "
                    f"{adj_str:>8} {entry.gain_loss:>12,.2f}"
                )
            
            lines.append("-" * 80)
            lines.append(
                f"{'TOTALS':<25} {'':<12} {'':<12} "
                f"{form.short_term_proceeds:>12,.2f} {form.short_term_basis:>12,.2f} "
                f"{form.short_term_adjustments:>8,.0f} {form.short_term_gain_loss:>12,.2f}"
            )
        else:
            lines.append("No short-term transactions")
        
        lines.extend([
            "",
            "PART II - LONG-TERM (Held more than 1 year)",
            "-" * 80,
        ])
        
        if form.long_term_entries:
            lines.append(
                f"{'Description':<25} {'Acquired':<12} {'Sold':<12} "
                f"{'Proceeds':>12} {'Basis':>12} {'Adj':>8} {'Gain/Loss':>12}"
            )
            lines.append("-" * 80)
            
            for entry in form.long_term_entries:
                adj_str = f"{entry.adjustment_code or ''}{entry.adjustment_amount:>6.0f}" if entry.adjustment_amount else ""
                lines.append(
                    f"{entry.description:<25} {entry.date_acquired.strftime('%m/%d/%Y'):<12} "
                    f"{entry.date_sold.strftime('%m/%d/%Y'):<12} "
                    f"{entry.proceeds:>12,.2f} {entry.cost_basis:>12,.2f} "
                    f"{adj_str:>8} {entry.gain_loss:>12,.2f}"
                )
            
            lines.append("-" * 80)
            lines.append(
                f"{'TOTALS':<25} {'':<12} {'':<12} "
                f"{form.long_term_proceeds:>12,.2f} {form.long_term_basis:>12,.2f} "
                f"{form.long_term_adjustments:>8,.0f} {form.long_term_gain_loss:>12,.2f}"
            )
        else:
            lines.append("No long-term transactions")
        
        return "\n".join(lines)
    
    def format_schedule_d_text(self, schedule: ScheduleD) -> str:
        """Format Schedule D as human-readable text."""
        lines = [
            f"Schedule D - Capital Gains and Losses",
            f"Tax Year: {schedule.tax_year}",
            "=" * 60,
            "",
            "PART I - SHORT-TERM CAPITAL GAINS AND LOSSES",
            "-" * 60,
            f"  From Form 8949:           {schedule.short_term_from_8949:>15,.2f}",
            f"  From Schedule K-1:        {schedule.short_term_from_k1:>15,.2f}",
            f"  Carryover from prior year:{schedule.short_term_carryover:>15,.2f}",
            f"  Net Short-Term:           {schedule.net_short_term:>15,.2f}",
            "",
            "PART II - LONG-TERM CAPITAL GAINS AND LOSSES",
            "-" * 60,
            f"  From Form 8949:           {schedule.long_term_from_8949:>15,.2f}",
            f"  From Schedule K-1:        {schedule.long_term_from_k1:>15,.2f}",
            f"  Carryover from prior year:{schedule.long_term_carryover:>15,.2f}",
            f"  Net Long-Term:            {schedule.net_long_term:>15,.2f}",
            "",
            "PART III - SUMMARY",
            "-" * 60,
            f"  Net Capital Gain (Loss):  {schedule.net_capital_gain_loss:>15,.2f}",
        ]
        
        if schedule.capital_loss_carryover < 0:
            lines.append(
                f"  Loss Carryover to Next Year:{schedule.capital_loss_carryover:>12,.2f}"
            )
        
        return "\n".join(lines)
    
    def format_summary_text(self, summary: TaxSummaryReport) -> str:
        """Format tax summary as human-readable text."""
        lines = [
            f"TAX SUMMARY REPORT - {summary.tax_year}",
            f"Account: {summary.account_id}",
            "=" * 60,
            "",
            "CAPITAL GAINS/LOSSES",
            "-" * 60,
            f"  Total Proceeds:           {summary.total_proceeds:>15,.2f}",
            f"  Total Cost Basis:         {summary.total_cost_basis:>15,.2f}",
            f"  Short-Term Gain/Loss:     {summary.short_term_gain_loss:>15,.2f}",
            f"  Long-Term Gain/Loss:      {summary.long_term_gain_loss:>15,.2f}",
            f"  Net Capital Gain/Loss:    {summary.net_gain_loss:>15,.2f}",
            "",
            "WASH SALES",
            "-" * 60,
            f"  Wash Sale Count:          {summary.wash_sale_count:>15}",
            f"  Disallowed Losses:        {summary.wash_sale_disallowed:>15,.2f}",
            "",
            "TAX-LOSS HARVESTING",
            "-" * 60,
            f"  Harvests Executed:        {summary.harvest_count:>15}",
            f"  Total Losses Harvested:   {summary.total_harvested_losses:>15,.2f}",
            f"  Estimated Tax Savings:    {summary.estimated_tax_savings:>15,.2f}",
            "",
            "DIVIDENDS",
            "-" * 60,
            f"  Qualified Dividends:      {summary.qualified_dividends:>15,.2f}",
            f"  Ordinary Dividends:       {summary.ordinary_dividends:>15,.2f}",
            "",
            "TAX ESTIMATE",
            "-" * 60,
            f"  Estimated Tax Liability:  {summary.estimated_tax_liability:>15,.2f}",
            f"  Effective Tax Rate:       {summary.effective_rate:>14.1%}",
            "",
            f"Generated: {summary.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]
        
        return "\n".join(lines)
