"""Position Sizing Algorithms - Determine optimal position sizes.

Implements multiple sizing strategies:
- Equal weight
- Score-weighted (proportional to factor scores)
- Volatility-targeted (inverse volatility weighting)
- Kelly Criterion (optimal growth)
- Risk parity (equal risk contribution)

All methods respect position and sector constraints.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SizingConstraints:
    """Constraints for position sizing."""
    max_position_pct: float = 0.15  # Max 15% in single position
    max_sector_pct: float = 0.35   # Max 35% in single sector
    min_position_value: float = 500  # Minimum $500 per position
    cash_buffer_pct: float = 0.02   # Keep 2% cash minimum
    max_leverage: float = 1.0       # No leverage by default


class PositionSizer:
    """Calculate optimal position sizes using various methodologies.
    
    Example:
        sizer = PositionSizer(constraints=SizingConstraints())
        
        # Equal weight across 10 stocks
        allocations = sizer.equal_weight(100000, 10)
        
        # Score-weighted based on factor scores
        scores = {'AAPL': 0.8, 'MSFT': 0.7, 'GOOGL': 0.6}
        allocations = sizer.score_weighted(100000, scores)
        
        # Volatility-targeted
        vols = {'AAPL': 0.25, 'MSFT': 0.22, 'GOOGL': 0.28}
        allocations = sizer.volatility_targeted(100000, 0.15, vols)
    """
    
    def __init__(
        self,
        constraints: Optional[SizingConstraints] = None,
        sector_map: Optional[dict[str, str]] = None,
    ):
        """Initialize position sizer.
        
        Args:
            constraints: Position sizing constraints.
            sector_map: Mapping of symbol -> sector for sector limits.
        """
        self.constraints = constraints or SizingConstraints()
        self.sector_map = sector_map or {}
    
    def equal_weight(
        self,
        portfolio_value: float,
        n_positions: int,
    ) -> dict[str, float]:
        """Equal allocation across all positions.
        
        Args:
            portfolio_value: Total portfolio value.
            n_positions: Number of positions.
            
        Returns:
            Dict with position size (same for each position).
        """
        if n_positions <= 0:
            return {}
        
        # Apply cash buffer
        investable = portfolio_value * (1 - self.constraints.cash_buffer_pct)
        
        # Equal split
        position_size = investable / n_positions
        
        # Apply max position constraint
        max_size = portfolio_value * self.constraints.max_position_pct
        position_size = min(position_size, max_size)
        
        return {"per_position": position_size}
    
    def score_weighted(
        self,
        portfolio_value: float,
        scores: dict[str, float],
        min_score: float = 0.0,
    ) -> dict[str, float]:
        """Allocate proportional to factor scores.
        
        Higher-scoring stocks get larger allocations.
        
        Args:
            portfolio_value: Total portfolio value.
            scores: Dict mapping symbol to factor score.
            min_score: Minimum score threshold (exclude below).
            
        Returns:
            Dict mapping symbol to dollar allocation.
        """
        if not scores:
            return {}
        
        # Filter by minimum score
        filtered = {s: max(0, score - min_score) for s, score in scores.items() if score > min_score}
        
        if not filtered:
            return {}
        
        # Calculate raw weights
        total_score = sum(filtered.values())
        if total_score == 0:
            # Fall back to equal weight
            equal_size = portfolio_value / len(filtered)
            return {s: equal_size for s in filtered}
        
        raw_weights = {s: score / total_score for s, score in filtered.items()}
        
        # Apply constraints
        allocations = self._apply_constraints(portfolio_value, raw_weights)
        
        return allocations
    
    def volatility_targeted(
        self,
        portfolio_value: float,
        target_vol: float,
        stock_vols: dict[str, float],
    ) -> dict[str, float]:
        """Size positions to achieve target portfolio volatility.
        
        Uses inverse volatility weighting - lower vol stocks get higher weight.
        
        Args:
            portfolio_value: Total portfolio value.
            target_vol: Target annual portfolio volatility (e.g., 0.15 for 15%).
            stock_vols: Dict mapping symbol to annualized volatility.
            
        Returns:
            Dict mapping symbol to dollar allocation.
        """
        if not stock_vols:
            return {}
        
        # Calculate inverse volatility weights
        inv_vols = {}
        for symbol, vol in stock_vols.items():
            if vol > 0:
                inv_vols[symbol] = 1 / vol
            else:
                inv_vols[symbol] = 1  # Default if vol is zero
        
        total_inv_vol = sum(inv_vols.values())
        raw_weights = {s: iv / total_inv_vol for s, iv in inv_vols.items()}
        
        # Scale weights by target volatility
        # Simple scaling: if average stock vol is higher than target, reduce total exposure
        avg_vol = sum(stock_vols.values()) / len(stock_vols)
        vol_scalar = min(1.0, target_vol / avg_vol) if avg_vol > 0 else 1.0
        
        scaled_weights = {s: w * vol_scalar for s, w in raw_weights.items()}
        
        # Apply constraints
        allocations = self._apply_constraints(portfolio_value, scaled_weights)
        
        return allocations
    
    def kelly_criterion(
        self,
        win_rate: float,
        avg_win_pct: float,
        avg_loss_pct: float,
        kelly_fraction: float = 0.25,
    ) -> float:
        """Calculate Kelly Criterion position size.
        
        Returns optimal fraction of portfolio to risk on a single trade.
        We use fractional Kelly (default 1/4) for safety.
        
        Args:
            win_rate: Probability of winning trade (0-1).
            avg_win_pct: Average win as percentage (e.g., 0.05 for 5%).
            avg_loss_pct: Average loss as percentage (positive number).
            kelly_fraction: Fraction of full Kelly to use (0.25 = quarter Kelly).
            
        Returns:
            Optimal position size as fraction of portfolio.
        """
        if avg_loss_pct <= 0 or avg_win_pct <= 0:
            return 0.0
        
        if not (0 < win_rate < 1):
            return 0.0
        
        # Kelly formula: f* = (p * b - q) / b
        # where p = win rate, q = 1-p, b = win/loss ratio
        b = avg_win_pct / avg_loss_pct
        p = win_rate
        q = 1 - p
        
        kelly = (p * b - q) / b
        
        # Apply fraction and ensure non-negative
        result = max(0, kelly * kelly_fraction)
        
        # Cap at max position constraint
        return min(result, self.constraints.max_position_pct)
    
    def risk_parity(
        self,
        portfolio_value: float,
        volatilities: dict[str, float],
        correlations: Optional[pd.DataFrame] = None,
    ) -> dict[str, float]:
        """Equal risk contribution from each position.
        
        Each position contributes equally to total portfolio risk.
        
        Args:
            portfolio_value: Total portfolio value.
            volatilities: Dict mapping symbol to annualized volatility.
            correlations: Optional correlation matrix (assumes 0 if not provided).
            
        Returns:
            Dict mapping symbol to dollar allocation.
        """
        if not volatilities:
            return {}
        
        symbols = list(volatilities.keys())
        n = len(symbols)
        
        if correlations is None:
            # Assume zero correlation (simplification)
            # In this case, risk parity = inverse volatility weighting
            return self.volatility_targeted(portfolio_value, 0.15, volatilities)
        
        # Build covariance matrix
        vols = np.array([volatilities[s] for s in symbols])
        corr_matrix = correlations.loc[symbols, symbols].values
        cov_matrix = np.outer(vols, vols) * corr_matrix
        
        # Start with inverse volatility weights
        inv_vol = 1 / vols
        weights = inv_vol / inv_vol.sum()
        
        # Iterative optimization for risk parity
        # (Simple Newton-like iteration)
        for _ in range(100):
            # Calculate marginal risk contribution
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
            if portfolio_vol == 0:
                break
            
            mrc = (cov_matrix @ weights) / portfolio_vol
            risk_contrib = weights * mrc
            
            # Target equal risk contribution
            target_rc = portfolio_vol / n
            
            # Adjust weights
            adjustment = target_rc / (risk_contrib + 1e-10)
            weights = weights * adjustment
            weights = weights / weights.sum()  # Normalize
        
        # Convert to allocations
        raw_weights = {s: w for s, w in zip(symbols, weights)}
        allocations = self._apply_constraints(portfolio_value, raw_weights)
        
        return allocations
    
    def from_target_weights(
        self,
        portfolio_value: float,
        target_weights: dict[str, float],
    ) -> dict[str, float]:
        """Convert target weights to dollar allocations.
        
        Args:
            portfolio_value: Total portfolio value.
            target_weights: Dict mapping symbol to target weight (0-1).
            
        Returns:
            Dict mapping symbol to dollar allocation.
        """
        # Normalize weights if they don't sum to 1
        total = sum(target_weights.values())
        if total > 0 and abs(total - 1.0) > 0.01:
            target_weights = {s: w / total for s, w in target_weights.items()}
        
        allocations = self._apply_constraints(portfolio_value, target_weights)
        return allocations
    
    def _apply_constraints(
        self,
        portfolio_value: float,
        weights: dict[str, float],
    ) -> dict[str, float]:
        """Apply position and sector constraints to weights.
        
        Args:
            portfolio_value: Total portfolio value.
            weights: Raw weights (should sum to ~1).
            
        Returns:
            Constrained dollar allocations.
        """
        # Apply cash buffer
        investable = portfolio_value * (1 - self.constraints.cash_buffer_pct)
        
        # Apply max position constraint
        max_position_weight = self.constraints.max_position_pct
        constrained_weights = {
            s: min(w, max_position_weight)
            for s, w in weights.items()
        }
        
        # Apply sector constraints if sector map provided
        if self.sector_map:
            sector_weights: dict[str, float] = {}
            for symbol, weight in constrained_weights.items():
                sector = self.sector_map.get(symbol, "Unknown")
                sector_weights[sector] = sector_weights.get(sector, 0) + weight
            
            # Scale down sectors that exceed limit
            for sector, total_weight in sector_weights.items():
                if total_weight > self.constraints.max_sector_pct:
                    scale = self.constraints.max_sector_pct / total_weight
                    for symbol in constrained_weights:
                        if self.sector_map.get(symbol) == sector:
                            constrained_weights[symbol] *= scale
        
        # Renormalize weights
        total_weight = sum(constrained_weights.values())
        if total_weight > 0:
            # Don't exceed investable amount
            scale = min(1.0, 1.0 / total_weight)
            normalized_weights = {s: w * scale for s, w in constrained_weights.items()}
        else:
            normalized_weights = constrained_weights
        
        # Convert to dollar allocations
        allocations = {}
        for symbol, weight in normalized_weights.items():
            allocation = weight * investable
            
            # Apply minimum position size
            if allocation >= self.constraints.min_position_value:
                allocations[symbol] = allocation
        
        return allocations
    
    def calculate_shares(
        self,
        allocations: dict[str, float],
        prices: dict[str, float],
        allow_fractional: bool = True,
    ) -> dict[str, float]:
        """Convert dollar allocations to share counts.
        
        Args:
            allocations: Dollar allocation per symbol.
            prices: Current price per symbol.
            allow_fractional: Allow fractional shares (Alpaca supports this).
            
        Returns:
            Dict mapping symbol to number of shares.
        """
        shares = {}
        
        for symbol, allocation in allocations.items():
            price = prices.get(symbol, 0)
            if price <= 0:
                continue
            
            share_count = allocation / price
            
            if not allow_fractional:
                share_count = int(share_count)
            
            if share_count > 0:
                shares[symbol] = share_count
        
        return shares
