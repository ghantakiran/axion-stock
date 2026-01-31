"""Institutional Holdings Tracking.

Track 13F filings and institutional ownership changes.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
import logging

from src.insider.config import (
    InstitutionType,
    InstitutionalConfig,
    DEFAULT_INSTITUTIONAL_CONFIG,
)
from src.insider.models import (
    InstitutionalHolding,
    InstitutionalSummary,
)

logger = logging.getLogger(__name__)


class InstitutionalTracker:
    """Tracks institutional holdings from 13F filings.
    
    Example:
        tracker = InstitutionalTracker()
        
        # Add holding
        tracker.add_holding(InstitutionalHolding(
            institution_name="Berkshire Hathaway",
            symbol="AAPL",
            shares=905_000_000,
            value=167_000_000_000,
        ))
        
        # Get top holders
        holders = tracker.get_top_holders("AAPL")
    """
    
    def __init__(self, config: Optional[InstitutionalConfig] = None):
        self.config = config or DEFAULT_INSTITUTIONAL_CONFIG
        self._holdings: dict[str, InstitutionalHolding] = {}
        self._by_symbol: dict[str, list[str]] = {}
        self._by_institution: dict[str, list[str]] = {}
    
    # =========================================================================
    # Holdings CRUD
    # =========================================================================
    
    def add_holding(self, holding: InstitutionalHolding) -> None:
        """Add an institutional holding."""
        self._holdings[holding.holding_id] = holding
        
        # Index by symbol
        if holding.symbol not in self._by_symbol:
            self._by_symbol[holding.symbol] = []
        self._by_symbol[holding.symbol].append(holding.holding_id)
        
        # Index by institution
        if holding.institution_name not in self._by_institution:
            self._by_institution[holding.institution_name] = []
        self._by_institution[holding.institution_name].append(holding.holding_id)
    
    def get_holding(self, holding_id: str) -> Optional[InstitutionalHolding]:
        """Get holding by ID."""
        return self._holdings.get(holding_id)
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def get_holders(self, symbol: str) -> list[InstitutionalHolding]:
        """Get all institutional holders of a symbol."""
        holding_ids = self._by_symbol.get(symbol, [])
        holdings = [self._holdings[hid] for hid in holding_ids]
        holdings.sort(key=lambda h: h.value, reverse=True)
        return holdings
    
    def get_top_holders(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[InstitutionalHolding]:
        """Get top institutional holders by value."""
        return self.get_holders(symbol)[:limit]
    
    def get_institution_holdings(
        self,
        institution_name: str,
    ) -> list[InstitutionalHolding]:
        """Get all holdings for an institution."""
        holding_ids = self._by_institution.get(institution_name, [])
        holdings = [self._holdings[hid] for hid in holding_ids]
        holdings.sort(key=lambda h: h.value, reverse=True)
        return holdings
    
    def get_new_positions(self, symbol: Optional[str] = None) -> list[InstitutionalHolding]:
        """Get new institutional positions."""
        holdings = list(self._holdings.values())
        
        if symbol:
            holdings = [h for h in holdings if h.symbol == symbol]
        
        return [h for h in holdings if h.is_new_position]
    
    def get_sold_out(self, symbol: Optional[str] = None) -> list[InstitutionalHolding]:
        """Get positions that were completely sold."""
        holdings = list(self._holdings.values())
        
        if symbol:
            holdings = [h for h in holdings if h.symbol == symbol]
        
        return [h for h in holdings if h.is_sold_out]
    
    def get_increases(
        self,
        symbol: Optional[str] = None,
        min_change_pct: float = 10.0,
    ) -> list[InstitutionalHolding]:
        """Get positions that increased."""
        holdings = list(self._holdings.values())
        
        if symbol:
            holdings = [h for h in holdings if h.symbol == symbol]
        
        increases = [
            h for h in holdings
            if h.shares_change_pct >= min_change_pct
            and not h.is_new_position
        ]
        
        increases.sort(key=lambda h: h.shares_change_pct, reverse=True)
        return increases
    
    def get_decreases(
        self,
        symbol: Optional[str] = None,
        min_change_pct: float = 10.0,
    ) -> list[InstitutionalHolding]:
        """Get positions that decreased."""
        holdings = list(self._holdings.values())
        
        if symbol:
            holdings = [h for h in holdings if h.symbol == symbol]
        
        decreases = [
            h for h in holdings
            if h.shares_change_pct <= -min_change_pct
            and not h.is_sold_out
        ]
        
        decreases.sort(key=lambda h: h.shares_change_pct)
        return decreases
    
    # =========================================================================
    # Summaries
    # =========================================================================
    
    def get_summary(self, symbol: str) -> InstitutionalSummary:
        """Get institutional ownership summary for a symbol."""
        holdings = self.get_holders(symbol)
        
        if not holdings:
            return InstitutionalSummary(symbol=symbol)
        
        new_positions = [h for h in holdings if h.is_new_position]
        increases = [h for h in holdings if h.is_increase and not h.is_new_position]
        decreases = [h for h in holdings if h.is_decrease and not h.is_sold_out]
        sold_out = [h for h in holdings if h.is_sold_out]
        
        top_holders = [h.institution_name for h in holdings[:5]]
        
        return InstitutionalSummary(
            symbol=symbol,
            total_institutions=len(holdings),
            total_shares=sum(h.shares for h in holdings),
            total_value=sum(h.value for h in holdings),
            new_positions=len(new_positions),
            increased_positions=len(increases),
            decreased_positions=len(decreases),
            sold_out=len(sold_out),
            top_holders=top_holders,
        )
    
    def get_most_accumulated(self, limit: int = 10) -> list[tuple[str, float]]:
        """Get symbols with most institutional accumulation."""
        accumulation_by_symbol: dict[str, float] = {}
        
        for holding in self._holdings.values():
            if holding.is_increase or holding.is_new_position:
                symbol = holding.symbol
                change = holding.value_change if holding.value_change > 0 else holding.value
                accumulation_by_symbol[symbol] = accumulation_by_symbol.get(symbol, 0) + change
        
        sorted_symbols = sorted(
            accumulation_by_symbol.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_symbols[:limit]
    
    def get_most_distributed(self, limit: int = 10) -> list[tuple[str, float]]:
        """Get symbols with most institutional distribution."""
        distribution_by_symbol: dict[str, float] = {}
        
        for holding in self._holdings.values():
            if holding.is_decrease or holding.is_sold_out:
                symbol = holding.symbol
                change = abs(holding.value_change) if holding.value_change < 0 else holding.value
                distribution_by_symbol[symbol] = distribution_by_symbol.get(symbol, 0) + change
        
        sorted_symbols = sorted(
            distribution_by_symbol.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_symbols[:limit]


def generate_sample_institutional() -> InstitutionalTracker:
    """Generate sample institutional holdings data."""
    tracker = InstitutionalTracker()
    today = date.today()
    
    # Sample AAPL holdings
    aapl_holdings = [
        ("Berkshire Hathaway", InstitutionType.OTHER, 905_000_000, 167_000_000_000, 0, 0),
        ("Vanguard Group", InstitutionType.MUTUAL_FUND, 1_300_000_000, 240_000_000_000, 50_000_000, 4.0),
        ("BlackRock", InstitutionType.MUTUAL_FUND, 1_000_000_000, 185_000_000_000, -20_000_000, -2.0),
        ("State Street", InstitutionType.MUTUAL_FUND, 600_000_000, 111_000_000_000, 10_000_000, 1.7),
        ("Fidelity", InstitutionType.MUTUAL_FUND, 400_000_000, 74_000_000_000, 25_000_000, 6.7),
    ]
    
    for name, itype, shares, value, change, change_pct in aapl_holdings:
        tracker.add_holding(InstitutionalHolding(
            institution_name=name,
            institution_type=itype,
            symbol="AAPL",
            company_name="Apple Inc.",
            shares=shares,
            value=value,
            shares_change=change,
            shares_change_pct=change_pct,
            report_date=today - timedelta(days=45),
            filing_date=today - timedelta(days=30),
        ))
    
    # Sample NVDA holdings with new position
    tracker.add_holding(InstitutionalHolding(
        institution_name="ARK Invest",
        institution_type=InstitutionType.HEDGE_FUND,
        symbol="NVDA",
        company_name="NVIDIA Corp.",
        shares=5_000_000,
        value=4_000_000_000,
        shares_change=5_000_000,
        shares_change_pct=100.0,
        is_new_position=True,
        report_date=today - timedelta(days=45),
        filing_date=today - timedelta(days=30),
    ))
    
    # Sample sold out position
    tracker.add_holding(InstitutionalHolding(
        institution_name="Tiger Global",
        institution_type=InstitutionType.HEDGE_FUND,
        symbol="META",
        company_name="Meta Platforms",
        shares=0,
        value=0,
        shares_change=-10_000_000,
        shares_change_pct=-100.0,
        is_sold_out=True,
        report_date=today - timedelta(days=45),
        filing_date=today - timedelta(days=30),
    ))
    
    return tracker
