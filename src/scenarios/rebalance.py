"""Rebalancing Simulation.

Simulate portfolio rebalancing strategies.
"""

from copy import deepcopy
from typing import Optional
import logging

from src.scenarios.config import (
    SimulationConfig,
    DEFAULT_SIMULATION_CONFIG,
    RebalanceStrategy,
    TradeAction,
    MIN_TRADE_SIZE,
)
from src.scenarios.models import (
    Portfolio,
    Holding,
    ProposedTrade,
    TargetAllocation,
    RebalanceSimulation,
    TaxImpact,
)
from src.scenarios.what_if import WhatIfAnalyzer

logger = logging.getLogger(__name__)


class RebalanceSimulator:
    """Simulates portfolio rebalancing.
    
    Supports multiple rebalancing strategies and calculates
    required trades to achieve target allocation.
    
    Example:
        simulator = RebalanceSimulator()
        
        target = TargetAllocation(
            targets={"AAPL": 0.30, "MSFT": 0.30, "GOOGL": 0.40}
        )
        
        result = simulator.simulate(portfolio, target)
        print(f"Trades needed: {len(result.required_trades)}")
    """
    
    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or DEFAULT_SIMULATION_CONFIG
        self._what_if = WhatIfAnalyzer(config)
    
    def simulate(
        self,
        portfolio: Portfolio,
        target: TargetAllocation,
        strategy: RebalanceStrategy = RebalanceStrategy.TARGET_WEIGHT,
        threshold_pct: float = 5.0,
        prices: Optional[dict[str, float]] = None,
    ) -> RebalanceSimulation:
        """Simulate a rebalance.
        
        Args:
            portfolio: Current portfolio.
            target: Target allocation.
            strategy: Rebalancing strategy.
            threshold_pct: Drift threshold for threshold strategy.
            prices: Current prices.
            
        Returns:
            RebalanceSimulation with required trades.
        """
        prices = prices or {}
        
        # Calculate current drift
        current_drift = self._calculate_drift(portfolio, target)
        
        # Determine if rebalance is needed
        needs_rebalance = self._needs_rebalance(
            current_drift, strategy, threshold_pct
        )
        
        simulation = RebalanceSimulation(
            current_portfolio=portfolio,
            target_allocation=target,
            strategy=strategy,
            threshold_pct=threshold_pct,
            current_drift=current_drift,
        )
        
        if not needs_rebalance and strategy == RebalanceStrategy.THRESHOLD:
            # No rebalance needed
            simulation.post_rebalance_drift = current_drift
            return simulation
        
        # Generate trades based on strategy
        if strategy == RebalanceStrategy.TAX_AWARE:
            trades = self._generate_tax_aware_trades(portfolio, target, prices)
        else:
            trades = self._generate_trades(portfolio, target, prices)
        
        simulation.required_trades = trades
        
        # Simulate the trades
        if trades:
            trade_sim = self._what_if.simulate(portfolio, trades, prices)
            simulation.resulting_portfolio = trade_sim.resulting_portfolio
            simulation.estimated_costs = trade_sim.total_cost
            simulation.tax_impact = trade_sim.tax_impact
            
            # Calculate post-rebalance drift
            if simulation.resulting_portfolio:
                simulation.post_rebalance_drift = self._calculate_drift(
                    simulation.resulting_portfolio, target
                )
        else:
            simulation.resulting_portfolio = deepcopy(portfolio)
            simulation.post_rebalance_drift = current_drift
        
        return simulation
    
    def _calculate_drift(
        self,
        portfolio: Portfolio,
        target: TargetAllocation,
    ) -> dict[str, float]:
        """Calculate drift from target allocation."""
        drift = {}
        current_weights = portfolio.get_weights()
        
        # Check all target symbols
        for symbol, target_weight in target.targets.items():
            current_weight = current_weights.get(symbol, 0.0)
            drift[symbol] = current_weight - target_weight
        
        # Check for symbols in portfolio not in target
        for symbol in current_weights:
            if symbol not in target.targets:
                drift[symbol] = current_weights[symbol]  # Should be 0
        
        return drift
    
    def _needs_rebalance(
        self,
        drift: dict[str, float],
        strategy: RebalanceStrategy,
        threshold_pct: float,
    ) -> bool:
        """Check if rebalance is needed."""
        if strategy == RebalanceStrategy.THRESHOLD:
            max_drift = max(abs(d) for d in drift.values()) if drift else 0
            return max_drift > (threshold_pct / 100)
        
        # Other strategies always rebalance when called
        return True
    
    def _generate_trades(
        self,
        portfolio: Portfolio,
        target: TargetAllocation,
        prices: dict[str, float],
    ) -> list[ProposedTrade]:
        """Generate trades to achieve target allocation."""
        trades = []
        total_value = portfolio.total_value
        current_weights = portfolio.get_weights()
        
        # First pass: calculate sells (to free up cash)
        sells = []
        buys = []
        
        for symbol, target_weight in target.targets.items():
            current_weight = current_weights.get(symbol, 0.0)
            diff = target_weight - current_weight
            trade_value = abs(diff) * total_value
            
            # Skip small trades
            if trade_value < self.config.min_trade_size:
                continue
            
            price = prices.get(symbol, 100.0)
            holding = portfolio.get_holding(symbol)
            if holding:
                price = holding.current_price
            
            if diff < 0:
                # Need to sell
                sells.append(ProposedTrade(
                    symbol=symbol,
                    action=TradeAction.SELL,
                    dollar_amount=trade_value,
                    assumed_price=price,
                ))
            elif diff > 0:
                # Need to buy
                buys.append(ProposedTrade(
                    symbol=symbol,
                    action=TradeAction.BUY,
                    dollar_amount=trade_value,
                    assumed_price=price,
                ))
        
        # Handle positions not in target (sell all)
        for symbol, weight in current_weights.items():
            if symbol not in target.targets and weight > 0:
                sells.append(ProposedTrade(
                    symbol=symbol,
                    action=TradeAction.SELL_ALL,
                ))
        
        # Order: sells first, then buys
        trades = sells + buys
        return trades
    
    def _generate_tax_aware_trades(
        self,
        portfolio: Portfolio,
        target: TargetAllocation,
        prices: dict[str, float],
    ) -> list[ProposedTrade]:
        """Generate tax-efficient rebalancing trades.
        
        Prioritizes:
        1. Selling losing positions
        2. Buying new positions
        3. Selling winning positions only if necessary
        """
        trades = []
        total_value = portfolio.total_value
        current_weights = portfolio.get_weights()
        
        sells_with_loss = []
        sells_with_gain = []
        buys = []
        
        for symbol, target_weight in target.targets.items():
            current_weight = current_weights.get(symbol, 0.0)
            diff = target_weight - current_weight
            trade_value = abs(diff) * total_value
            
            if trade_value < self.config.min_trade_size:
                continue
            
            holding = portfolio.get_holding(symbol)
            price = prices.get(symbol, holding.current_price if holding else 100.0)
            
            if diff < 0 and holding:
                # Need to sell - check if gain or loss
                trade = ProposedTrade(
                    symbol=symbol,
                    action=TradeAction.SELL,
                    dollar_amount=trade_value,
                    assumed_price=price,
                )
                
                if holding.unrealized_gain < 0:
                    sells_with_loss.append(trade)
                else:
                    sells_with_gain.append(trade)
            
            elif diff > 0:
                buys.append(ProposedTrade(
                    symbol=symbol,
                    action=TradeAction.BUY,
                    dollar_amount=trade_value,
                    assumed_price=price,
                ))
        
        # Tax-aware order: sell losses first, then buys, then sell gains
        trades = sells_with_loss + buys + sells_with_gain
        return trades
    
    def calculate_rebalance_frequency(
        self,
        portfolio: Portfolio,
        target: TargetAllocation,
        historical_drift: list[dict[str, float]],
    ) -> dict:
        """Analyze optimal rebalancing frequency.
        
        Args:
            portfolio: Current portfolio.
            target: Target allocation.
            historical_drift: Historical drift measurements.
            
        Returns:
            Analysis of rebalancing frequency.
        """
        if not historical_drift:
            return {"recommended_frequency": "monthly"}
        
        # Calculate how often drift exceeded thresholds
        thresholds = [0.03, 0.05, 0.10]  # 3%, 5%, 10%
        threshold_breaches = {t: 0 for t in thresholds}
        
        for drift in historical_drift:
            max_drift = max(abs(d) for d in drift.values())
            for t in thresholds:
                if max_drift > t:
                    threshold_breaches[t] += 1
        
        # Recommend based on 5% threshold
        breach_rate = threshold_breaches[0.05] / len(historical_drift)
        
        if breach_rate > 0.5:
            frequency = "monthly"
        elif breach_rate > 0.25:
            frequency = "quarterly"
        else:
            frequency = "semi-annually"
        
        return {
            "recommended_frequency": frequency,
            "threshold_analysis": threshold_breaches,
            "breach_rate_5pct": breach_rate,
        }
