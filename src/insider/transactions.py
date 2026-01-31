"""Insider Transaction Tracking.

Track and analyze insider trading transactions.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
import logging

from src.insider.config import (
    InsiderType,
    TransactionType,
    InsiderConfig,
    DEFAULT_INSIDER_CONFIG,
    TITLE_TO_TYPE,
)
from src.insider.models import (
    InsiderTransaction,
    InsiderSummary,
)

logger = logging.getLogger(__name__)


class TransactionTracker:
    """Tracks insider trading transactions.
    
    Example:
        tracker = TransactionTracker()
        
        # Add transaction
        tracker.add_transaction(InsiderTransaction(
            symbol="AAPL",
            insider_name="Tim Cook",
            insider_type=InsiderType.CEO,
            transaction_type=TransactionType.BUY,
            shares=10000,
            price=185.0,
            value=1850000,
        ))
        
        # Get recent buys
        buys = tracker.get_recent_buys(days=30)
    """
    
    def __init__(self, config: Optional[InsiderConfig] = None):
        self.config = config or DEFAULT_INSIDER_CONFIG
        self._transactions: dict[str, InsiderTransaction] = {}
        self._by_symbol: dict[str, list[str]] = {}  # symbol -> transaction_ids
        self._by_insider: dict[str, list[str]] = {}  # insider_name -> transaction_ids
    
    # =========================================================================
    # Transaction CRUD
    # =========================================================================
    
    def add_transaction(self, transaction: InsiderTransaction) -> None:
        """Add an insider transaction."""
        # Calculate value if not set
        if transaction.value == 0 and transaction.shares > 0 and transaction.price > 0:
            transaction.value = transaction.shares * transaction.price
        
        # Infer insider type from title if not set
        if transaction.insider_type == InsiderType.OTHER and transaction.insider_title:
            transaction.insider_type = self._infer_insider_type(transaction.insider_title)
        
        self._transactions[transaction.transaction_id] = transaction
        
        # Index by symbol
        if transaction.symbol not in self._by_symbol:
            self._by_symbol[transaction.symbol] = []
        self._by_symbol[transaction.symbol].append(transaction.transaction_id)
        
        # Index by insider
        if transaction.insider_name not in self._by_insider:
            self._by_insider[transaction.insider_name] = []
        self._by_insider[transaction.insider_name].append(transaction.transaction_id)
    
    def get_transaction(self, transaction_id: str) -> Optional[InsiderTransaction]:
        """Get transaction by ID."""
        return self._transactions.get(transaction_id)
    
    def get_all_transactions(self) -> list[InsiderTransaction]:
        """Get all transactions."""
        return list(self._transactions.values())
    
    def _infer_insider_type(self, title: str) -> InsiderType:
        """Infer insider type from title."""
        title_lower = title.lower()
        
        for key, insider_type in TITLE_TO_TYPE.items():
            if key in title_lower:
                return insider_type
        
        return InsiderType.OTHER
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def get_by_symbol(
        self,
        symbol: str,
        days: int = 90,
        transaction_type: Optional[TransactionType] = None,
    ) -> list[InsiderTransaction]:
        """Get transactions for a symbol."""
        transaction_ids = self._by_symbol.get(symbol, [])
        transactions = [self._transactions[tid] for tid in transaction_ids]
        
        # Filter by date
        cutoff = date.today() - timedelta(days=days)
        transactions = [
            t for t in transactions
            if t.transaction_date and t.transaction_date >= cutoff
        ]
        
        # Filter by type
        if transaction_type:
            transactions = [t for t in transactions if t.transaction_type == transaction_type]
        
        # Sort by date
        transactions.sort(key=lambda t: t.transaction_date or date.min, reverse=True)
        
        return transactions
    
    def get_by_insider(
        self,
        insider_name: str,
        days: int = 365,
    ) -> list[InsiderTransaction]:
        """Get transactions by insider."""
        transaction_ids = self._by_insider.get(insider_name, [])
        transactions = [self._transactions[tid] for tid in transaction_ids]
        
        # Filter by date
        cutoff = date.today() - timedelta(days=days)
        transactions = [
            t for t in transactions
            if t.transaction_date and t.transaction_date >= cutoff
        ]
        
        transactions.sort(key=lambda t: t.transaction_date or date.min, reverse=True)
        return transactions
    
    def get_recent_buys(
        self,
        days: int = 30,
        min_value: float = 0,
    ) -> list[InsiderTransaction]:
        """Get recent buy transactions."""
        cutoff = date.today() - timedelta(days=days)
        
        buys = [
            t for t in self._transactions.values()
            if t.transaction_type == TransactionType.BUY
            and t.transaction_date and t.transaction_date >= cutoff
            and t.value >= min_value
        ]
        
        buys.sort(key=lambda t: t.value, reverse=True)
        return buys
    
    def get_recent_sells(
        self,
        days: int = 30,
        min_value: float = 0,
    ) -> list[InsiderTransaction]:
        """Get recent sell transactions."""
        cutoff = date.today() - timedelta(days=days)
        
        sells = [
            t for t in self._transactions.values()
            if t.transaction_type == TransactionType.SELL
            and t.transaction_date and t.transaction_date >= cutoff
            and t.value >= min_value
        ]
        
        sells.sort(key=lambda t: t.value, reverse=True)
        return sells
    
    def get_large_transactions(
        self,
        min_value: float = 500_000,
        days: int = 30,
    ) -> list[InsiderTransaction]:
        """Get large transactions."""
        cutoff = date.today() - timedelta(days=days)
        
        large = [
            t for t in self._transactions.values()
            if t.value >= min_value
            and t.transaction_date and t.transaction_date >= cutoff
        ]
        
        large.sort(key=lambda t: t.value, reverse=True)
        return large
    
    def get_ceo_transactions(
        self,
        days: int = 90,
        buys_only: bool = True,
    ) -> list[InsiderTransaction]:
        """Get CEO transactions."""
        cutoff = date.today() - timedelta(days=days)
        
        ceo_txns = [
            t for t in self._transactions.values()
            if t.insider_type == InsiderType.CEO
            and t.transaction_date and t.transaction_date >= cutoff
        ]
        
        if buys_only:
            ceo_txns = [t for t in ceo_txns if t.is_buy]
        
        ceo_txns.sort(key=lambda t: t.transaction_date or date.min, reverse=True)
        return ceo_txns
    
    # =========================================================================
    # Summaries
    # =========================================================================
    
    def get_summary(self, symbol: str, days: int = 90) -> InsiderSummary:
        """Get insider activity summary for a symbol."""
        transactions = self.get_by_symbol(symbol, days=days)
        
        if not transactions:
            return InsiderSummary(symbol=symbol)
        
        buys = [t for t in transactions if t.is_buy]
        sells = [t for t in transactions if t.is_sell]
        
        unique_insiders = set(t.insider_name for t in transactions)
        unique_buyers = set(t.insider_name for t in buys)
        
        dates = [t.transaction_date for t in transactions if t.transaction_date]
        
        return InsiderSummary(
            symbol=symbol,
            company_name=transactions[0].company_name if transactions else "",
            total_transactions=len(transactions),
            buy_count=len(buys),
            sell_count=len(sells),
            total_buy_value=sum(t.value for t in buys),
            total_sell_value=sum(t.value for t in sells),
            net_value=sum(t.value for t in buys) - sum(t.value for t in sells),
            unique_insiders=len(unique_insiders),
            unique_buyers=len(unique_buyers),
            first_transaction=min(dates) if dates else None,
            last_transaction=max(dates) if dates else None,
        )
    
    def get_market_summary(self, days: int = 30) -> dict:
        """Get market-wide insider activity summary."""
        cutoff = date.today() - timedelta(days=days)
        
        recent = [
            t for t in self._transactions.values()
            if t.transaction_date and t.transaction_date >= cutoff
        ]
        
        buys = [t for t in recent if t.is_buy]
        sells = [t for t in recent if t.is_sell]
        
        return {
            "total_transactions": len(recent),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "total_buy_value": sum(t.value for t in buys),
            "total_sell_value": sum(t.value for t in sells),
            "net_value": sum(t.value for t in buys) - sum(t.value for t in sells),
            "unique_companies": len(set(t.symbol for t in recent)),
            "unique_insiders": len(set(t.insider_name for t in recent)),
            "buy_sell_ratio": len(buys) / len(sells) if sells else float('inf'),
        }
    
    def get_top_bought(self, days: int = 30, limit: int = 10) -> list[tuple[str, float]]:
        """Get top bought symbols by value."""
        cutoff = date.today() - timedelta(days=days)
        
        buys_by_symbol: dict[str, float] = {}
        
        for t in self._transactions.values():
            if t.is_buy and t.transaction_date and t.transaction_date >= cutoff:
                buys_by_symbol[t.symbol] = buys_by_symbol.get(t.symbol, 0) + t.value
        
        sorted_symbols = sorted(buys_by_symbol.items(), key=lambda x: x[1], reverse=True)
        return sorted_symbols[:limit]
    
    def get_top_sold(self, days: int = 30, limit: int = 10) -> list[tuple[str, float]]:
        """Get top sold symbols by value."""
        cutoff = date.today() - timedelta(days=days)
        
        sells_by_symbol: dict[str, float] = {}
        
        for t in self._transactions.values():
            if t.is_sell and t.transaction_date and t.transaction_date >= cutoff:
                sells_by_symbol[t.symbol] = sells_by_symbol.get(t.symbol, 0) + t.value
        
        sorted_symbols = sorted(sells_by_symbol.items(), key=lambda x: x[1], reverse=True)
        return sorted_symbols[:limit]


def generate_sample_transactions() -> TransactionTracker:
    """Generate sample transaction data."""
    tracker = TransactionTracker()
    today = date.today()
    
    # Sample transactions
    sample_data = [
        # AAPL
        ("AAPL", "Apple Inc.", "Tim Cook", "CEO", InsiderType.CEO, TransactionType.BUY, 
         today - timedelta(days=5), 50000, 185.0),
        ("AAPL", "Apple Inc.", "Luca Maestri", "CFO", InsiderType.CFO, TransactionType.BUY,
         today - timedelta(days=7), 25000, 183.0),
        ("AAPL", "Apple Inc.", "Jeff Williams", "COO", InsiderType.COO, TransactionType.BUY,
         today - timedelta(days=8), 30000, 182.0),
        
        # NVDA
        ("NVDA", "NVIDIA Corp.", "Jensen Huang", "CEO", InsiderType.CEO, TransactionType.SELL,
         today - timedelta(days=3), 100000, 800.0),
        ("NVDA", "NVIDIA Corp.", "Colette Kress", "CFO", InsiderType.CFO, TransactionType.SELL,
         today - timedelta(days=10), 20000, 750.0),
        
        # MSFT
        ("MSFT", "Microsoft Corp.", "Satya Nadella", "CEO", InsiderType.CEO, TransactionType.BUY,
         today - timedelta(days=12), 15000, 378.0),
        ("MSFT", "Microsoft Corp.", "Amy Hood", "CFO", InsiderType.CFO, TransactionType.BUY,
         today - timedelta(days=14), 10000, 375.0),
        
        # GOOGL
        ("GOOGL", "Alphabet Inc.", "Sundar Pichai", "CEO", InsiderType.CEO, TransactionType.SELL,
         today - timedelta(days=20), 50000, 140.0),
        
        # Small cap example
        ("XYZ", "XYZ Corp", "John Smith", "CEO", InsiderType.CEO, TransactionType.BUY,
         today - timedelta(days=2), 100000, 25.0),
        ("XYZ", "XYZ Corp", "Jane Doe", "CFO", InsiderType.CFO, TransactionType.BUY,
         today - timedelta(days=3), 75000, 24.5),
        ("XYZ", "XYZ Corp", "Bob Wilson", "Director", InsiderType.DIRECTOR, TransactionType.BUY,
         today - timedelta(days=4), 50000, 24.0),
    ]
    
    for symbol, company, name, title, itype, ttype, tdate, shares, price in sample_data:
        tracker.add_transaction(InsiderTransaction(
            symbol=symbol,
            company_name=company,
            insider_name=name,
            insider_title=title,
            insider_type=itype,
            transaction_type=ttype,
            transaction_date=tdate,
            shares=shares,
            price=price,
            value=shares * price,
        ))
    
    return tracker
