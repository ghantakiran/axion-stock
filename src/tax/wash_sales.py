"""Wash Sale Detection and Tracking.

Implements IRS wash sale rules to detect disallowed losses and track
basis adjustments for replacement shares.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional
import logging

from src.tax.config import WashSaleConfig, TaxConfig, DEFAULT_TAX_CONFIG
from src.tax.models import TaxLot, RealizedGain, WashSale

logger = logging.getLogger(__name__)


@dataclass
class WashSaleCheckResult:
    """Result of checking for wash sale."""
    is_wash_sale: bool = False
    disallowed_loss: float = 0.0
    wash_sale_shares: float = 0.0
    replacement_lot_id: Optional[str] = None
    replacement_date: Optional[date] = None
    basis_adjustment: float = 0.0
    holding_period_adjustment_days: int = 0
    reason: str = ""


@dataclass
class Transaction:
    """Generic transaction for wash sale checking."""
    symbol: str
    shares: float
    date: date
    is_purchase: bool  # True for buy, False for sell
    lot_id: Optional[str] = None
    price: float = 0.0


class WashSaleTracker:
    """Tracks and detects wash sales per IRS rules.
    
    A wash sale occurs when you sell a security at a loss and buy
    a "substantially identical" security within 30 days before or
    after the sale.
    
    Consequences:
    - The loss is disallowed for tax purposes
    - The disallowed loss is added to the basis of the replacement shares
    - The holding period of the replacement shares is adjusted
    """
    
    def __init__(self, config: Optional[TaxConfig] = None):
        self.config = config or DEFAULT_TAX_CONFIG
        self._wash_sale_config = self.config.wash_sale
        self._transactions: list[Transaction] = []
        self._wash_sales: list[WashSale] = []
        self._substantially_identical: dict[str, set[str]] = {}  # symbol -> related symbols
    
    def add_transaction(self, txn: Transaction) -> None:
        """Record a transaction for wash sale tracking."""
        self._transactions.append(txn)
        self._transactions.sort(key=lambda x: x.date)
    
    def add_substantially_identical(self, symbol: str, related: str) -> None:
        """Mark two symbols as substantially identical.
        
        For example, SPY and IVV are substantially identical
        (both track S&P 500).
        """
        if symbol not in self._substantially_identical:
            self._substantially_identical[symbol] = set()
        if related not in self._substantially_identical:
            self._substantially_identical[related] = set()
        
        self._substantially_identical[symbol].add(related)
        self._substantially_identical[related].add(symbol)
    
    def get_substantially_identical(self, symbol: str) -> set[str]:
        """Get all symbols substantially identical to given symbol."""
        identical = {symbol}  # Always includes itself
        identical.update(self._substantially_identical.get(symbol, set()))
        return identical
    
    def check_wash_sale(
        self,
        symbol: str,
        sale_date: date,
        loss_amount: float,
        shares_sold: float,
    ) -> WashSaleCheckResult:
        """Check if a loss sale triggers wash sale rules.
        
        Args:
            symbol: Symbol sold at a loss.
            sale_date: Date of the loss sale.
            loss_amount: Amount of loss (should be negative).
            shares_sold: Number of shares sold.
            
        Returns:
            WashSaleCheckResult with details.
        """
        # Only applies to losses
        if loss_amount >= 0:
            return WashSaleCheckResult(reason="Not a loss sale")
        
        # Define wash sale window
        window_start = sale_date - timedelta(days=self._wash_sale_config.lookback_days)
        window_end = sale_date + timedelta(days=self._wash_sale_config.lookforward_days)
        
        # Get all symbols to check
        symbols_to_check = self.get_substantially_identical(symbol)
        
        # Find replacement purchases in the window
        replacement_purchases = self._find_replacement_purchases(
            symbols_to_check=symbols_to_check,
            window_start=window_start,
            window_end=window_end,
            sale_date=sale_date,
        )
        
        if not replacement_purchases:
            return WashSaleCheckResult(reason="No replacement purchase found")
        
        # Calculate wash sale impact
        # Use the earliest replacement purchase
        replacement = min(replacement_purchases, key=lambda x: x.date)
        
        # Wash sale shares is the minimum of sold shares and replacement shares
        wash_shares = min(shares_sold, replacement.shares)
        
        # Disallowed loss is proportional to wash sale shares
        disallow_ratio = wash_shares / shares_sold
        disallowed = abs(loss_amount) * disallow_ratio
        
        return WashSaleCheckResult(
            is_wash_sale=True,
            disallowed_loss=disallowed,
            wash_sale_shares=wash_shares,
            replacement_lot_id=replacement.lot_id,
            replacement_date=replacement.date,
            basis_adjustment=disallowed,
            holding_period_adjustment_days=self._calculate_holding_adjustment(
                sale_date, replacement.date
            ),
            reason=f"Replacement purchase on {replacement.date}",
        )
    
    def _find_replacement_purchases(
        self,
        symbols_to_check: set[str],
        window_start: date,
        window_end: date,
        sale_date: date,
    ) -> list[Transaction]:
        """Find purchases that could trigger wash sale."""
        replacements = []
        
        for txn in self._transactions:
            if not txn.is_purchase:
                continue
            
            if txn.symbol not in symbols_to_check:
                continue
            
            if window_start <= txn.date <= window_end:
                # Exclude the sale transaction itself
                if txn.date != sale_date:
                    replacements.append(txn)
        
        return replacements
    
    def _calculate_holding_adjustment(
        self,
        sale_date: date,
        replacement_date: date,
    ) -> int:
        """Calculate holding period adjustment for wash sale.
        
        The holding period of the original shares is added to the
        replacement shares.
        """
        # This would need the original acquisition date to be accurate
        # For now, return the days between sale and replacement
        return abs((replacement_date - sale_date).days)
    
    def check_potential_wash_sale(
        self,
        symbol: str,
        purchase_date: date,
    ) -> WashSaleCheckResult:
        """Check if a purchase could trigger wash sale for prior loss.
        
        Useful for warning users before they make a purchase that
        would trigger wash sale on a recent loss.
        """
        window_start = purchase_date - timedelta(days=self._wash_sale_config.lookback_days)
        window_end = purchase_date + timedelta(days=self._wash_sale_config.lookforward_days)
        
        symbols_to_check = self.get_substantially_identical(symbol)
        
        # Look for loss sales in the window
        for txn in self._transactions:
            if txn.is_purchase:
                continue
            
            if txn.symbol not in symbols_to_check:
                continue
            
            if window_start <= txn.date <= window_end:
                return WashSaleCheckResult(
                    is_wash_sale=True,
                    reason=f"Would trigger wash sale with loss sale on {txn.date}",
                )
        
        return WashSaleCheckResult(reason="No wash sale risk")
    
    def record_wash_sale(
        self,
        loss_sale: RealizedGain,
        replacement_lot: TaxLot,
        disallowed_loss: float,
    ) -> WashSale:
        """Record a wash sale and apply adjustments.
        
        Args:
            loss_sale: The realized loss that triggered wash sale.
            replacement_lot: The lot that caused the wash sale.
            disallowed_loss: Amount of loss disallowed.
            
        Returns:
            WashSale record.
        """
        wash_sale = WashSale(
            account_id=loss_sale.account_id,
            loss_sale_id=loss_sale.gain_id,
            replacement_lot_id=replacement_lot.lot_id,
            symbol=loss_sale.symbol,
            disallowed_loss=disallowed_loss,
            basis_adjustment=disallowed_loss,
            loss_sale_date=loss_sale.sale_date,
            replacement_date=replacement_lot.acquisition_date,
        )
        
        # Update the loss sale record
        loss_sale.is_wash_sale = True
        loss_sale.disallowed_loss = disallowed_loss
        
        # Update the replacement lot basis
        replacement_lot.adjusted_basis += disallowed_loss
        replacement_lot.wash_sale_adjustment += disallowed_loss
        
        self._wash_sales.append(wash_sale)
        
        logger.info(
            f"Recorded wash sale: ${disallowed_loss:.2f} disallowed, "
            f"basis added to lot {replacement_lot.lot_id}"
        )
        
        return wash_sale
    
    def get_wash_sales(
        self,
        symbol: Optional[str] = None,
        year: Optional[int] = None,
    ) -> list[WashSale]:
        """Get wash sale records, optionally filtered."""
        result = self._wash_sales
        
        if symbol:
            result = [ws for ws in result if ws.symbol == symbol]
        
        if year:
            result = [ws for ws in result if ws.loss_sale_date.year == year]
        
        return result
    
    def get_total_disallowed(
        self,
        year: Optional[int] = None,
    ) -> float:
        """Get total disallowed losses."""
        wash_sales = self.get_wash_sales(year=year)
        return sum(ws.disallowed_loss for ws in wash_sales)
    
    def get_pending_repurchase_dates(self, symbol: str) -> list[date]:
        """Get dates when it's safe to repurchase a symbol after loss sale.
        
        Returns dates 31 days after each loss sale of the symbol.
        """
        safe_dates = []
        
        for txn in self._transactions:
            if txn.is_purchase:
                continue
            if txn.symbol != symbol:
                continue
            
            safe_date = txn.date + timedelta(days=31)
            if safe_date > date.today():
                safe_dates.append(safe_date)
        
        return sorted(safe_dates)
    
    def is_symbol_in_wash_window(self, symbol: str) -> bool:
        """Check if a symbol is currently in a wash sale window.
        
        Returns True if buying this symbol now would trigger wash sale.
        """
        result = self.check_potential_wash_sale(symbol, date.today())
        return result.is_wash_sale
