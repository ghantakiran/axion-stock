"""Tax Liability Estimation.

Calculates federal and state tax liability based on income,
capital gains, and filing status.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from src.tax.config import (
    FilingStatus,
    TaxConfig,
    DEFAULT_TAX_CONFIG,
    FEDERAL_BRACKETS_2024,
    LTCG_BRACKETS_2024,
    NIIT_THRESHOLDS,
    NIIT_RATE,
    STATE_TAX_RATES,
    STATE_LTCG_EXCLUSIONS,
    NO_INCOME_TAX_STATES,
)
from src.tax.models import TaxEstimate, TaxSavingsProjection, GainLossReport

logger = logging.getLogger(__name__)


class TaxEstimator:
    """Estimates tax liability for individuals.
    
    Calculates:
    - Federal ordinary income tax
    - Federal capital gains tax (short-term and long-term)
    - Net Investment Income Tax (NIIT)
    - State income tax
    - Effective and marginal tax rates
    """
    
    def __init__(self, config: Optional[TaxConfig] = None):
        self.config = config or DEFAULT_TAX_CONFIG
    
    def estimate_liability(
        self,
        ordinary_income: float,
        short_term_gains: float = 0.0,
        long_term_gains: float = 0.0,
        filing_status: Optional[FilingStatus] = None,
        state: Optional[str] = None,
        deductions: float = 0.0,
    ) -> TaxEstimate:
        """Estimate total tax liability.
        
        Args:
            ordinary_income: Wages, salary, interest, etc.
            short_term_gains: Net short-term capital gains.
            long_term_gains: Net long-term capital gains.
            filing_status: IRS filing status.
            state: State abbreviation (e.g., 'CA', 'NY').
            deductions: Total deductions (itemized or standard).
            
        Returns:
            TaxEstimate with full breakdown.
        """
        filing_status = filing_status or self.config.tax_profile.filing_status
        state = state or self.config.tax_profile.state
        
        # Apply deductions to ordinary income
        taxable_ordinary = max(0, ordinary_income - deductions)
        
        # Short-term gains are taxed as ordinary income
        total_ordinary_taxable = taxable_ordinary + short_term_gains
        
        # Calculate federal ordinary income tax
        federal_ordinary = self._calculate_bracket_tax(
            total_ordinary_taxable,
            FEDERAL_BRACKETS_2024[filing_status],
        )
        
        # Calculate federal long-term capital gains tax
        # LTCG rate depends on total taxable income
        total_income = total_ordinary_taxable + long_term_gains
        federal_ltcg = self._calculate_ltcg_tax(
            long_term_gains,
            total_ordinary_taxable,
            filing_status,
        )
        
        # Calculate NIIT
        niit = self._calculate_niit(
            short_term_gains + long_term_gains,
            total_income,
            filing_status,
        )
        
        # Calculate state tax
        state_tax = self._calculate_state_tax(
            total_income,
            long_term_gains,
            state,
        )
        
        # Totals
        total_federal = federal_ordinary + federal_ltcg + niit
        total_tax = total_federal + state_tax
        
        # Effective rate
        if total_income > 0:
            effective_rate = total_tax / total_income
        else:
            effective_rate = 0.0
        
        # Marginal rate (for next dollar of ordinary income)
        marginal_rate = self._get_marginal_rate(
            total_ordinary_taxable,
            FEDERAL_BRACKETS_2024[filing_status],
        )
        
        # Investment income tax specifically
        investment_income = short_term_gains + long_term_gains
        investment_tax = federal_ltcg + self._calculate_bracket_tax(
            short_term_gains,
            FEDERAL_BRACKETS_2024[filing_status],
            starting_income=taxable_ordinary,
        ) + niit
        
        investment_effective = 0.0
        if investment_income > 0:
            investment_effective = investment_tax / investment_income
        
        return TaxEstimate(
            ordinary_income=ordinary_income,
            short_term_gains=short_term_gains,
            long_term_gains=long_term_gains,
            total_taxable_income=total_income,
            federal_ordinary_tax=federal_ordinary,
            federal_stcg_tax=self._calculate_bracket_tax(
                short_term_gains,
                FEDERAL_BRACKETS_2024[filing_status],
                starting_income=taxable_ordinary,
            ),
            federal_ltcg_tax=federal_ltcg,
            federal_niit=niit,
            total_federal_tax=total_federal,
            state=state,
            state_tax=state_tax,
            total_tax=total_tax,
            effective_rate=effective_rate,
            marginal_rate=marginal_rate,
            investment_income_tax=investment_tax,
            investment_effective_rate=investment_effective,
            filing_status=filing_status,
            tax_year=self.config.tax_year,
        )
    
    def _calculate_bracket_tax(
        self,
        income: float,
        brackets: list[tuple[float, float]],
        starting_income: float = 0.0,
    ) -> float:
        """Calculate tax using marginal brackets.
        
        Args:
            income: Income to tax.
            brackets: List of (threshold, rate) tuples.
            starting_income: Income already taxed (for stacking).
            
        Returns:
            Total tax amount.
        """
        if income <= 0:
            return 0.0
        
        tax = 0.0
        prev_threshold = 0.0
        remaining = income
        
        for threshold, rate in brackets:
            # Adjust threshold for starting income
            adjusted_threshold = max(0, threshold - starting_income)
            
            if remaining <= 0:
                break
            
            bracket_size = adjusted_threshold - prev_threshold
            if bracket_size <= 0:
                prev_threshold = adjusted_threshold
                continue
            
            taxable_in_bracket = min(remaining, bracket_size)
            tax += taxable_in_bracket * rate
            remaining -= taxable_in_bracket
            prev_threshold = adjusted_threshold
        
        # Any remaining at top rate
        if remaining > 0:
            tax += remaining * brackets[-1][1]
        
        return tax
    
    def _calculate_ltcg_tax(
        self,
        ltcg: float,
        ordinary_income: float,
        filing_status: FilingStatus,
    ) -> float:
        """Calculate long-term capital gains tax.
        
        LTCG has special lower rates that depend on total income.
        """
        if ltcg <= 0:
            return 0.0
        
        brackets = LTCG_BRACKETS_2024[filing_status]
        
        tax = 0.0
        prev_threshold = 0.0
        remaining = ltcg
        
        for threshold, rate in brackets:
            if remaining <= 0:
                break
            
            # How much of this bracket is available?
            # (already used by ordinary income)
            bracket_start = max(prev_threshold, ordinary_income)
            
            if bracket_start >= threshold:
                prev_threshold = threshold
                continue
            
            bracket_space = threshold - bracket_start
            taxable = min(remaining, bracket_space)
            tax += taxable * rate
            remaining -= taxable
            prev_threshold = threshold
        
        # Any remaining at top rate
        if remaining > 0:
            tax += remaining * brackets[-1][1]
        
        return tax
    
    def _calculate_niit(
        self,
        investment_income: float,
        total_income: float,
        filing_status: FilingStatus,
    ) -> float:
        """Calculate Net Investment Income Tax (3.8%).
        
        Applies to lesser of:
        - Net investment income, OR
        - Amount by which MAGI exceeds threshold
        """
        threshold = NIIT_THRESHOLDS[filing_status]
        
        if total_income <= threshold:
            return 0.0
        
        excess = total_income - threshold
        taxable = min(investment_income, excess)
        
        return taxable * NIIT_RATE
    
    def _calculate_state_tax(
        self,
        total_income: float,
        ltcg: float,
        state: str,
    ) -> float:
        """Calculate state income tax (simplified).
        
        Uses top marginal rate for simplicity.
        Some states have special capital gains treatment.
        """
        if state in NO_INCOME_TAX_STATES:
            return 0.0
        
        rate = STATE_TAX_RATES.get(state, 0.0)
        
        # Check for LTCG exclusions
        if state in STATE_LTCG_EXCLUSIONS and ltcg > 0:
            exclusion = STATE_LTCG_EXCLUSIONS[state]
            if exclusion < 1:
                # Percentage exclusion (e.g., SC 44%)
                taxable_ltcg = ltcg * (1 - exclusion)
                return (total_income - ltcg + taxable_ltcg) * rate
            else:
                # Fixed rate for LTCG
                non_ltcg_income = total_income - ltcg
                return non_ltcg_income * rate + ltcg * exclusion
        
        return total_income * rate
    
    def _get_marginal_rate(
        self,
        income: float,
        brackets: list[tuple[float, float]],
    ) -> float:
        """Get marginal tax rate for income level."""
        for threshold, rate in brackets:
            if income <= threshold:
                return rate
        return brackets[-1][1]
    
    def compare_scenarios(
        self,
        base_income: float,
        scenarios: list[dict],
        filing_status: Optional[FilingStatus] = None,
        state: Optional[str] = None,
    ) -> list[TaxSavingsProjection]:
        """Compare tax liability across different scenarios.
        
        Args:
            base_income: Base ordinary income.
            scenarios: List of dicts with 'name', 'short_term', 'long_term'.
            filing_status: Filing status.
            state: State.
            
        Returns:
            List of projections comparing each scenario.
        """
        filing_status = filing_status or self.config.tax_profile.filing_status
        state = state or self.config.tax_profile.state
        
        # Calculate base case (no investment income)
        base = self.estimate_liability(
            base_income, 0, 0, filing_status, state
        )
        
        projections = []
        
        for scenario in scenarios:
            estimate = self.estimate_liability(
                base_income,
                scenario.get("short_term", 0),
                scenario.get("long_term", 0),
                filing_status,
                state,
            )
            
            projections.append(TaxSavingsProjection(
                action=scenario.get("name", "unnamed"),
                current_tax=base.total_tax,
                projected_tax=estimate.total_tax,
                tax_savings=base.total_tax - estimate.total_tax,
                assumptions={
                    "ordinary_income": base_income,
                    "short_term_gains": scenario.get("short_term", 0),
                    "long_term_gains": scenario.get("long_term", 0),
                    "filing_status": filing_status.value,
                    "state": state,
                },
            ))
        
        return projections
    
    def estimate_from_gain_loss_report(
        self,
        report: GainLossReport,
        ordinary_income: Optional[float] = None,
    ) -> TaxEstimate:
        """Estimate tax from a gain/loss report."""
        ordinary_income = ordinary_income or self.config.tax_profile.estimated_ordinary_income
        
        # Net realized gains/losses
        net_short = report.net_short_term_realized
        net_long = report.net_long_term_realized
        
        # Apply capital loss limitation if net is negative
        total_net = net_short + net_long
        if total_net < -3000:
            # Can only deduct $3,000 against ordinary income
            # Excess carries forward
            deductible_loss = -3000
            if net_short < 0 and net_long < 0:
                # Proportionally reduce both
                ratio = -3000 / total_net
                net_short *= ratio
                net_long *= ratio
            elif net_short < 0:
                net_short = max(net_short, -3000 - max(0, net_long))
            else:
                net_long = max(net_long, -3000 - max(0, net_short))
        
        return self.estimate_liability(
            ordinary_income=ordinary_income,
            short_term_gains=net_short,
            long_term_gains=net_long,
        )
    
    def calculate_breakeven_hold_days(
        self,
        unrealized_gain: float,
        days_held: int,
        ordinary_income: float,
    ) -> dict:
        """Calculate if it's worth waiting for long-term treatment.
        
        Compares tax if sold now (short-term) vs waiting for long-term.
        """
        days_to_long_term = max(0, 366 - days_held)
        
        if days_to_long_term == 0:
            return {
                "already_long_term": True,
                "recommendation": "Already qualifies for long-term rate",
            }
        
        # Tax if sold now (short-term)
        st_estimate = self.estimate_liability(
            ordinary_income, unrealized_gain, 0
        )
        
        # Tax if sold after becoming long-term
        lt_estimate = self.estimate_liability(
            ordinary_income, 0, unrealized_gain
        )
        
        tax_savings = st_estimate.total_tax - lt_estimate.total_tax
        
        return {
            "days_to_long_term": days_to_long_term,
            "short_term_tax": st_estimate.total_tax,
            "long_term_tax": lt_estimate.total_tax,
            "tax_savings": tax_savings,
            "savings_per_day": tax_savings / days_to_long_term if days_to_long_term > 0 else 0,
            "recommendation": (
                f"Waiting {days_to_long_term} days saves ${tax_savings:.2f}"
                if tax_savings > 0 else "No benefit to waiting"
            ),
        }
