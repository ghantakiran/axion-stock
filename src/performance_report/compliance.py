"""GIPS compliance validation engine."""

from datetime import date, datetime
from typing import List, Optional

from .config import GIPSConfig, MIN_HISTORY_YEARS
from .models import (
    ComplianceCheck,
    ComplianceReport,
    CompositeDefinition,
    CompositePeriod,
    GIPSDisclosure,
)


class ComplianceValidator:
    """Validates GIPS compliance for composites and presentations."""

    def __init__(self, config: Optional[GIPSConfig] = None):
        self.config = config or GIPSConfig()

    def validate_composite(
        self,
        composite: CompositeDefinition,
        periods: List[CompositePeriod],
    ) -> ComplianceReport:
        """Run all GIPS compliance checks on a composite."""
        checks: List[ComplianceCheck] = []

        checks.append(self._check_composite_definition(composite))
        checks.append(self._check_inception_date(composite))
        checks.append(self._check_creation_date(composite))
        checks.append(self._check_benchmark(composite))
        checks.append(self._check_membership_rules(composite))
        checks.append(self._check_active_portfolios(composite))
        checks.append(self._check_history_length(periods))
        checks.append(self._check_annual_returns(periods))
        checks.append(self._check_3yr_std_dev(periods))
        checks.append(self._check_assets_reported(periods))
        checks.append(self._check_n_portfolios(periods))
        checks.append(self._check_dispersion(periods))
        checks.append(self._check_firm_assets(periods))

        overall = all(c.passed for c in checks if c.severity == "error")

        return ComplianceReport(
            composite_id=composite.composite_id,
            checked_at=datetime.now(),
            checks=checks,
            overall_compliant=overall,
        )

    def generate_disclosures(
        self,
        composite: CompositeDefinition,
        periods: List[CompositePeriod],
    ) -> List[GIPSDisclosure]:
        """Generate required GIPS disclosures."""
        disclosures = []

        disclosures.append(GIPSDisclosure(
            category="firm_definition",
            text=f"{self.config.firm_name} is defined as {self.config.firm_definition}.",
        ))

        disclosures.append(GIPSDisclosure(
            category="compliance_claim",
            text=(
                f"{self.config.firm_name} claims compliance with the Global Investment "
                f"Performance Standards (GIPS\u00ae) and has prepared and presented this report "
                f"in compliance with the GIPS standards. {self.config.firm_name} has "
                f"{'been' if self.config.verification_status != 'Not Verified' else 'not been'} "
                f"independently verified."
            ),
        ))

        disclosures.append(GIPSDisclosure(
            category="composite_description",
            text=(
                f"The {composite.name} composite includes all discretionary, fee-paying "
                f"portfolios managed in the {composite.strategy} strategy. "
                f"The composite inception date is {composite.inception_date.isoformat()}. "
                f"The composite creation date is {composite.creation_date.isoformat()}."
            ),
        ))

        disclosures.append(GIPSDisclosure(
            category="benchmark",
            text=(
                f"The benchmark for this composite is the {composite.benchmark_name}. "
                f"The benchmark is used for comparative purposes only."
            ),
        ))

        disclosures.append(GIPSDisclosure(
            category="fees",
            text=(
                f"Returns are presented gross and net of management fees. "
                f"Net returns are calculated by deducting the actual management fee "
                f"from the gross return. The management fee schedule is available upon request."
            ),
        ))

        disclosures.append(GIPSDisclosure(
            category="currency",
            text=f"Valuations and returns are computed and stated in {composite.currency}.",
        ))

        if self.config.include_3yr_std_dev:
            disclosures.append(GIPSDisclosure(
                category="risk_measure",
                text=(
                    "The three-year annualized ex-post standard deviation measures "
                    "the variability of the composite and the benchmark returns over "
                    "the preceding 36-month period."
                ),
            ))

        disclosures.append(GIPSDisclosure(
            category="policies",
            text=(
                f"Policies for valuing investments, calculating performance, and preparing "
                f"GIPS reports are available upon request."
            ),
        ))

        return disclosures

    def _check_composite_definition(self, composite: CompositeDefinition) -> ComplianceCheck:
        has_def = bool(composite.name and composite.strategy and composite.description)
        return ComplianceCheck(
            rule_id="GIPS-1.1",
            description="Composite must have name, strategy, and description",
            passed=has_def,
            details=f"Name='{composite.name}', Strategy='{composite.strategy}'",
        )

    def _check_inception_date(self, composite: CompositeDefinition) -> ComplianceCheck:
        return ComplianceCheck(
            rule_id="GIPS-1.2",
            description="Composite must have inception date",
            passed=composite.inception_date is not None,
            details=f"Inception: {composite.inception_date}",
        )

    def _check_creation_date(self, composite: CompositeDefinition) -> ComplianceCheck:
        valid = (
            composite.creation_date is not None
            and composite.creation_date >= composite.inception_date
        )
        return ComplianceCheck(
            rule_id="GIPS-1.3",
            description="Creation date must exist and be >= inception date",
            passed=valid,
            details=f"Creation: {composite.creation_date}, Inception: {composite.inception_date}",
        )

    def _check_benchmark(self, composite: CompositeDefinition) -> ComplianceCheck:
        return ComplianceCheck(
            rule_id="GIPS-2.1",
            description="Composite must have a designated benchmark",
            passed=bool(composite.benchmark_name),
            details=f"Benchmark: {composite.benchmark_name}",
        )

    def _check_membership_rules(self, composite: CompositeDefinition) -> ComplianceCheck:
        has_rules = bool(composite.membership_rules)
        return ComplianceCheck(
            rule_id="GIPS-3.1",
            description="Composite must define portfolio inclusion/exclusion rules",
            passed=has_rules,
            severity="warning" if not has_rules else "error",
            details=f"Rules defined: {has_rules}",
        )

    def _check_active_portfolios(self, composite: CompositeDefinition) -> ComplianceCheck:
        n = composite.n_portfolios
        return ComplianceCheck(
            rule_id="GIPS-3.2",
            description="Composite should contain at least one portfolio",
            passed=n > 0,
            severity="warning",
            details=f"Active portfolios: {n}",
        )

    def _check_history_length(self, periods: List[CompositePeriod]) -> ComplianceCheck:
        n_years = len(periods)
        passed = n_years >= MIN_HISTORY_YEARS
        return ComplianceCheck(
            rule_id="GIPS-4.1",
            description=f"Must present minimum {MIN_HISTORY_YEARS} years (building to 10)",
            passed=passed,
            severity="warning",
            details=f"Years presented: {n_years}",
        )

    def _check_annual_returns(self, periods: List[CompositePeriod]) -> ComplianceCheck:
        has_returns = all(
            p.gross_return is not None and p.net_return is not None
            for p in periods
        )
        return ComplianceCheck(
            rule_id="GIPS-5.1",
            description="Must present both gross and net annual returns",
            passed=has_returns,
            details=f"All periods have gross+net: {has_returns}",
        )

    def _check_3yr_std_dev(self, periods: List[CompositePeriod]) -> ComplianceCheck:
        if len(periods) < 3:
            return ComplianceCheck(
                rule_id="GIPS-5.2",
                description="3-year annualized std dev required after 3 years",
                passed=True,
                severity="info",
                details="Fewer than 3 years — not yet required",
            )

        # Check periods from year 3 onward
        has_std = all(
            p.composite_3yr_std is not None
            for p in periods[2:]
        )
        return ComplianceCheck(
            rule_id="GIPS-5.2",
            description="3-year annualized std dev required for years 3+",
            passed=has_std,
            severity="warning",
            details=f"3yr std available for applicable periods: {has_std}",
        )

    def _check_assets_reported(self, periods: List[CompositePeriod]) -> ComplianceCheck:
        has_assets = all(p.composite_assets > 0 for p in periods)
        return ComplianceCheck(
            rule_id="GIPS-6.1",
            description="Composite assets must be reported each period",
            passed=has_assets,
            details=f"All periods have assets: {has_assets}",
        )

    def _check_n_portfolios(self, periods: List[CompositePeriod]) -> ComplianceCheck:
        has_count = all(p.n_portfolios > 0 for p in periods)
        return ComplianceCheck(
            rule_id="GIPS-6.2",
            description="Number of portfolios must be reported each period",
            passed=has_count,
            details=f"All periods have portfolio count: {has_count}",
        )

    def _check_dispersion(self, periods: List[CompositePeriod]) -> ComplianceCheck:
        # Dispersion is required when >= 6 portfolios
        applicable = [p for p in periods if p.n_portfolios >= 6]
        if not applicable:
            return ComplianceCheck(
                rule_id="GIPS-6.3",
                description="Internal dispersion required when >= 6 portfolios",
                passed=True,
                severity="info",
                details="No periods with >= 6 portfolios",
            )

        has_disp = all(p.dispersion is not None for p in applicable)
        return ComplianceCheck(
            rule_id="GIPS-6.3",
            description="Internal dispersion required when >= 6 portfolios",
            passed=has_disp,
            severity="warning",
            details=f"Dispersion available for applicable periods: {has_disp}",
        )

    def _check_firm_assets(self, periods: List[CompositePeriod]) -> ComplianceCheck:
        has_firm = all(p.firm_assets > 0 for p in periods)
        return ComplianceCheck(
            rule_id="GIPS-7.1",
            description="Total firm assets or % of firm assets must be reported",
            passed=has_firm,
            severity="warning",
            details=f"Firm assets reported: {has_firm}",
        )
