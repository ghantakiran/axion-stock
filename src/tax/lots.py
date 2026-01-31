"""Tax Lot Management.

Manages tax lots for cost basis tracking and lot selection for sales.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import logging

from src.tax.config import (
    LotSelectionMethod,
    HoldingPeriod,
    AcquisitionType,
    TaxConfig,
    DEFAULT_TAX_CONFIG,
)
from src.tax.models import TaxLot, RealizedGain

logger = logging.getLogger(__name__)


@dataclass
class LotSelectionResult:
    """Result of selecting lots for a sale."""
    lots_used: list[tuple[TaxLot, float]]  # (lot, shares_from_lot)
    total_shares: float = 0.0
    total_cost_basis: float = 0.0
    short_term_shares: float = 0.0
    long_term_shares: float = 0.0
    estimated_gain_loss: float = 0.0


class TaxLotManager:
    """Manages tax lots for cost basis tracking and lot selection.
    
    Provides methods to:
    - Add new lots from purchases
    - Select lots for sales using various methods (FIFO, LIFO, MinTax, etc.)
    - Track remaining shares in each lot
    - Calculate cost basis for sales
    """
    
    def __init__(self, config: Optional[TaxConfig] = None):
        self.config = config or DEFAULT_TAX_CONFIG
        self._lots: dict[str, list[TaxLot]] = {}  # symbol -> list of lots
        self._lot_index: dict[str, TaxLot] = {}  # lot_id -> lot
    
    def add_lot(self, lot: TaxLot) -> TaxLot:
        """Add a new tax lot.
        
        Args:
            lot: Tax lot to add.
            
        Returns:
            The added lot.
        """
        if lot.symbol not in self._lots:
            self._lots[lot.symbol] = []
        
        self._lots[lot.symbol].append(lot)
        self._lot_index[lot.lot_id] = lot
        
        logger.debug(f"Added lot {lot.lot_id}: {lot.shares} shares of {lot.symbol}")
        return lot
    
    def create_lot(
        self,
        account_id: str,
        symbol: str,
        shares: float,
        cost_per_share: float,
        acquisition_date: Optional[date] = None,
        acquisition_type: AcquisitionType = AcquisitionType.BUY,
    ) -> TaxLot:
        """Create and add a new tax lot.
        
        Args:
            account_id: Account identifier.
            symbol: Stock symbol.
            shares: Number of shares.
            cost_per_share: Cost per share.
            acquisition_date: Date acquired (defaults to today).
            acquisition_type: How shares were acquired.
            
        Returns:
            Newly created lot.
        """
        lot = TaxLot(
            account_id=account_id,
            symbol=symbol,
            shares=shares,
            cost_basis=shares * cost_per_share,
            acquisition_date=acquisition_date or date.today(),
            acquisition_type=acquisition_type,
        )
        return self.add_lot(lot)
    
    def get_lots(self, symbol: str, include_empty: bool = False) -> list[TaxLot]:
        """Get all lots for a symbol.
        
        Args:
            symbol: Stock symbol.
            include_empty: Include lots with no remaining shares.
            
        Returns:
            List of tax lots.
        """
        lots = self._lots.get(symbol, [])
        if include_empty:
            return lots
        return [lot for lot in lots if lot.remaining_shares > 0]
    
    def get_lot(self, lot_id: str) -> Optional[TaxLot]:
        """Get a specific lot by ID."""
        return self._lot_index.get(lot_id)
    
    def get_total_shares(self, symbol: str) -> float:
        """Get total remaining shares for a symbol."""
        return sum(lot.remaining_shares for lot in self.get_lots(symbol))
    
    def get_total_cost_basis(self, symbol: str) -> float:
        """Get total cost basis for remaining shares."""
        total = 0.0
        for lot in self.get_lots(symbol):
            if lot.remaining_shares > 0:
                ratio = lot.remaining_shares / lot.shares
                total += lot.adjusted_basis * ratio
        return total
    
    def get_average_cost(self, symbol: str) -> float:
        """Get average cost per share for a symbol."""
        total_shares = self.get_total_shares(symbol)
        if total_shares == 0:
            return 0.0
        return self.get_total_cost_basis(symbol) / total_shares
    
    def select_lots(
        self,
        symbol: str,
        shares_to_sell: float,
        method: Optional[LotSelectionMethod] = None,
        current_price: Optional[float] = None,
        target_lot_ids: Optional[list[str]] = None,
    ) -> LotSelectionResult:
        """Select lots for a sale using specified method.
        
        Args:
            symbol: Stock symbol.
            shares_to_sell: Number of shares to sell.
            method: Lot selection method (defaults to config default).
            current_price: Current market price (for tax calculations).
            target_lot_ids: Specific lots to use (for SPEC_ID method).
            
        Returns:
            LotSelectionResult with selected lots and cost basis.
        """
        method = method or self.config.lot_selection.default_method
        lots = self.get_lots(symbol)
        
        if not lots:
            return LotSelectionResult(lots_used=[])
        
        if method == LotSelectionMethod.SPEC_ID and target_lot_ids:
            return self._select_specific_lots(lots, shares_to_sell, target_lot_ids)
        
        # Sort lots based on method
        sorted_lots = self._sort_lots_by_method(lots, method, current_price)
        
        return self._select_from_sorted(sorted_lots, shares_to_sell, current_price)
    
    def _sort_lots_by_method(
        self,
        lots: list[TaxLot],
        method: LotSelectionMethod,
        current_price: Optional[float],
    ) -> list[TaxLot]:
        """Sort lots based on selection method."""
        if method == LotSelectionMethod.FIFO:
            return sorted(lots, key=lambda x: x.acquisition_date)
        
        elif method == LotSelectionMethod.LIFO:
            return sorted(lots, key=lambda x: x.acquisition_date, reverse=True)
        
        elif method == LotSelectionMethod.HIGH_COST:
            return sorted(lots, key=lambda x: x.adjusted_cost_per_share, reverse=True)
        
        elif method == LotSelectionMethod.MAX_LOSS:
            if current_price is None:
                return lots
            return sorted(
                lots,
                key=lambda x: current_price - x.adjusted_cost_per_share
            )
        
        elif method == LotSelectionMethod.MIN_TAX:
            return self._sort_for_min_tax(lots, current_price)
        
        return lots
    
    def _sort_for_min_tax(
        self,
        lots: list[TaxLot],
        current_price: Optional[float],
    ) -> list[TaxLot]:
        """Sort lots to minimize tax impact.
        
        Strategy:
        1. First use lots with losses (highest loss first)
        2. Then use long-term gain lots (lowest gain first)
        3. Finally use short-term gain lots (lowest gain first)
        """
        if current_price is None:
            return lots
        
        def tax_score(lot: TaxLot) -> tuple[int, float]:
            gain_per_share = current_price - lot.adjusted_cost_per_share
            is_gain = gain_per_share > 0
            is_long_term = lot.holding_period == HoldingPeriod.LONG_TERM
            
            if not is_gain:
                # Losses first, biggest loss first
                return (0, gain_per_share)
            elif is_long_term:
                # Long-term gains second, smallest gain first
                return (1, gain_per_share)
            else:
                # Short-term gains last, smallest gain first
                return (2, gain_per_share)
        
        return sorted(lots, key=tax_score)
    
    def _select_from_sorted(
        self,
        sorted_lots: list[TaxLot],
        shares_to_sell: float,
        current_price: Optional[float],
    ) -> LotSelectionResult:
        """Select shares from sorted lots."""
        lots_used: list[tuple[TaxLot, float]] = []
        remaining = shares_to_sell
        total_basis = 0.0
        short_term = 0.0
        long_term = 0.0
        
        for lot in sorted_lots:
            if remaining <= 0:
                break
            
            if lot.remaining_shares <= 0:
                continue
            
            shares_from_lot = min(lot.remaining_shares, remaining)
            lots_used.append((lot, shares_from_lot))
            
            # Calculate cost basis for shares used
            ratio = shares_from_lot / lot.shares
            lot_basis = lot.adjusted_basis * ratio
            total_basis += lot_basis
            
            # Track holding period
            if lot.holding_period == HoldingPeriod.SHORT_TERM:
                short_term += shares_from_lot
            else:
                long_term += shares_from_lot
            
            remaining -= shares_from_lot
        
        total_shares = shares_to_sell - remaining
        estimated_gain = 0.0
        if current_price is not None:
            estimated_gain = (current_price * total_shares) - total_basis
        
        return LotSelectionResult(
            lots_used=lots_used,
            total_shares=total_shares,
            total_cost_basis=total_basis,
            short_term_shares=short_term,
            long_term_shares=long_term,
            estimated_gain_loss=estimated_gain,
        )
    
    def _select_specific_lots(
        self,
        lots: list[TaxLot],
        shares_to_sell: float,
        target_lot_ids: list[str],
    ) -> LotSelectionResult:
        """Select specific lots by ID."""
        lot_map = {lot.lot_id: lot for lot in lots}
        target_lots = [lot_map[lid] for lid in target_lot_ids if lid in lot_map]
        return self._select_from_sorted(target_lots, shares_to_sell, None)
    
    def execute_sale(
        self,
        symbol: str,
        shares: float,
        proceeds: float,
        sale_date: Optional[date] = None,
        method: Optional[LotSelectionMethod] = None,
        target_lot_ids: Optional[list[str]] = None,
    ) -> list[RealizedGain]:
        """Execute a sale and generate realized gain/loss records.
        
        Args:
            symbol: Stock symbol.
            shares: Number of shares sold.
            proceeds: Total sale proceeds.
            sale_date: Date of sale (defaults to today).
            method: Lot selection method.
            target_lot_ids: Specific lots to sell from.
            
        Returns:
            List of RealizedGain records for each lot used.
        """
        sale_date = sale_date or date.today()
        price_per_share = proceeds / shares if shares > 0 else 0
        
        selection = self.select_lots(
            symbol=symbol,
            shares_to_sell=shares,
            method=method,
            current_price=price_per_share,
            target_lot_ids=target_lot_ids,
        )
        
        realized_gains: list[RealizedGain] = []
        
        for lot, shares_sold in selection.lots_used:
            # Calculate proceeds and basis for this portion
            ratio = shares_sold / shares
            lot_proceeds = proceeds * ratio
            
            basis_ratio = shares_sold / lot.shares
            lot_basis = lot.adjusted_basis * basis_ratio
            
            gain_loss = lot_proceeds - lot_basis
            
            # Create realized gain record
            realized = RealizedGain(
                account_id=lot.account_id,
                lot_id=lot.lot_id,
                symbol=symbol,
                shares=shares_sold,
                proceeds=lot_proceeds,
                cost_basis=lot_basis,
                gain_loss=gain_loss,
                holding_period=lot.holding_period,
                sale_date=sale_date,
                acquisition_date=lot.acquisition_date,
            )
            realized_gains.append(realized)
            
            # Update lot remaining shares
            lot.remaining_shares -= shares_sold
            
            logger.debug(
                f"Sold {shares_sold} shares from lot {lot.lot_id}: "
                f"gain/loss = ${gain_loss:.2f}"
            )
        
        return realized_gains
    
    def adjust_lot_basis(
        self,
        lot_id: str,
        adjustment: float,
        reason: str = "wash_sale",
    ) -> None:
        """Adjust a lot's cost basis (e.g., for wash sale).
        
        Args:
            lot_id: Lot to adjust.
            adjustment: Amount to add to basis.
            reason: Reason for adjustment.
        """
        lot = self.get_lot(lot_id)
        if lot:
            lot.adjusted_basis += adjustment
            lot.wash_sale_adjustment += adjustment
            logger.info(
                f"Adjusted lot {lot_id} basis by ${adjustment:.2f} ({reason})"
            )
    
    def get_unrealized_gains(
        self,
        symbol: str,
        current_price: float,
    ) -> dict[str, float]:
        """Get unrealized gains/losses by holding period.
        
        Args:
            symbol: Stock symbol.
            current_price: Current market price.
            
        Returns:
            Dict with 'short_term' and 'long_term' unrealized amounts.
        """
        short_term = 0.0
        long_term = 0.0
        
        for lot in self.get_lots(symbol):
            if lot.remaining_shares <= 0:
                continue
            
            ratio = lot.remaining_shares / lot.shares
            basis = lot.adjusted_basis * ratio
            value = lot.remaining_shares * current_price
            gain = value - basis
            
            if lot.holding_period == HoldingPeriod.SHORT_TERM:
                short_term += gain
            else:
                long_term += gain
        
        return {
            "short_term": short_term,
            "long_term": long_term,
            "total": short_term + long_term,
        }
    
    def get_lots_approaching_long_term(
        self,
        days_threshold: int = 30,
    ) -> list[TaxLot]:
        """Find lots that will become long-term within threshold.
        
        Useful for identifying positions to hold for better tax treatment.
        """
        approaching = []
        for lots in self._lots.values():
            for lot in lots:
                if lot.remaining_shares > 0:
                    days_to_lt = lot.days_to_long_term
                    if 0 < days_to_lt <= days_threshold:
                        approaching.append(lot)
        
        return sorted(approaching, key=lambda x: x.days_to_long_term)
