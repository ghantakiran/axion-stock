"""Tax-Loss Harvesting Engine.

Identifies and manages tax-loss harvesting opportunities while
avoiding wash sales and maintaining portfolio exposure.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional, Callable
import logging

from src.tax.config import (
    HarvestingConfig,
    HoldingPeriod,
    TaxConfig,
    DEFAULT_TAX_CONFIG,
    FEDERAL_BRACKETS_2024,
    LTCG_BRACKETS_2024,
    FilingStatus,
)
from src.tax.models import TaxLot, HarvestOpportunity, HarvestResult
from src.tax.lots import TaxLotManager
from src.tax.wash_sales import WashSaleTracker, Transaction

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Simplified position for harvesting analysis."""
    symbol: str
    shares: float
    current_price: float
    sector: str = ""
    
    @property
    def market_value(self) -> float:
        return self.shares * self.current_price


# Common ETF substitutes for tax-loss harvesting
ETF_SUBSTITUTES: dict[str, list[str]] = {
    # S&P 500
    "SPY": ["IVV", "VOO", "SPLG"],
    "IVV": ["SPY", "VOO", "SPLG"],
    "VOO": ["SPY", "IVV", "SPLG"],
    # Total Market
    "VTI": ["ITOT", "SPTM", "SCHB"],
    "ITOT": ["VTI", "SPTM", "SCHB"],
    # Nasdaq
    "QQQ": ["QQQM", "ONEQ"],
    "QQQM": ["QQQ", "ONEQ"],
    # Small Cap
    "IWM": ["IJR", "VB", "SCHA"],
    "IJR": ["IWM", "VB", "SCHA"],
    # International
    "VEA": ["IEFA", "SCHF", "EFA"],
    "IEFA": ["VEA", "SCHF", "EFA"],
    "EFA": ["VEA", "IEFA", "SCHF"],
    # Emerging Markets
    "VWO": ["IEMG", "EEM", "SCHE"],
    "EEM": ["VWO", "IEMG", "SCHE"],
    # Bonds
    "BND": ["AGG", "SCHZ"],
    "AGG": ["BND", "SCHZ"],
}


