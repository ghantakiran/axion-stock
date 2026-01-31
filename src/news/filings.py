"""SEC Filings Tracking.

Monitors SEC filings including 10-K, 10-Q, 8-K, Form 4, and 13F.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional
import logging

from src.news.config import (
    FilingType,
    InsiderTransactionType,
    FilingsConfig,
    NewsConfig,
    DEFAULT_NEWS_CONFIG,
    HIGH_IMPORTANCE_FILINGS,
)
from src.news.models import SECFiling, InsiderTransaction

logger = logging.getLogger(__name__)


class SECFilingsTracker:
    """Tracks SEC filings and insider transactions.
    
    Features:
    - Filing monitoring by type
    - Insider transaction tracking (Form 4)
    - 13F institutional holdings
    - Symbol-based filtering
    """
    
    def __init__(self, config: Optional[NewsConfig] = None):
        self.config = config or DEFAULT_NEWS_CONFIG
        self._filings_config = self.config.filings
        self._filings: dict[str, SECFiling] = {}  # filing_id -> filing
        self._symbol_index: dict[str, set[str]] = {}  # symbol -> filing_ids
        self._type_index: dict[FilingType, set[str]] = {}  # type -> filing_ids
        self._insider_txns: dict[str, InsiderTransaction] = {}  # txn_id -> txn
    
    def add_filing(self, filing: SECFiling) -> SECFiling:
        """Add an SEC filing.
        
        Args:
            filing: SECFiling to add.
            
        Returns:
            The added filing.
        """
        self._filings[filing.filing_id] = filing
        
        # Index by symbol
        if filing.symbol:
            if filing.symbol not in self._symbol_index:
                self._symbol_index[filing.symbol] = set()
            self._symbol_index[filing.symbol].add(filing.filing_id)
        
        # Index by type
        if filing.form_type not in self._type_index:
            self._type_index[filing.form_type] = set()
        self._type_index[filing.form_type].add(filing.filing_id)
        
        logger.debug(f"Added filing: {filing.symbol} {filing.form_type.value} on {filing.filed_date}")
        return filing
    
    def add_insider_transaction(self, txn: InsiderTransaction) -> InsiderTransaction:
        """Add an insider transaction (from Form 4).
        
        Args:
            txn: InsiderTransaction to add.
            
        Returns:
            The added transaction.
        """
        self._insider_txns[txn.transaction_id] = txn
        
        logger.debug(
            f"Added insider transaction: {txn.insider_name} "
            f"{txn.transaction_type.value} {txn.shares} {txn.symbol}"
        )
        return txn
    
    def get_filing(self, filing_id: str) -> Optional[SECFiling]:
        """Get a filing by ID."""
        return self._filings.get(filing_id)
    
    def get_recent_filings(
        self,
        symbols: Optional[list[str]] = None,
        form_types: Optional[list[FilingType]] = None,
        days: int = 30,
        limit: int = 50,
    ) -> list[SECFiling]:
        """Get recent SEC filings.
        
        Args:
            symbols: Filter by symbols.
            form_types: Filter by form types.
            days: Days to look back.
            limit: Maximum filings to return.
            
        Returns:
            List of recent filings.
        """
        cutoff = date.today() - timedelta(days=days)
        form_types = form_types or self._filings_config.tracked_forms
        
        # Get candidate filing IDs
        if symbols:
            candidate_ids = set()
            for symbol in symbols:
                candidate_ids.update(self._symbol_index.get(symbol, set()))
        else:
            candidate_ids = set(self._filings.keys())
        
        # Filter by type
        if form_types:
            type_ids = set()
            for ft in form_types:
                type_ids.update(self._type_index.get(ft, set()))
            candidate_ids &= type_ids
        
        # Get and filter filings
        filings = []
        for fid in candidate_ids:
            filing = self._filings.get(fid)
            if filing and filing.filed_date >= cutoff:
                filings.append(filing)
        
        # Sort by date (newest first)
        filings.sort(key=lambda f: f.filed_date, reverse=True)
        return filings[:limit]
    
    def get_for_symbol(
        self,
        symbol: str,
        form_types: Optional[list[FilingType]] = None,
        limit: int = 20,
    ) -> list[SECFiling]:
        """Get filings for a specific symbol.
        
        Args:
            symbol: Stock symbol.
            form_types: Filter by form types.
            limit: Maximum filings to return.
            
        Returns:
            List of filings for symbol.
        """
        return self.get_recent_filings(
            symbols=[symbol],
            form_types=form_types,
            days=365,
            limit=limit,
        )
    
    def get_insider_transactions(
        self,
        symbols: Optional[list[str]] = None,
        transaction_types: Optional[list[InsiderTransactionType]] = None,
        days: int = 30,
        min_value: float = 0.0,
        limit: int = 50,
    ) -> list[InsiderTransaction]:
        """Get insider transactions.
        
        Args:
            symbols: Filter by symbols.
            transaction_types: Filter by transaction types.
            days: Days to look back.
            min_value: Minimum transaction value.
            limit: Maximum transactions to return.
            
        Returns:
            List of insider transactions.
        """
        cutoff = date.today() - timedelta(days=days)
        
        txns = []
        for txn in self._insider_txns.values():
            if txn.transaction_date < cutoff:
                continue
            
            if symbols and txn.symbol not in symbols:
                continue
            
            if transaction_types and txn.transaction_type not in transaction_types:
                continue
            
            if min_value > 0 and (txn.value or 0) < min_value:
                continue
            
            txns.append(txn)
        
        # Sort by date (newest first)
        txns.sort(key=lambda t: t.transaction_date, reverse=True)
        return txns[:limit]
    
    def get_insider_buys(
        self,
        days: int = 30,
        min_value: float = 10000,
    ) -> list[InsiderTransaction]:
        """Get significant insider buys.
        
        Args:
            days: Days to look back.
            min_value: Minimum transaction value.
            
        Returns:
            List of insider buy transactions.
        """
        return self.get_insider_transactions(
            transaction_types=[InsiderTransactionType.BUY],
            days=days,
            min_value=min_value,
        )
    
    def get_insider_sells(
        self,
        days: int = 30,
        min_value: float = 10000,
    ) -> list[InsiderTransaction]:
        """Get significant insider sells.
        
        Args:
            days: Days to look back.
            min_value: Minimum transaction value.
            
        Returns:
            List of insider sell transactions.
        """
        return self.get_insider_transactions(
            transaction_types=[InsiderTransactionType.SELL],
            days=days,
            min_value=min_value,
        )
    
    def get_8k_filings(
        self,
        symbols: Optional[list[str]] = None,
        days: int = 30,
    ) -> list[SECFiling]:
        """Get recent 8-K filings (material events).
        
        Args:
            symbols: Filter by symbols.
            days: Days to look back.
            
        Returns:
            List of 8-K filings.
        """
        return self.get_recent_filings(
            symbols=symbols,
            form_types=[FilingType.FORM_8K],
            days=days,
        )
    
    def get_quarterly_filings(
        self,
        symbol: str,
        quarters: int = 8,
    ) -> list[SECFiling]:
        """Get 10-Q and 10-K filings for a symbol.
        
        Args:
            symbol: Stock symbol.
            quarters: Number of quarters to include.
            
        Returns:
            List of quarterly/annual filings.
        """
        filings = self.get_for_symbol(
            symbol=symbol,
            form_types=[FilingType.FORM_10Q, FilingType.FORM_10K],
            limit=quarters,
        )
        return filings
    
    def get_insider_summary(self, symbol: str, days: int = 90) -> dict:
        """Get insider transaction summary for a symbol.
        
        Args:
            symbol: Stock symbol.
            days: Days to analyze.
            
        Returns:
            Summary dict with buy/sell totals.
        """
        txns = self.get_insider_transactions(symbols=[symbol], days=days, limit=100)
        
        buys = [t for t in txns if t.is_purchase]
        sells = [t for t in txns if t.is_sale]
        
        buy_value = sum(t.value or 0 for t in buys)
        sell_value = sum(t.value or 0 for t in sells)
        buy_shares = sum(t.shares for t in buys)
        sell_shares = sum(t.shares for t in sells)
        
        return {
            "symbol": symbol,
            "days": days,
            "total_transactions": len(txns),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "buy_shares": buy_shares,
            "sell_shares": sell_shares,
            "buy_value": buy_value,
            "sell_value": sell_value,
            "net_shares": buy_shares - sell_shares,
            "net_value": buy_value - sell_value,
            "unique_insiders": len(set(t.insider_name for t in txns)),
        }
    
    def is_high_importance(self, filing: SECFiling) -> bool:
        """Check if filing is high importance."""
        return filing.form_type in HIGH_IMPORTANCE_FILINGS
