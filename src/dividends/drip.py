"""DRIP Simulation.

Simulate dividend reinvestment plan (DRIP) growth over time.
"""

from typing import Optional
import logging

from src.dividends.config import DRIPConfig, DEFAULT_DRIP_CONFIG
from src.dividends.models import DRIPSimulation, DRIPYear

logger = logging.getLogger(__name__)


class DRIPSimulator:
    """Simulates dividend reinvestment growth.
    
    Models how dividends reinvested over time can compound
    to grow both shares owned and income generated.
    
    Example:
        simulator = DRIPSimulator()
        
        result = simulator.simulate(
            symbol="KO",
            initial_shares=100,
            initial_price=60.0,
            initial_dividend=1.84,
            years=20,
        )
        
        print(f"Final shares: {result.final_shares:.2f}")
        print(f"Final value: ${result.final_value:,.2f}")
        print(f"Final income: ${result.final_annual_income:,.2f}/year")
    """
    
    def __init__(self, config: Optional[DRIPConfig] = None):
        self.config = config or DEFAULT_DRIP_CONFIG
    
    def simulate(
        self,
        symbol: str,
        initial_shares: float,
        initial_price: float,
        initial_dividend: float,  # Annual dividend per share
        years: Optional[int] = None,
        dividend_growth_rate: Optional[float] = None,
        price_growth_rate: Optional[float] = None,
        reinvest: bool = True,
    ) -> DRIPSimulation:
        """Run DRIP simulation.
        
        Args:
            symbol: Stock symbol.
            initial_shares: Starting share count.
            initial_price: Current share price.
            initial_dividend: Current annual dividend per share.
            years: Simulation period.
            dividend_growth_rate: Annual dividend growth rate.
            price_growth_rate: Annual price appreciation rate.
            reinvest: Whether to reinvest dividends.
            
        Returns:
            DRIPSimulation results.
        """
        years = years or self.config.years
        div_growth = dividend_growth_rate or self.config.dividend_growth_rate
        price_growth = price_growth_rate or self.config.price_growth_rate
        
        simulation = DRIPSimulation(
            symbol=symbol,
            initial_shares=initial_shares,
            initial_investment=initial_shares * initial_price,
            initial_price=initial_price,
            initial_dividend=initial_dividend,
            years=years,
            dividend_growth_rate=div_growth,
            price_growth_rate=price_growth,
        )
        
        # Track state
        shares = initial_shares
        price = initial_price
        dividend = initial_dividend
        
        total_dividends = 0.0
        total_drip_shares = 0.0
        
        yearly_projections = []
        
        for year in range(1, years + 1):
            # Start of year
            starting_shares = shares
            starting_value = shares * price
            
            # Calculate dividends received
            dividends_received = shares * dividend
            total_dividends += dividends_received
            
            # Reinvest if DRIP enabled
            shares_purchased = 0.0
            if reinvest and price > 0:
                shares_purchased = dividends_received / price
                shares += shares_purchased
                total_drip_shares += shares_purchased
            
            # Year-end values (after growth applied)
            ending_shares = shares
            ending_value = shares * price
            
            # Yield on original cost
            original_cost = simulation.initial_investment
            current_income = shares * dividend
            yoc = current_income / original_cost if original_cost > 0 else 0
            
            # Income growth vs year 1
            year_1_income = initial_shares * initial_dividend
            income_growth = (current_income - year_1_income) / year_1_income if year_1_income > 0 else 0
            
            # Record year
            drip_year = DRIPYear(
                year=year,
                starting_shares=starting_shares,
                starting_value=starting_value,
                dividend_per_share=dividend,
                dividends_received=dividends_received,
                share_price=price,
                shares_purchased=shares_purchased,
                ending_shares=ending_shares,
                ending_value=ending_value,
                yield_on_original_cost=yoc,
                income_growth_pct=income_growth,
            )
            yearly_projections.append(drip_year)
            
            # Apply growth for next year
            dividend *= (1 + div_growth)
            price *= (1 + price_growth)
        
        # Final results
        simulation.final_shares = shares
        simulation.final_value = shares * price
        simulation.final_annual_income = shares * dividend
        simulation.total_dividends_received = total_dividends
        simulation.total_shares_from_drip = total_drip_shares
        simulation.yearly_projections = yearly_projections
        
        # Calculate returns
        if simulation.initial_investment > 0:
            total_return = (simulation.final_value + total_dividends - simulation.initial_investment)
            simulation.total_return_pct = total_return / simulation.initial_investment
            
            # Annualized return
            ending_total = simulation.final_value
            if not reinvest:
                ending_total += total_dividends
            simulation.annualized_return = (ending_total / simulation.initial_investment) ** (1/years) - 1
        
        return simulation
    
    def compare_scenarios(
        self,
        symbol: str,
        initial_shares: float,
        initial_price: float,
        initial_dividend: float,
        years: int = 20,
    ) -> dict:
        """Compare DRIP vs no-DRIP scenarios.
        
        Returns:
            Dict comparing both scenarios.
        """
        # With DRIP
        with_drip = self.simulate(
            symbol=symbol,
            initial_shares=initial_shares,
            initial_price=initial_price,
            initial_dividend=initial_dividend,
            years=years,
            reinvest=True,
        )
        
        # Without DRIP
        without_drip = self.simulate(
            symbol=symbol,
            initial_shares=initial_shares,
            initial_price=initial_price,
            initial_dividend=initial_dividend,
            years=years,
            reinvest=False,
        )
        
        return {
            "with_drip": {
                "final_shares": with_drip.final_shares,
                "final_value": with_drip.final_value,
                "final_annual_income": with_drip.final_annual_income,
                "total_return": with_drip.total_return_pct,
            },
            "without_drip": {
                "final_shares": without_drip.final_shares,
                "final_value": without_drip.final_value,
                "total_dividends_received": without_drip.total_dividends_received,
                "total_value": without_drip.final_value + without_drip.total_dividends_received,
            },
            "drip_benefit": {
                "extra_shares": with_drip.final_shares - without_drip.final_shares,
                "extra_value": with_drip.final_value - without_drip.final_value,
                "extra_income": with_drip.final_annual_income - (without_drip.final_shares * initial_dividend * (1 + self.config.dividend_growth_rate) ** years),
            }
        }
    
    def calculate_doubling_time(
        self,
        dividend_growth_rate: float,
        current_yield: float,
    ) -> dict:
        """Calculate time for income to double with DRIP.
        
        Uses Rule of 72 approximation and more precise calculation.
        
        Returns:
            Dict with doubling estimates.
        """
        # Combined growth rate (dividend growth + yield from reinvestment)
        combined_rate = dividend_growth_rate + current_yield
        
        # Rule of 72
        rule_72_years = 72 / (combined_rate * 100) if combined_rate > 0 else float('inf')
        
        # More precise calculation
        if combined_rate > 0:
            precise_years = 0.693 / combined_rate  # ln(2) / rate
        else:
            precise_years = float('inf')
        
        return {
            "dividend_growth_rate": dividend_growth_rate,
            "current_yield": current_yield,
            "combined_growth_rate": combined_rate,
            "rule_72_years": rule_72_years,
            "precise_years": precise_years,
        }
    
    def sensitivity_analysis(
        self,
        symbol: str,
        initial_shares: float,
        initial_price: float,
        initial_dividend: float,
        years: int = 20,
        dividend_growth_range: tuple = (0.02, 0.05, 0.08),
        price_growth_range: tuple = (0.04, 0.07, 0.10),
    ) -> list[dict]:
        """Run sensitivity analysis on growth assumptions.
        
        Returns:
            List of scenario results.
        """
        results = []
        
        for div_growth in dividend_growth_range:
            for price_growth in price_growth_range:
                sim = self.simulate(
                    symbol=symbol,
                    initial_shares=initial_shares,
                    initial_price=initial_price,
                    initial_dividend=initial_dividend,
                    years=years,
                    dividend_growth_rate=div_growth,
                    price_growth_rate=price_growth,
                )
                
                results.append({
                    "dividend_growth": div_growth,
                    "price_growth": price_growth,
                    "final_value": sim.final_value,
                    "final_income": sim.final_annual_income,
                    "total_return": sim.total_return_pct,
                    "annualized_return": sim.annualized_return,
                })
        
        return results