class TaxLossHarvester:
    """Identifies and executes tax-loss harvesting opportunities.
    
    Tax-loss harvesting involves selling positions at a loss to offset
    gains, while potentially buying substitute securities to maintain
    market exposure.
    
    Key features:
    - Identifies positions with harvestable losses
    - Calculates estimated tax savings
    - Suggests substitute securities
    - Tracks wash sale windows
    - Manages repurchase timing
    """
    
    def __init__(
        self,
        lot_manager: TaxLotManager,
        wash_sale_tracker: WashSaleTracker,
        config: Optional[TaxConfig] = None,
    ):
        self.lot_manager = lot_manager
        self.wash_sale_tracker = wash_sale_tracker
        self.config = config or DEFAULT_TAX_CONFIG
        self._harvest_config = self.config.harvesting
        self._harvests: list[HarvestResult] = []
        self._ytd_harvested: float = 0.0
    
    def find_opportunities(
        self,
        positions: list[Position],
        prices: Optional[dict[str, float]] = None,
    ) -> list[HarvestOpportunity]:
        """Find tax-loss harvesting opportunities.
        
        Args:
            positions: Current portfolio positions.
            prices: Current prices (if not in positions).
            
        Returns:
            List of harvesting opportunities sorted by potential savings.
        """
        opportunities: list[HarvestOpportunity] = []
        
        for pos in positions:
            price = prices.get(pos.symbol, pos.current_price) if prices else pos.current_price
            
            # Get lots for this position
            lots = self.lot_manager.get_lots(pos.symbol)
            
            for lot in lots:
                if lot.remaining_shares <= 0:
                    continue
                
                # Calculate unrealized gain/loss
                ratio = lot.remaining_shares / lot.shares
                basis = lot.adjusted_basis * ratio
                value = lot.remaining_shares * price
                unrealized = value - basis
                
                # Only interested in losses
                if unrealized >= 0:
                    continue
                
                # Check minimum loss threshold
                if abs(unrealized) < self._harvest_config.min_loss_threshold:
                    continue
                
                # Check holding period requirement
                if lot.days_held < self._harvest_config.min_holding_days:
                    continue
                
                # Check wash sale risk
                wash_risk = self.wash_sale_tracker.is_symbol_in_wash_window(pos.symbol)
                
                # Calculate estimated tax savings
                tax_savings = self._estimate_tax_savings(
                    unrealized, lot.holding_period
                )
                
                # Find substitute securities
                substitutes = self._find_substitutes(pos.symbol)
                
                opp = HarvestOpportunity(
                    symbol=pos.symbol,
                    lot_id=lot.lot_id,
                    shares=lot.remaining_shares,
                    current_value=value,
                    cost_basis=basis,
                    unrealized_loss=unrealized,
                    holding_period=lot.holding_period,
                    days_held=lot.days_held,
                    estimated_tax_savings=tax_savings,
                    wash_sale_risk=wash_risk,
                    last_purchase_date=lot.acquisition_date,
                    substitute_symbols=substitutes,
                )
                opportunities.append(opp)
        
        # Sort by estimated tax savings (highest first)
        opportunities.sort(key=lambda x: x.estimated_tax_savings, reverse=True)
        
        return opportunities
    
    def _estimate_tax_savings(
        self,
        loss: float,
        holding_period: HoldingPeriod,
    ) -> float:
        """Estimate tax savings from realizing a loss.
        
        Short-term losses offset short-term gains (taxed at ordinary rates).
        Long-term losses offset long-term gains (lower rates).
        Losses can also offset up to $3,000 of ordinary income.
        """
        profile = self.config.tax_profile
        
        # Get marginal tax rate
        if holding_period == HoldingPeriod.SHORT_TERM:
            # Short-term losses save at ordinary income rate
            brackets = FEDERAL_BRACKETS_2024[profile.filing_status]
            marginal_rate = self._get_marginal_rate(
                profile.estimated_ordinary_income, brackets
            )
        else:
            # Long-term losses save at LTCG rate
            brackets = LTCG_BRACKETS_2024[profile.filing_status]
            marginal_rate = self._get_marginal_rate(
                profile.estimated_ordinary_income, brackets
            )
        
        # Add state tax
        marginal_rate += profile.state_rate
        
        # Tax savings = loss * marginal rate
        return abs(loss) * marginal_rate
    
    def _get_marginal_rate(
        self,
        income: float,
        brackets: list[tuple[float, float]],
    ) -> float:
        """Get marginal tax rate for income level."""
        for threshold, rate in brackets:
            if income <= threshold:
                return rate
        return brackets[-1][1]  # Top rate
    
    def _find_substitutes(self, symbol: str) -> list[str]:
        """Find substitute securities for maintaining exposure."""
        # Check predefined ETF substitutes
        if symbol in ETF_SUBSTITUTES:
            return ETF_SUBSTITUTES[symbol][:3]  # Top 3
        
        # For individual stocks, could use sector ETFs
        # This would need sector data integration
        return []
    
    def execute_harvest(
        self,
        opportunity: HarvestOpportunity,
        execute_trade: Optional[Callable[[str, float, str], float]] = None,
        buy_substitute: bool = True,
    ) -> HarvestResult:
        """Execute a tax-loss harvest.
        
        Args:
            opportunity: The harvesting opportunity.
            execute_trade: Optional callback to execute actual trades.
                          Takes (symbol, shares, side) returns proceeds.
            buy_substitute: Whether to buy a substitute security.
            
        Returns:
            HarvestResult with details of the harvest.
        """
        # Check daily/annual limits
        daily_harvests = len([h for h in self._harvests if h.harvest_date == date.today()])
        if daily_harvests >= self._harvest_config.max_daily_harvests:
            logger.warning("Daily harvest limit reached")
            return HarvestResult(status="limit_reached")
        
        if (self._harvest_config.annual_harvest_limit > 0 and
            self._ytd_harvested >= self._harvest_config.annual_harvest_limit):
            logger.warning("Annual harvest limit reached")
            return HarvestResult(status="limit_reached")
        
        # Execute the sale
        proceeds = opportunity.current_value
        if execute_trade:
            proceeds = execute_trade(opportunity.symbol, opportunity.shares, "sell")
        
        # Record the sale with lot manager
        realized_gains = self.lot_manager.execute_sale(
            symbol=opportunity.symbol,
            shares=opportunity.shares,
            proceeds=proceeds,
            sale_date=date.today(),
            target_lot_ids=[opportunity.lot_id],
        )
        
        # Record transaction for wash sale tracking
        self.wash_sale_tracker.add_transaction(Transaction(
            symbol=opportunity.symbol,
            shares=opportunity.shares,
            date=date.today(),
            is_purchase=False,
            price=proceeds / opportunity.shares if opportunity.shares > 0 else 0,
        ))
        
        # Calculate repurchase date
        repurchase_date = date.today() + timedelta(days=31)
        
        # Buy substitute if requested
        replacement_symbol = None
        replacement_shares = 0.0
        if buy_substitute and opportunity.substitute_symbols:
            replacement_symbol = opportunity.substitute_symbols[0]
            # Would execute buy trade here
            if execute_trade:
                replacement_shares = opportunity.shares  # Same number of shares
                execute_trade(replacement_symbol, replacement_shares, "buy")
        
        # Create harvest result
        result = HarvestResult(
            account_id=self.lot_manager.get_lot(opportunity.lot_id).account_id,
            symbol=opportunity.symbol,
            shares=opportunity.shares,
            proceeds=proceeds,
            loss_realized=opportunity.unrealized_loss,
            tax_savings=opportunity.estimated_tax_savings,
            replacement_symbol=replacement_symbol,
            replacement_shares=replacement_shares,
            harvest_date=date.today(),
            repurchase_eligible_date=repurchase_date,
            status="completed",
        )
        
        self._harvests.append(result)
        self._ytd_harvested += abs(opportunity.unrealized_loss)
        
        logger.info(
            f"Harvested ${abs(opportunity.unrealized_loss):.2f} loss from "
            f"{opportunity.shares} shares of {opportunity.symbol}"
        )
        
        return result
    
    def get_harvest_summary(self, year: Optional[int] = None) -> dict:
        """Get summary of harvesting activity."""
        year = year or date.today().year
        
        harvests = [h for h in self._harvests if h.harvest_date.year == year]
        
        return {
            "year": year,
            "total_harvests": len(harvests),
            "total_losses_harvested": sum(abs(h.loss_realized) for h in harvests),
            "total_tax_savings": sum(h.tax_savings for h in harvests),
            "symbols_harvested": list(set(h.symbol for h in harvests)),
            "pending_repurchases": [
                {
                    "symbol": h.symbol,
                    "eligible_date": h.repurchase_eligible_date.isoformat(),
                }
                for h in harvests
                if h.repurchase_eligible_date > date.today()
            ],
        }
    
    def get_repurchase_calendar(self) -> list[dict]:
        """Get calendar of when symbols become eligible for repurchase."""
        calendar = []
        
        for harvest in self._harvests:
            if harvest.repurchase_eligible_date > date.today():
                calendar.append({
                    "symbol": harvest.symbol,
                    "eligible_date": harvest.repurchase_eligible_date,
                    "shares": harvest.shares,
                    "original_loss": harvest.loss_realized,
                })
        
        return sorted(calendar, key=lambda x: x["eligible_date"])
    
    def should_harvest_before_year_end(
        self,
        positions: list[Position],
        realized_gains_ytd: float,
    ) -> list[HarvestOpportunity]:
        """Find opportunities to harvest before year end to offset gains.
        
        Useful in December to identify last-minute harvesting opportunities.
        """
        opportunities = self.find_opportunities(positions)
        
        # Filter to those without wash sale risk and with sufficient savings
        priority = []
        remaining_gains = realized_gains_ytd
        
        for opp in opportunities:
            if opp.wash_sale_risk:
                continue
            
            # Prioritize if we have gains to offset
            if remaining_gains > 0:
                offset_amount = min(abs(opp.unrealized_loss), remaining_gains)
                opp.estimated_tax_savings = self._estimate_tax_savings(
                    -offset_amount, opp.holding_period
                )
                remaining_gains -= offset_amount
            
            priority.append(opp)
        
        return priority
