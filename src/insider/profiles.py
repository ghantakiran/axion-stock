"""Insider Profiles.

Track individual insider trading history and patterns.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
import logging

from src.insider.config import TransactionType
from src.insider.models import (
    InsiderTransaction,
    InsiderProfile,
)
from src.insider.transactions import TransactionTracker

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages insider profiles.
    
    Example:
        manager = ProfileManager(tracker)
        
        # Build profiles
        manager.build_profiles()
        
        # Get profile
        profile = manager.get_profile("Tim Cook")
        print(f"Total buys: {profile.total_buys}")
    """
    
    def __init__(self, tracker: TransactionTracker):
        self.tracker = tracker
        self._profiles: dict[str, InsiderProfile] = {}
    
    def build_profiles(self) -> None:
        """Build profiles from transaction history."""
        self._profiles.clear()
        
        # Group transactions by insider
        insider_transactions: dict[str, list[InsiderTransaction]] = {}
        
        for transaction in self.tracker.get_all_transactions():
            name = transaction.insider_name
            if name not in insider_transactions:
                insider_transactions[name] = []
            insider_transactions[name].append(transaction)
        
        # Build profile for each insider
        for name, transactions in insider_transactions.items():
            profile = self._build_profile(name, transactions)
            self._profiles[name] = profile
    
    def _build_profile(
        self,
        name: str,
        transactions: list[InsiderTransaction],
    ) -> InsiderProfile:
        """Build profile from transactions."""
        # Get unique companies and titles
        companies = list(set(t.symbol for t in transactions))
        titles = {t.symbol: t.insider_title for t in transactions}
        
        # Count transactions
        buys = [t for t in transactions if t.is_buy]
        sells = [t for t in transactions if t.is_sell]
        
        # Get dates
        dates = [t.transaction_date for t in transactions if t.transaction_date]
        last_date = max(dates) if dates else None
        
        # Recent transactions
        recent = sorted(
            transactions,
            key=lambda t: t.transaction_date or date.min,
            reverse=True
        )[:10]
        
        return InsiderProfile(
            name=name,
            companies=companies,
            titles=titles,
            total_transactions=len(transactions),
            total_buys=len(buys),
            total_sells=len(sells),
            total_buy_value=sum(t.value for t in buys),
            total_sell_value=sum(t.value for t in sells),
            last_transaction_date=last_date,
            recent_transactions=recent,
        )
    
    def get_profile(self, name: str) -> Optional[InsiderProfile]:
        """Get profile by insider name."""
        return self._profiles.get(name)
    
    def get_all_profiles(self) -> list[InsiderProfile]:
        """Get all profiles."""
        return list(self._profiles.values())
    
    def search_profiles(self, query: str) -> list[InsiderProfile]:
        """Search profiles by name."""
        query_lower = query.lower()
        return [
            p for p in self._profiles.values()
            if query_lower in p.name.lower()
        ]
    
    def get_top_buyers(self, limit: int = 10) -> list[InsiderProfile]:
        """Get insiders with highest buy value."""
        profiles = list(self._profiles.values())
        profiles.sort(key=lambda p: p.total_buy_value, reverse=True)
        return profiles[:limit]
    
    def get_top_sellers(self, limit: int = 10) -> list[InsiderProfile]:
        """Get insiders with highest sell value."""
        profiles = list(self._profiles.values())
        profiles.sort(key=lambda p: p.total_sell_value, reverse=True)
        return profiles[:limit]
    
    def get_most_active(self, limit: int = 10) -> list[InsiderProfile]:
        """Get most active insiders by transaction count."""
        profiles = list(self._profiles.values())
        profiles.sort(key=lambda p: p.total_transactions, reverse=True)
        return profiles[:limit]
    
    def get_recent_activity(
        self,
        name: str,
        days: int = 90,
    ) -> list[InsiderTransaction]:
        """Get recent activity for an insider."""
        return self.tracker.get_by_insider(name, days=days)
    
    def get_companies_for_insider(self, name: str) -> list[str]:
        """Get companies associated with an insider."""
        profile = self._profiles.get(name)
        return profile.companies if profile else []
    
    def get_insiders_for_company(self, symbol: str) -> list[InsiderProfile]:
        """Get insiders associated with a company."""
        return [
            p for p in self._profiles.values()
            if symbol in p.companies
        ]
    
    def calculate_success_rate(
        self,
        name: str,
        price_data: dict[str, dict[date, float]],
        hold_days: int = 30,
    ) -> Optional[float]:
        """Calculate insider's trading success rate.
        
        Args:
            name: Insider name.
            price_data: Historical prices {symbol: {date: price}}.
            hold_days: Days to hold for return calculation.
            
        Returns:
            Success rate (0-100) or None if insufficient data.
        """
        profile = self._profiles.get(name)
        if not profile:
            return None
        
        successful = 0
        total = 0
        
        for txn in profile.recent_transactions:
            if not txn.transaction_date or not txn.is_buy:
                continue
            
            symbol_prices = price_data.get(txn.symbol, {})
            buy_price = txn.price
            
            # Get price after hold period
            target_date = txn.transaction_date + timedelta(days=hold_days)
            future_price = symbol_prices.get(target_date)
            
            if future_price and buy_price > 0:
                total += 1
                if future_price > buy_price:
                    successful += 1
        
        if total == 0:
            return None
        
        return (successful / total) * 100
