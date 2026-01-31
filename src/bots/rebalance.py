"""Rebalancing Bot.

Automated portfolio rebalancing to maintain target allocations.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.bots.config import (
    BotConfig,
    RebalanceConfig,
    RebalanceMethod,
    TradeSide,
    OrderType,
)
from src.bots.models import BotOrder, BotPosition
from src.bots.base import BaseBot, BrokerInterface

logger = logging.getLogger(__name__)


class RebalanceBot(BaseBot):
    """Portfolio Rebalancing Bot.
    
    Maintains target portfolio allocations through
    periodic rebalancing.
    
    Features:
    - Target weight maintenance
    - Drift-based triggers
    - Tax-aware rebalancing
    - Cash flow rebalancing
    
    Example:
        config = BotConfig(
            bot_id="rebal_1",
            name="60/40 Portfolio",
            bot_type=BotType.REBALANCE,
            symbols=["SPY", "BND"],
            rebalance_config=RebalanceConfig(
                target_allocations={"SPY": 0.6, "BND": 0.4},
                drift_threshold_pct=5.0,
            ),
        )
        bot = RebalanceBot(config)
    """
    
    def __init__(
        self,
        config: BotConfig,
        broker: Optional[BrokerInterface] = None,
    ):
        super().__init__(config, broker)
        self.rebalance_config = config.rebalance_config or RebalanceConfig()
        
        # Validate allocations sum to 1
        total = sum(self.rebalance_config.target_allocations.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Target allocations sum to {total}, not 1.0")
    
    def generate_orders(self, market_data: dict[str, dict]) -> list[BotOrder]:
        """Generate rebalancing orders.
        
        Args:
            market_data: Current market prices.
            
        Returns:
            List of buy/sell orders to rebalance.
        """
        # Calculate current portfolio value
        portfolio_value = self._calculate_portfolio_value(market_data)
        if portfolio_value <= 0:
            logger.warning("Portfolio value is zero, cannot rebalance")
            return []
        
        # Calculate current vs target allocations
        drift_analysis = self._analyze_drift(market_data, portfolio_value)
        
        # Check if rebalancing is needed
        max_drift = max(abs(d["drift_pct"]) for d in drift_analysis.values())
        if max_drift < self.rebalance_config.drift_threshold_pct:
            logger.info(f"Max drift {max_drift:.2f}% below threshold, no rebalance needed")
            return []
        
        # Generate orders based on method
        method = self.rebalance_config.rebalance_method
        
        if method == RebalanceMethod.FULL:
            orders = self._full_rebalance(drift_analysis, market_data)
        elif method == RebalanceMethod.THRESHOLD_ONLY:
            orders = self._threshold_rebalance(drift_analysis, market_data)
        elif method == RebalanceMethod.TAX_AWARE:
            orders = self._tax_aware_rebalance(drift_analysis, market_data)
        else:
            orders = self._threshold_rebalance(drift_analysis, market_data)
        
        return orders
    
    def _calculate_portfolio_value(self, market_data: dict[str, dict]) -> float:
        """Calculate total portfolio value."""
        total = 0.0
        
        for symbol, pos in self._positions.items():
            price = market_data.get(symbol, {}).get("price", pos.current_price)
            total += pos.quantity * price
        
        return total
    
    def _analyze_drift(
        self,
        market_data: dict[str, dict],
        portfolio_value: float,
    ) -> dict[str, dict]:
        """Analyze current allocation drift.
        
        Returns:
            Dict of symbol -> drift analysis.
        """
        analysis = {}
        targets = self.rebalance_config.target_allocations
        
        for symbol in set(list(targets.keys()) + list(self._positions.keys())):
            pos = self._positions.get(symbol)
            price = market_data.get(symbol, {}).get("price", 0)
            
            current_value = (pos.quantity * price) if pos else 0
            current_pct = (current_value / portfolio_value * 100) if portfolio_value > 0 else 0
            target_pct = targets.get(symbol, 0) * 100
            drift_pct = current_pct - target_pct
            
            target_value = portfolio_value * targets.get(symbol, 0)
            trade_value = target_value - current_value
            trade_shares = (trade_value / price) if price > 0 else 0
            
            analysis[symbol] = {
                "current_value": current_value,
                "current_pct": current_pct,
                "target_pct": target_pct,
                "drift_pct": drift_pct,
                "target_value": target_value,
                "trade_value": trade_value,
                "trade_shares": trade_shares,
                "price": price,
            }
        
        return analysis
    
    def _full_rebalance(
        self,
        drift_analysis: dict[str, dict],
        market_data: dict[str, dict],
    ) -> list[BotOrder]:
        """Generate orders for full rebalance."""
        orders = []
        
        # Sell orders first
        for symbol, analysis in drift_analysis.items():
            if analysis["trade_shares"] < 0:
                quantity = abs(analysis["trade_shares"])
                if quantity * analysis["price"] >= self.rebalance_config.min_trade_size:
                    orders.append(BotOrder(
                        bot_id=self.bot_id,
                        symbol=symbol,
                        side=TradeSide.SELL,
                        quantity=round(quantity, 4),
                        order_type=OrderType.MARKET,
                        limit_price=analysis["price"],
                    ))
        
        # Buy orders
        for symbol, analysis in drift_analysis.items():
            if analysis["trade_shares"] > 0:
                quantity = analysis["trade_shares"]
                if quantity * analysis["price"] >= self.rebalance_config.min_trade_size:
                    orders.append(BotOrder(
                        bot_id=self.bot_id,
                        symbol=symbol,
                        side=TradeSide.BUY,
                        quantity=round(quantity, 4),
                        order_type=OrderType.MARKET,
                        limit_price=analysis["price"],
                    ))
        
        return orders
    
    def _threshold_rebalance(
        self,
        drift_analysis: dict[str, dict],
        market_data: dict[str, dict],
    ) -> list[BotOrder]:
        """Generate orders only for positions exceeding drift threshold."""
        orders = []
        threshold = self.rebalance_config.drift_threshold_pct
        
        for symbol, analysis in drift_analysis.items():
            if abs(analysis["drift_pct"]) < threshold:
                continue
            
            quantity = abs(analysis["trade_shares"])
            if quantity * analysis["price"] < self.rebalance_config.min_trade_size:
                continue
            
            side = TradeSide.SELL if analysis["trade_shares"] < 0 else TradeSide.BUY
            
            orders.append(BotOrder(
                bot_id=self.bot_id,
                symbol=symbol,
                side=side,
                quantity=round(quantity, 4),
                order_type=OrderType.MARKET,
                limit_price=analysis["price"],
            ))
        
        return orders
    
    def _tax_aware_rebalance(
        self,
        drift_analysis: dict[str, dict],
        market_data: dict[str, dict],
    ) -> list[BotOrder]:
        """Generate tax-efficient rebalancing orders.
        
        Prefers selling losers and buying with new cash.
        """
        orders = []
        threshold = self.rebalance_config.drift_threshold_pct
        
        # Prioritize selling positions with losses
        sell_candidates = []
        for symbol, analysis in drift_analysis.items():
            if analysis["trade_shares"] >= 0:
                continue
            if abs(analysis["drift_pct"]) < threshold:
                continue
            
            pos = self._positions.get(symbol)
            if pos:
                # Check if position has loss
                has_loss = pos.unrealized_pnl < 0
                sell_candidates.append({
                    "symbol": symbol,
                    "analysis": analysis,
                    "has_loss": has_loss,
                    "pnl": pos.unrealized_pnl,
                })
        
        # Sort: sell losers first
        sell_candidates.sort(key=lambda x: (not x["has_loss"], x["pnl"]))
        
        for candidate in sell_candidates:
            analysis = candidate["analysis"]
            quantity = abs(analysis["trade_shares"])
            
            if quantity * analysis["price"] >= self.rebalance_config.min_trade_size:
                orders.append(BotOrder(
                    bot_id=self.bot_id,
                    symbol=candidate["symbol"],
                    side=TradeSide.SELL,
                    quantity=round(quantity, 4),
                    order_type=OrderType.MARKET,
                    limit_price=analysis["price"],
                ))
        
        # Add buy orders
        for symbol, analysis in drift_analysis.items():
            if analysis["trade_shares"] <= 0:
                continue
            if abs(analysis["drift_pct"]) < threshold:
                continue
            
            quantity = analysis["trade_shares"]
            if quantity * analysis["price"] >= self.rebalance_config.min_trade_size:
                orders.append(BotOrder(
                    bot_id=self.bot_id,
                    symbol=symbol,
                    side=TradeSide.BUY,
                    quantity=round(quantity, 4),
                    order_type=OrderType.MARKET,
                    limit_price=analysis["price"],
                ))
        
        return orders
    
    def get_drift_analysis(self, market_data: dict[str, dict]) -> list[dict]:
        """Get current drift analysis for display.
        
        Args:
            market_data: Current market data.
            
        Returns:
            List of drift details per symbol.
        """
        portfolio_value = self._calculate_portfolio_value(market_data)
        if portfolio_value <= 0:
            return []
        
        analysis = self._analyze_drift(market_data, portfolio_value)
        
        result = []
        for symbol, data in analysis.items():
            result.append({
                "symbol": symbol,
                "target_pct": data["target_pct"],
                "current_pct": data["current_pct"],
                "drift_pct": data["drift_pct"],
                "current_value": data["current_value"],
                "target_value": data["target_value"],
                "trade_needed": data["trade_value"],
                "needs_rebalance": abs(data["drift_pct"]) >= self.rebalance_config.drift_threshold_pct,
            })
        
        return sorted(result, key=lambda x: abs(x["drift_pct"]), reverse=True)
    
    def set_positions(self, positions: list[BotPosition]) -> None:
        """Set current positions (for testing/initialization).
        
        Args:
            positions: List of positions.
        """
        self._positions = {p.symbol: p for p in positions}
