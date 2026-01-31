"""What-If Trade Analysis.

Simulate trade impacts before execution.
"""

from copy import deepcopy
from typing import Optional
import logging

from src.scenarios.config import (
    SimulationConfig,
    DEFAULT_SIMULATION_CONFIG,
    TradeAction,
    SizeMethod,
)
from src.scenarios.models import (
    Portfolio,
    Holding,
    ProposedTrade,
    TradeSimulation,
    RiskImpact,
    TaxImpact,
)

logger = logging.getLogger(__name__)


class WhatIfAnalyzer:
    """Analyzes what-if trade scenarios.
    
    Simulates trades to show portfolio impact before execution.
    
    Example:
        analyzer = WhatIfAnalyzer()
        
        trades = [
            ProposedTrade(symbol="AAPL", action=TradeAction.SELL, shares=50),
            ProposedTrade(symbol="MSFT", action=TradeAction.BUY, dollar_amount=5000),
        ]
        
        result = analyzer.simulate(portfolio, trades)
        print(f"New value: ${result.resulting_portfolio.total_value:,.2f}")
    """
    
    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or DEFAULT_SIMULATION_CONFIG
    
    def simulate(
        self,
        portfolio: Portfolio,
        trades: list[ProposedTrade],
        prices: Optional[dict[str, float]] = None,
    ) -> TradeSimulation:
        """Simulate trades on a portfolio.
        
        Args:
            portfolio: Current portfolio.
            trades: List of proposed trades.
            prices: Current prices (symbol -> price).
            
        Returns:
            TradeSimulation with results.
        """
        prices = prices or {}
        
        # Create simulation result
        simulation = TradeSimulation(
            base_portfolio=portfolio,
            trades=trades,
        )
        
        # Deep copy portfolio for modification
        result_portfolio = deepcopy(portfolio)
        result_portfolio.portfolio_id = f"{portfolio.portfolio_id}_sim"
        result_portfolio.name = f"{portfolio.name} (Simulated)"
        
        total_commission = 0.0
        total_slippage = 0.0
        weight_changes = {}
        
        # Process each trade
        for trade in trades:
            # Get price
            price = trade.assumed_price or prices.get(trade.symbol, 0)
            if price == 0:
                # Try to get from existing holding
                holding = result_portfolio.get_holding(trade.symbol)
                if holding:
                    price = holding.current_price
                else:
                    price = 100.0  # Default
            
            trade.assumed_price = price
            
            # Calculate trade size
            self._calculate_trade_size(trade, result_portfolio, price)
            
            # Execute trade on portfolio copy
            self._execute_trade(trade, result_portfolio, price)
            
            # Calculate costs
            trade_value = abs(trade.calculated_value)
            commission = self.config.commission_per_trade
            slippage = trade_value * self.config.slippage_bps / 10000
            
            total_commission += commission
            total_slippage += slippage
            
            # Track weight changes
            old_weight = portfolio.get_weight(trade.symbol)
            new_weight = result_portfolio.get_weight(trade.symbol)
            weight_changes[trade.symbol] = new_weight - old_weight
        
        # Calculate impacts
        risk_impact = self._calculate_risk_impact(portfolio, result_portfolio)
        tax_impact = self._calculate_tax_impact(portfolio, trades)
        
        # Populate simulation result
        simulation.resulting_portfolio = result_portfolio
        simulation.value_change = result_portfolio.total_value - portfolio.total_value
        simulation.weight_changes = weight_changes
        simulation.risk_impact = risk_impact
        simulation.tax_impact = tax_impact
        simulation.estimated_commission = total_commission
        simulation.estimated_slippage = total_slippage
        simulation.total_cost = total_commission + total_slippage
        
        return simulation
    
    def _calculate_trade_size(
        self,
        trade: ProposedTrade,
        portfolio: Portfolio,
        price: float,
    ) -> None:
        """Calculate actual trade size based on sizing method."""
        method = trade.get_size_method()
        
        if method == SizeMethod.SHARES:
            trade.calculated_shares = trade.shares or 0
            trade.calculated_value = trade.calculated_shares * price
        
        elif method == SizeMethod.DOLLARS:
            trade.calculated_value = trade.dollar_amount or 0
            trade.calculated_shares = trade.calculated_value / price if price > 0 else 0
        
        elif method == SizeMethod.WEIGHT:
            target_value = portfolio.total_value * (trade.target_weight or 0)
            current_value = 0
            holding = portfolio.get_holding(trade.symbol)
            if holding:
                current_value = holding.market_value
            
            trade.calculated_value = abs(target_value - current_value)
            trade.calculated_shares = trade.calculated_value / price if price > 0 else 0
            
            # Adjust action based on target
            if target_value > current_value:
                trade.action = TradeAction.BUY
            elif target_value < current_value:
                trade.action = TradeAction.SELL
        
        elif method == SizeMethod.PERCENT_OF_POSITION:
            holding = portfolio.get_holding(trade.symbol)
            if holding:
                trade.calculated_shares = holding.shares * (trade.percent_of_position or 0)
                trade.calculated_value = trade.calculated_shares * price
            else:
                trade.calculated_shares = 0
                trade.calculated_value = 0
    
    def _execute_trade(
        self,
        trade: ProposedTrade,
        portfolio: Portfolio,
        price: float,
    ) -> None:
        """Execute a trade on portfolio (in place modification)."""
        holding = portfolio.get_holding(trade.symbol)
        
        if trade.action == TradeAction.BUY:
            if holding:
                # Add to existing position
                total_cost = holding.cost_basis + trade.calculated_value
                holding.shares += trade.calculated_shares
                holding.cost_basis = total_cost
                holding.current_price = price
            else:
                # New position
                new_holding = Holding(
                    symbol=trade.symbol,
                    shares=trade.calculated_shares,
                    cost_basis=trade.calculated_value,
                    current_price=price,
                )
                portfolio.holdings.append(new_holding)
            
            # Reduce cash
            portfolio.cash -= trade.calculated_value
        
        elif trade.action == TradeAction.SELL:
            if holding:
                # Reduce position
                sell_ratio = trade.calculated_shares / holding.shares if holding.shares > 0 else 0
                holding.cost_basis *= (1 - sell_ratio)
                holding.shares -= trade.calculated_shares
                holding.current_price = price
                
                # Remove if zero
                if holding.shares <= 0:
                    portfolio.holdings.remove(holding)
                
                # Add cash
                portfolio.cash += trade.calculated_value
        
        elif trade.action == TradeAction.SELL_ALL:
            if holding:
                # Sell entire position
                trade.calculated_shares = holding.shares
                trade.calculated_value = holding.market_value
                portfolio.cash += holding.market_value
                portfolio.holdings.remove(holding)
    
    def _calculate_risk_impact(
        self,
        old_portfolio: Portfolio,
        new_portfolio: Portfolio,
    ) -> RiskImpact:
        """Calculate risk impact of changes."""
        from src.scenarios.config import SECTOR_BETAS
        
        # Calculate portfolio betas
        def calc_beta(p: Portfolio) -> float:
            if p.total_value == 0:
                return 1.0
            weighted_beta = 0.0
            for h in p.holdings:
                weight = h.market_value / p.total_value
                beta = SECTOR_BETAS.get(h.sector, 1.0)
                weighted_beta += weight * beta
            return weighted_beta
        
        old_beta = calc_beta(old_portfolio)
        new_beta = calc_beta(new_portfolio)
        
        # Calculate concentration (HHI)
        def calc_hhi(p: Portfolio) -> float:
            if p.total_value == 0:
                return 0
            return sum((h.market_value / p.total_value) ** 2 for h in p.holdings)
        
        old_hhi = calc_hhi(old_portfolio)
        new_hhi = calc_hhi(new_portfolio)
        
        # Sector exposure changes
        old_sectors = {}
        new_sectors = {}
        
        for h in old_portfolio.holdings:
            if old_portfolio.total_value > 0:
                old_sectors[h.sector] = old_sectors.get(h.sector, 0) + h.market_value / old_portfolio.total_value
        
        for h in new_portfolio.holdings:
            if new_portfolio.total_value > 0:
                new_sectors[h.sector] = new_sectors.get(h.sector, 0) + h.market_value / new_portfolio.total_value
        
        all_sectors = set(old_sectors.keys()) | set(new_sectors.keys())
        sector_changes = {
            s: new_sectors.get(s, 0) - old_sectors.get(s, 0)
            for s in all_sectors
        }
        
        return RiskImpact(
            beta_change=new_beta - old_beta,
            concentration_change=new_hhi - old_hhi,
            sector_exposure_changes=sector_changes,
        )
    
    def _calculate_tax_impact(
        self,
        portfolio: Portfolio,
        trades: list[ProposedTrade],
    ) -> TaxImpact:
        """Calculate tax impact of trades."""
        short_term_gains = 0.0
        long_term_gains = 0.0
        short_term_losses = 0.0
        long_term_losses = 0.0
        
        for trade in trades:
            if trade.action in (TradeAction.SELL, TradeAction.SELL_ALL):
                holding = portfolio.get_holding(trade.symbol)
                if holding and holding.shares > 0:
                    # Calculate gain/loss
                    avg_cost = holding.cost_basis / holding.shares
                    sell_shares = trade.calculated_shares
                    sell_value = trade.calculated_value
                    cost_basis = avg_cost * sell_shares
                    gain = sell_value - cost_basis
                    
                    # Assume long-term for simplicity (>1 year)
                    # In production, would track holding periods
                    if gain > 0:
                        long_term_gains += gain
                    else:
                        long_term_losses += abs(gain)
        
        # Estimate tax
        estimated_tax = (
            short_term_gains * self.config.short_term_rate +
            long_term_gains * self.config.long_term_rate -
            min(short_term_losses + long_term_losses, 3000) * self.config.short_term_rate
        )
        
        return TaxImpact(
            short_term_gains=short_term_gains,
            long_term_gains=long_term_gains,
            short_term_losses=short_term_losses,
            long_term_losses=long_term_losses,
            estimated_tax=max(0, estimated_tax),
        )
    
    def quick_buy(
        self,
        portfolio: Portfolio,
        symbol: str,
        amount: float,
        price: float,
    ) -> TradeSimulation:
        """Quick what-if for buying a stock."""
        trade = ProposedTrade(
            symbol=symbol,
            action=TradeAction.BUY,
            dollar_amount=amount,
            assumed_price=price,
        )
        return self.simulate(portfolio, [trade])
    
    def quick_sell(
        self,
        portfolio: Portfolio,
        symbol: str,
        shares: Optional[float] = None,
        sell_all: bool = False,
    ) -> TradeSimulation:
        """Quick what-if for selling a stock."""
        if sell_all:
            trade = ProposedTrade(symbol=symbol, action=TradeAction.SELL_ALL)
        else:
            trade = ProposedTrade(
                symbol=symbol,
                action=TradeAction.SELL,
                shares=shares or 0,
            )
        return self.simulate(portfolio, [trade])
