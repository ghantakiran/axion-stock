"""GIPS-compliant report generation."""

from datetime import datetime
from typing import Dict, List, Optional

from .compliance import ComplianceValidator
from .config import GIPSConfig
from .models import (
    CompositeDefinition,
    CompositePeriod,
    CompositeReturn,
    GIPSDisclosure,
    GIPSPresentation,
)


class GIPSReportGenerator:
    """Generates GIPS-compliant performance presentations."""

    def __init__(self, config: Optional[GIPSConfig] = None):
        self.config = config or GIPSConfig()
        self._validator = ComplianceValidator(self.config)

    def generate_presentation(
        self,
        composite: CompositeDefinition,
        periods: List[CompositePeriod],
        disclosures: Optional[List[GIPSDisclosure]] = None,
    ) -> GIPSPresentation:
        """Generate a full GIPS-compliant presentation."""
        if disclosures is None:
            disclosures = self._validator.generate_disclosures(composite, periods)

        compliance = self._validator.validate_composite(composite, periods)
        status = "Compliant" if compliance.overall_compliant else "Non-Compliant"

        return GIPSPresentation(
            composite_name=composite.name,
            firm_name=self.config.firm_name,
            benchmark_name=composite.benchmark_name,
            periods=sorted(periods, key=lambda p: p.year),
            disclosures=disclosures,
            compliance_status=status,
        )

    def format_presentation_table(self, presentation: GIPSPresentation) -> str:
        """Format presentation as a text table for display."""
        lines = []
        lines.append(f"{'=' * 120}")
        lines.append(f"{presentation.firm_name}")
        lines.append(f"{presentation.composite_name} Composite")
        lines.append(f"Benchmark: {presentation.benchmark_name}")
        lines.append(f"{'=' * 120}")
        lines.append("")

        # Header
        header = (
            f"{'Year':<6} {'Gross':>8} {'Net':>8} {'Bench':>8} "
            f"{'Excess':>8} {'# Ports':>8} {'Comp Assets':>14} "
            f"{'Firm Assets':>14} {'% Firm':>8} {'Disp':>8} "
            f"{'Comp 3yr':>9} {'Bench 3yr':>9}"
        )
        lines.append(header)
        lines.append("-" * 120)

        for p in presentation.periods:
            excess = p.gross_return - p.benchmark_return
            disp_str = f"{p.dispersion:.2%}" if p.dispersion is not None else "N/A"
            comp_std = f"{p.composite_3yr_std:.2%}" if p.composite_3yr_std is not None else "N/A"
            bench_std = f"{p.benchmark_3yr_std:.2%}" if p.benchmark_3yr_std is not None else "N/A"

            line = (
                f"{p.year:<6} {p.gross_return:>8.2%} {p.net_return:>8.2%} "
                f"{p.benchmark_return:>8.2%} {excess:>8.2%} {p.n_portfolios:>8} "
                f"${p.composite_assets:>13,.0f} ${p.firm_assets:>13,.0f} "
                f"{p.pct_firm_assets:>7.1f}% {disp_str:>8} "
                f"{comp_std:>9} {bench_std:>9}"
            )
            lines.append(line)

        lines.append("-" * 120)

        # Cumulative
        cum_gross = presentation.cumulative_gross
        cum_bench = presentation.cumulative_benchmark
        lines.append(
            f"\nCumulative Gross Return: {cum_gross:.2%} | "
            f"Cumulative Benchmark Return: {cum_bench:.2%} | "
            f"Cumulative Excess: {cum_gross - cum_bench:.2%}"
        )

        # Disclosures
        lines.append(f"\n{'=' * 120}")
        lines.append("DISCLOSURES")
        lines.append(f"{'=' * 120}")
        for d in presentation.disclosures:
            lines.append(f"\n[{d.category.upper()}]")
            lines.append(d.text)

        lines.append(f"\nCompliance Status: {presentation.compliance_status}")
        lines.append(f"Report Generated: {presentation.generated_at.strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(lines)

    def generate_summary(self, presentation: GIPSPresentation) -> Dict:
        """Generate a summary dictionary for dashboard display."""
        if not presentation.periods:
            return {"years": 0, "status": presentation.compliance_status}

        latest = presentation.periods[-1]
        first = presentation.periods[0]

        return {
            "composite_name": presentation.composite_name,
            "firm_name": presentation.firm_name,
            "benchmark": presentation.benchmark_name,
            "years": len(presentation.periods),
            "first_year": first.year,
            "latest_year": latest.year,
            "latest_gross": latest.gross_return,
            "latest_net": latest.net_return,
            "latest_benchmark": latest.benchmark_return,
            "latest_excess": latest.gross_return - latest.benchmark_return,
            "cumulative_gross": presentation.cumulative_gross,
            "cumulative_benchmark": presentation.cumulative_benchmark,
            "latest_n_portfolios": latest.n_portfolios,
            "latest_composite_assets": latest.composite_assets,
            "latest_firm_assets": latest.firm_assets,
            "composite_3yr_std": latest.composite_3yr_std,
            "benchmark_3yr_std": latest.benchmark_3yr_std,
            "n_disclosures": len(presentation.disclosures),
            "status": presentation.compliance_status,
        }
