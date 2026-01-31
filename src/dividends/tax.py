"""Dividend Tax Analysis.

Analyze tax implications of dividend income.
"""

from datetime import date
from typing import Optional
import logging

from src.dividends.config import (
    TaxClassification,
    DividendConfig,
    DEFAULT_DIVIDEND_CONFIG,
    QUALIFIED_TAX_RATES,
    ORDINARY_TAX_RATES,
)
from src.dividends.models import DividendTaxAnalysis, DividendHolding

logger = logging.getLogger(__name__)


class TaxAnalyzer:
    """Analyzes dividend tax implications.
    
    Calculates tax liability for qualified and non-qualified dividends,
    and estimates after-tax income.
    
    Example:
        analyzer = TaxAnalyzer()
        
        analysis = analyzer.analyze_portfolio(
            holdings,
            tax_year=2024,
            taxable_income=100000,
        )
        
        print(f"Total dividends: ${analysis.total_dividend_income:,.2f}")
        print(f"Estimated tax: ${analysis.total_estimated_tax:,.2f}")
        print(f"After-tax income: ${analysis.after_tax_income:,.2f}")
    """
    
    def __init__(self, config: Optional[DividendConfig] = None):
        self.config = config or DEFAULT_DIVIDEND_CONFIG
    
    def analyze_holding(
        self,
        holding: DividendHolding,
        is_qualified: bool = True,
        tax_bracket: float = 0.22,
        qualified_rate: float = 0.15,
    ) -> dict:
        """Analyze tax for a single holding.
        
        Args:
            holding: Dividend holding.
            is_qualified: Whether dividends are qualified.
            tax_bracket: Ordinary income tax bracket.
            qualified_rate: Qualified dividend tax rate.
            
        Returns:
            Dict with tax analysis.
        """
        annual_income = holding.annual_income
        
        if is_qualified:
            tax = annual_income * qualified_rate
            effective_rate = qualified_rate
        else:
            tax = annual_income * tax_bracket
            effective_rate = tax_bracket
        
        return {
            "symbol": holding.symbol,
            "annual_income": annual_income,
            "is_qualified": is_qualified,
            "tax_rate": effective_rate,
            "estimated_tax": tax,
            "after_tax_income": annual_income - tax,
        }
    
    def analyze_portfolio(
        self,
        holdings: list[DividendHolding],
        tax_year: int = 2024,
        taxable_income: float = 100000,
        filing_status: str = "single",
        state_tax_rate: float = 0.05,
    ) -> DividendTaxAnalysis:
        """Analyze tax for entire portfolio.
        
        Args:
            holdings: List of dividend holdings.
            tax_year: Tax year.
            taxable_income: Other taxable income.
            filing_status: Tax filing status.
            state_tax_rate: State income tax rate.
            
        Returns:
            DividendTaxAnalysis.
        """
        analysis = DividendTaxAnalysis(tax_year=tax_year)
        
        # Determine tax rates based on income
        qualified_rate = self._get_qualified_rate(taxable_income, filing_status)
        ordinary_rate = self._get_ordinary_rate(taxable_income, filing_status)
        
        # Categorize dividends
        for holding in holdings:
            income = holding.annual_income
            
            # Assume most are qualified (simplification)
            # In reality, this would be tracked per holding
            analysis.qualified_dividends += income * 0.9
            analysis.non_qualified_dividends += income * 0.1
        
        analysis.total_dividend_income = (
            analysis.qualified_dividends +
            analysis.non_qualified_dividends +
            analysis.return_of_capital +
            analysis.foreign_dividends
        )
        
        # Calculate taxes
        analysis.estimated_tax_qualified = analysis.qualified_dividends * qualified_rate
        analysis.estimated_tax_ordinary = analysis.non_qualified_dividends * ordinary_rate
        
        # State tax (on all dividends)
        state_tax = analysis.total_dividend_income * state_tax_rate
        
        analysis.total_estimated_tax = (
            analysis.estimated_tax_qualified +
            analysis.estimated_tax_ordinary +
            state_tax
        )
        
        # After-tax
        analysis.after_tax_income = analysis.total_dividend_income - analysis.total_estimated_tax
        
        # Effective rate
        if analysis.total_dividend_income > 0:
            analysis.effective_tax_rate = analysis.total_estimated_tax / analysis.total_dividend_income
        
        return analysis
    
    def _get_qualified_rate(
        self,
        income: float,
        filing_status: str,
    ) -> float:
        """Get qualified dividend tax rate based on income."""
        # Simplified - using single filer brackets
        if income <= 44625:
            return 0.0
        elif income <= 492300:
            return 0.15
        else:
            return 0.20
    
    def _get_ordinary_rate(
        self,
        income: float,
        filing_status: str,
    ) -> float:
        """Get ordinary income tax rate based on income."""
        # Simplified - using single filer brackets
        if income <= 11600:
            return 0.10
        elif income <= 47150:
            return 0.12
        elif income <= 100525:
            return 0.22
        elif income <= 191950:
            return 0.24
        elif income <= 243725:
            return 0.32
        elif income <= 609350:
            return 0.35
        else:
            return 0.37
    
    def compare_qualified_vs_ordinary(
        self,
        dividend_income: float,
        taxable_income: float,
    ) -> dict:
        """Compare tax impact of qualified vs ordinary dividends.
        
        Returns:
            Dict with comparison.
        """
        qualified_rate = self._get_qualified_rate(taxable_income, "single")
        ordinary_rate = self._get_ordinary_rate(taxable_income, "single")
        
        tax_qualified = dividend_income * qualified_rate
        tax_ordinary = dividend_income * ordinary_rate
        
        savings = tax_ordinary - tax_qualified
        
        return {
            "dividend_income": dividend_income,
            "qualified_rate": qualified_rate,
            "ordinary_rate": ordinary_rate,
            "tax_if_qualified": tax_qualified,
            "tax_if_ordinary": tax_ordinary,
            "tax_savings": savings,
            "savings_pct": savings / dividend_income if dividend_income > 0 else 0,
        }
    
    def estimate_annual_tax(
        self,
        annual_dividend_income: float,
        pct_qualified: float = 0.90,
        taxable_income: float = 100000,
        state_rate: float = 0.05,
    ) -> dict:
        """Quick estimate of annual dividend tax.
        
        Args:
            annual_dividend_income: Total dividend income.
            pct_qualified: Percentage that is qualified.
            taxable_income: Other income for bracket determination.
            state_rate: State tax rate.
            
        Returns:
            Dict with tax estimates.
        """
        qualified = annual_dividend_income * pct_qualified
        ordinary = annual_dividend_income * (1 - pct_qualified)
        
        qualified_rate = self._get_qualified_rate(taxable_income, "single")
        ordinary_rate = self._get_ordinary_rate(taxable_income, "single")
        
        federal_tax = qualified * qualified_rate + ordinary * ordinary_rate
        state_tax = annual_dividend_income * state_rate
        total_tax = federal_tax + state_tax
        
        return {
            "gross_income": annual_dividend_income,
            "qualified_amount": qualified,
            "ordinary_amount": ordinary,
            "federal_tax": federal_tax,
            "state_tax": state_tax,
            "total_tax": total_tax,
            "after_tax_income": annual_dividend_income - total_tax,
            "effective_rate": total_tax / annual_dividend_income if annual_dividend_income > 0 else 0,
        }
    
    def tax_efficient_allocation(
        self,
        qualified_holdings: list[DividendHolding],
        non_qualified_holdings: list[DividendHolding],
        taxable_space: float,
        tax_advantaged_space: float,
    ) -> dict:
        """Suggest tax-efficient allocation between accounts.
        
        Higher-tax dividends should go in tax-advantaged accounts.
        
        Returns:
            Dict with allocation recommendations.
        """
        # Sort by yield (higher yield = more tax impact)
        qualified_sorted = sorted(
            qualified_holdings,
            key=lambda h: h.current_yield,
            reverse=True
        )
        non_qualified_sorted = sorted(
            non_qualified_holdings,
            key=lambda h: h.current_yield,
            reverse=True
        )
        
        # Non-qualified should go in tax-advantaged first
        tax_advantaged_holdings = []
        taxable_holdings = []
        
        remaining_tax_adv = tax_advantaged_space
        remaining_taxable = taxable_space
        
        # Prioritize non-qualified for tax-advantaged
        for h in non_qualified_sorted:
            if remaining_tax_adv >= h.market_value:
                tax_advantaged_holdings.append(h.symbol)
                remaining_tax_adv -= h.market_value
            elif remaining_taxable >= h.market_value:
                taxable_holdings.append(h.symbol)
                remaining_taxable -= h.market_value
        
        # Then qualified can go in taxable
        for h in qualified_sorted:
            if remaining_taxable >= h.market_value:
                taxable_holdings.append(h.symbol)
                remaining_taxable -= h.market_value
            elif remaining_tax_adv >= h.market_value:
                tax_advantaged_holdings.append(h.symbol)
                remaining_tax_adv -= h.market_value
        
        return {
            "tax_advantaged_account": tax_advantaged_holdings,
            "taxable_account": taxable_holdings,
            "reasoning": "Non-qualified dividends prioritized for tax-advantaged accounts",
        }
