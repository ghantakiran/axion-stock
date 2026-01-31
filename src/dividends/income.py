"""Dividend Income Projections.

Project and analyze dividend income across portfolios.
"""

from datetime import date
from typing import Optional
import logging

from src.dividends.config import (
    DividendFrequency,
    FREQUENCY_MULTIPLIERS,
)
from src.dividends.models import (
    DividendHolding,
    DividendIncome,
    PortfolioIncome,
)

logger = logging.getLogger(__name__)


# Month names for reporting
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


class IncomeProjector:
    """Projects dividend income for holdings and portfolios.
    
    Calculates expected annual income, monthly breakdowns,
    and various yield metrics.
    
    Example:
        projector = IncomeProjector()
        
        holdings = [
            DividendHolding(symbol="AAPL", shares=100, annual_dividend=0.96, ...),
            DividendHolding(symbol="MSFT", shares=50, annual_dividend=3.00, ...),
        ]
        
        portfolio_income = projector.project_portfolio(holdings)
        print(f"Annual income: ${portfolio_income.annual_income:,.2f}")
    """
    
    def __init__(self):
        pass
    
    def project_holding(
        self,
        holding: DividendHolding,
    ) -> DividendIncome:
        """Project dividend income for a single holding.
        
        Args:
            holding: Dividend holding.
            
        Returns:
            DividendIncome projection.
        """
        income = DividendIncome(
            symbol=holding.symbol,
            shares=holding.shares,
            annual_dividend_per_share=holding.annual_dividend,
            annual_income=holding.annual_income,
            current_yield=holding.current_yield,
            yield_on_cost=holding.yield_on_cost,
        )
        
        # Calculate monthly breakdown based on frequency
        monthly = self._calculate_monthly_breakdown(
            annual_income=holding.annual_income,
            frequency=holding.frequency,
        )
        income.monthly_income = monthly
        
        # Forward yield (same as current for now)
        income.forward_yield = holding.current_yield
        
        return income
    
    def project_portfolio(
        self,
        holdings: list[DividendHolding],
    ) -> PortfolioIncome:
        """Project dividend income for entire portfolio.
        
        Args:
            holdings: List of dividend holdings.
            
        Returns:
            PortfolioIncome with totals and breakdowns.
        """
        portfolio = PortfolioIncome()
        
        # Calculate totals
        total_value = 0.0
        total_cost = 0.0
        annual_income = 0.0
        monthly_totals = [0.0] * 12
        
        for holding in holdings:
            # Skip if no dividend
            if holding.annual_dividend <= 0:
                continue
            
            # Project this holding
            projection = self.project_holding(holding)
            
            # Accumulate
            annual_income += projection.annual_income
            portfolio.income_by_symbol[holding.symbol] = projection.annual_income
            
            # Monthly breakdown
            for i, monthly in enumerate(projection.monthly_income):
                monthly_totals[i] += monthly
            
            total_value += holding.market_value
            total_cost += holding.cost_basis
        
        # Set portfolio totals
        portfolio.annual_income = annual_income
        portfolio.monthly_average = annual_income / 12
        portfolio.total_value = total_value
        portfolio.total_cost_basis = total_cost
        
        # Monthly projections with names
        portfolio.monthly_projections = {
            MONTH_NAMES[i]: monthly_totals[i]
            for i in range(12)
        }
        
        # Portfolio yields
        if total_value > 0:
            portfolio.portfolio_yield = annual_income / total_value
        
        if total_cost > 0:
            portfolio.weighted_yield_on_cost = annual_income / total_cost
        
        return portfolio
    
    def _calculate_monthly_breakdown(
        self,
        annual_income: float,
        frequency: DividendFrequency,
        payment_months: Optional[list[int]] = None,
    ) -> list[float]:
        """Calculate monthly dividend breakdown.
        
        Args:
            annual_income: Total annual income.
            frequency: Payment frequency.
            payment_months: Specific payment months (1-12).
            
        Returns:
            List of 12 monthly amounts.
        """
        monthly = [0.0] * 12
        
        if frequency == DividendFrequency.MONTHLY:
            # Equal distribution
            monthly_amount = annual_income / 12
            monthly = [monthly_amount] * 12
        
        elif frequency == DividendFrequency.QUARTERLY:
            # Default to Mar, Jun, Sep, Dec
            payment_months = payment_months or [3, 6, 9, 12]
            quarterly_amount = annual_income / 4
            for month in payment_months:
                monthly[month - 1] = quarterly_amount
        
        elif frequency == DividendFrequency.SEMI_ANNUAL:
            # Default to Jun, Dec
            payment_months = payment_months or [6, 12]
            semi_amount = annual_income / 2
            for month in payment_months:
                monthly[month - 1] = semi_amount
        
        elif frequency == DividendFrequency.ANNUAL:
            # Default to December
            payment_months = payment_months or [12]
            monthly[payment_months[0] - 1] = annual_income
        
        else:
            # Irregular - spread evenly
            monthly = [annual_income / 12] * 12
        
        return monthly
    
    def project_future_income(
        self,
        holdings: list[DividendHolding],
        years: int = 5,
        growth_rate: float = 0.05,
    ) -> list[PortfolioIncome]:
        """Project future income with dividend growth.
        
        Args:
            holdings: Current holdings.
            years: Years to project.
            growth_rate: Annual dividend growth rate.
            
        Returns:
            List of PortfolioIncome for each year.
        """
        projections = []
        
        # Make copies to modify
        current_holdings = [
            DividendHolding(
                symbol=h.symbol,
                company_name=h.company_name,
                shares=h.shares,
                cost_basis=h.cost_basis,
                current_price=h.current_price,
                sector=h.sector,
                annual_dividend=h.annual_dividend,
                frequency=h.frequency,
            )
            for h in holdings
        ]
        
        for year in range(years):
            # Project current year
            projection = self.project_portfolio(current_holdings)
            projections.append(projection)
            
            # Grow dividends for next year
            for h in current_holdings:
                h.annual_dividend *= (1 + growth_rate)
        
        return projections
    
    def calculate_income_by_sector(
        self,
        holdings: list[DividendHolding],
    ) -> dict[str, float]:
        """Calculate income breakdown by sector.
        
        Returns:
            Dict of sector -> annual income.
        """
        by_sector = {}
        
        for holding in holdings:
            sector = holding.sector or "Unknown"
            income = holding.annual_income
            by_sector[sector] = by_sector.get(sector, 0) + income
        
        return by_sector
    
    def calculate_income_by_frequency(
        self,
        holdings: list[DividendHolding],
    ) -> dict[str, float]:
        """Calculate income breakdown by payment frequency.
        
        Returns:
            Dict of frequency -> annual income.
        """
        by_freq = {}
        
        for holding in holdings:
            freq = holding.frequency.value
            income = holding.annual_income
            by_freq[freq] = by_freq.get(freq, 0) + income
        
        return by_freq
    
    def identify_income_gaps(
        self,
        portfolio_income: PortfolioIncome,
    ) -> list[str]:
        """Identify months with below-average income.
        
        Returns:
            List of month names with low income.
        """
        if not portfolio_income.monthly_projections:
            return []
        
        avg = portfolio_income.monthly_average
        threshold = avg * 0.5  # Below 50% of average
        
        low_months = []
        for month, amount in portfolio_income.monthly_projections.items():
            if amount < threshold:
                low_months.append(month)
        
        return low_months
