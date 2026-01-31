"""Sector Rankings and Data.

Track and rank sector performance.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
import logging

from src.sectors.config import (
    SectorName,
    Trend,
    SECTOR_ETFS,
    SECTOR_CHARACTERISTICS,
    DEFAULT_SECTOR_CONFIG,
    SectorConfig,
)
from src.sectors.models import Sector, SectorPerformance

logger = logging.getLogger(__name__)


class SectorRankings:
    """Manages sector rankings and performance data.
    
    Example:
        rankings = SectorRankings()
        rankings.update_sector(Sector(
            name=SectorName.TECHNOLOGY,
            etf_symbol="XLK",
            change_1m=5.2,
            rs_ratio=1.05,
        ))
        
        top = rankings.get_top_sectors(5)
    """
    
    def __init__(self, config: Optional[SectorConfig] = None):
        self.config = config or DEFAULT_SECTOR_CONFIG
        self._sectors: dict[SectorName, Sector] = {}
        self._initialize_sectors()
    
    def _initialize_sectors(self) -> None:
        """Initialize all sectors."""
        for name, etf in SECTOR_ETFS.items():
            self._sectors[name] = Sector(
                name=name,
                etf_symbol=etf,
            )
    
    # =========================================================================
    # Sector CRUD
    # =========================================================================
    
    def update_sector(self, sector: Sector) -> None:
        """Update sector data."""
        self._sectors[sector.name] = sector
        self._recalculate_rankings()
    
    def get_sector(self, name: SectorName) -> Optional[Sector]:
        """Get sector by name."""
        return self._sectors.get(name)
    
    def get_all_sectors(self) -> list[Sector]:
        """Get all sectors."""
        return list(self._sectors.values())
    
    def update_prices(self, prices: dict[str, dict]) -> None:
        """Update sector prices from market data.
        
        Args:
            prices: Dict of ETF symbol -> price data.
        """
        benchmark_data = prices.get(self.config.benchmark, {})
        benchmark_change = benchmark_data.get("change_1m", 0)
        
        for name, sector in self._sectors.items():
            etf_data = prices.get(sector.etf_symbol, {})
            
            if etf_data:
                sector.price = etf_data.get("price", sector.price)
                sector.change_1d = etf_data.get("change_1d", 0)
                sector.change_1w = etf_data.get("change_1w", 0)
                sector.change_1m = etf_data.get("change_1m", 0)
                sector.change_3m = etf_data.get("change_3m", 0)
                sector.change_6m = etf_data.get("change_6m", 0)
                sector.change_ytd = etf_data.get("change_ytd", 0)
                sector.change_1y = etf_data.get("change_1y", 0)
                sector.volume = etf_data.get("volume", 0)
                sector.avg_volume = etf_data.get("avg_volume", 0)
                
                # Calculate relative strength
                if benchmark_change != 0:
                    sector.rs_ratio = (1 + sector.change_1m / 100) / (1 + benchmark_change / 100)
                
                # Determine trend
                sector.trend = self._determine_trend(sector)
                
                sector.updated_at = datetime.now(timezone.utc)
        
        self._recalculate_rankings()
    
    def _determine_trend(self, sector: Sector) -> Trend:
        """Determine sector trend."""
        # Simple trend based on multiple timeframes
        score = 0
        
        if sector.change_1w > 0:
            score += 1
        elif sector.change_1w < 0:
            score -= 1
        
        if sector.change_1m > 0:
            score += 1
        elif sector.change_1m < 0:
            score -= 1
        
        if sector.change_3m > 0:
            score += 1
        elif sector.change_3m < 0:
            score -= 1
        
        if score >= 2:
            return Trend.UP
        elif score <= -2:
            return Trend.DOWN
        return Trend.NEUTRAL
    
    def _recalculate_rankings(self) -> None:
        """Recalculate sector rankings."""
        # Sort by momentum score (composite of returns)
        sectors = list(self._sectors.values())
        
        # Calculate momentum score
        for sector in sectors:
            sector.momentum_score = (
                sector.change_1w * 0.2 +
                sector.change_1m * 0.4 +
                sector.change_3m * 0.3 +
                sector.rs_ratio * 10  # Boost for relative strength
            )
        
        # Rank by RS ratio
        sectors_by_rs = sorted(sectors, key=lambda s: s.rs_ratio, reverse=True)
        for i, sector in enumerate(sectors_by_rs):
            sector.rs_rank = i + 1
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def get_top_sectors(
        self,
        limit: int = 5,
        by: str = "momentum",
    ) -> list[Sector]:
        """Get top performing sectors.
        
        Args:
            limit: Number of sectors.
            by: Ranking criteria (momentum, rs, change_1m, etc.)
        """
        sectors = list(self._sectors.values())
        
        if by == "momentum":
            sectors.sort(key=lambda s: s.momentum_score, reverse=True)
        elif by == "rs":
            sectors.sort(key=lambda s: s.rs_ratio, reverse=True)
        elif by == "change_1d":
            sectors.sort(key=lambda s: s.change_1d, reverse=True)
        elif by == "change_1w":
            sectors.sort(key=lambda s: s.change_1w, reverse=True)
        elif by == "change_1m":
            sectors.sort(key=lambda s: s.change_1m, reverse=True)
        elif by == "change_3m":
            sectors.sort(key=lambda s: s.change_3m, reverse=True)
        
        return sectors[:limit]
    
    def get_bottom_sectors(
        self,
        limit: int = 5,
        by: str = "momentum",
    ) -> list[Sector]:
        """Get worst performing sectors."""
        top = self.get_top_sectors(limit=11, by=by)
        return list(reversed(top))[:limit]
    
    def get_outperformers(self) -> list[Sector]:
        """Get sectors outperforming benchmark."""
        return [s for s in self._sectors.values() if s.is_outperforming]
    
    def get_underperformers(self) -> list[Sector]:
        """Get sectors underperforming benchmark."""
        return [s for s in self._sectors.values() if not s.is_outperforming]
    
    def get_uptrending(self) -> list[Sector]:
        """Get sectors in uptrend."""
        return [s for s in self._sectors.values() if s.is_trending_up]
    
    def get_downtrending(self) -> list[Sector]:
        """Get sectors in downtrend."""
        return [s for s in self._sectors.values() if s.trend == Trend.DOWN]
    
    def get_cyclical_sectors(self) -> list[Sector]:
        """Get cyclical sectors."""
        return [
            s for s in self._sectors.values()
            if SECTOR_CHARACTERISTICS.get(s.name, {}).get("cyclical", False)
        ]
    
    def get_defensive_sectors(self) -> list[Sector]:
        """Get defensive sectors."""
        return [
            s for s in self._sectors.values()
            if SECTOR_CHARACTERISTICS.get(s.name, {}).get("type") == "defensive"
        ]
    
    # =========================================================================
    # Analysis
    # =========================================================================
    
    def get_performance_spread(self) -> dict:
        """Get spread between best and worst sectors."""
        sectors = list(self._sectors.values())
        
        best_1m = max(s.change_1m for s in sectors)
        worst_1m = min(s.change_1m for s in sectors)
        
        best_3m = max(s.change_3m for s in sectors)
        worst_3m = min(s.change_3m for s in sectors)
        
        return {
            "spread_1m": best_1m - worst_1m,
            "spread_3m": best_3m - worst_3m,
            "best_1m": best_1m,
            "worst_1m": worst_1m,
            "best_3m": best_3m,
            "worst_3m": worst_3m,
        }
    
    def get_sector_correlations(self) -> dict:
        """Get sector correlation summary."""
        # Simplified - just count trending together
        uptrending = len(self.get_uptrending())
        downtrending = len(self.get_downtrending())
        
        return {
            "sectors_uptrending": uptrending,
            "sectors_downtrending": downtrending,
            "sectors_neutral": 11 - uptrending - downtrending,
            "market_breadth": uptrending / 11 * 100,
        }


def generate_sample_rankings() -> SectorRankings:
    """Generate sample sector rankings data."""
    rankings = SectorRankings()
    
    # Sample price data
    sample_prices = {
        "XLK": {"price": 200.0, "change_1d": 1.2, "change_1w": 2.5, "change_1m": 5.0, "change_3m": 12.0, "change_6m": 18.0, "change_ytd": 15.0, "volume": 8000000},
        "XLV": {"price": 140.0, "change_1d": 0.3, "change_1w": 0.8, "change_1m": 2.0, "change_3m": 5.0, "change_6m": 8.0, "change_ytd": 6.0, "volume": 6000000},
        "XLF": {"price": 38.0, "change_1d": 0.8, "change_1w": 1.5, "change_1m": 3.5, "change_3m": 8.0, "change_6m": 12.0, "change_ytd": 10.0, "volume": 10000000},
        "XLY": {"price": 175.0, "change_1d": 1.0, "change_1w": 2.0, "change_1m": 4.0, "change_3m": 10.0, "change_6m": 15.0, "change_ytd": 12.0, "volume": 5000000},
        "XLP": {"price": 75.0, "change_1d": -0.2, "change_1w": 0.3, "change_1m": 1.0, "change_3m": 3.0, "change_6m": 5.0, "change_ytd": 4.0, "volume": 7000000},
        "XLE": {"price": 85.0, "change_1d": 1.5, "change_1w": 3.0, "change_1m": -2.0, "change_3m": -5.0, "change_6m": 2.0, "change_ytd": -3.0, "volume": 12000000},
        "XLU": {"price": 65.0, "change_1d": -0.5, "change_1w": -1.0, "change_1m": -0.5, "change_3m": 1.0, "change_6m": 3.0, "change_ytd": 2.0, "volume": 8000000},
        "XLRE": {"price": 38.0, "change_1d": 0.2, "change_1w": 0.5, "change_1m": 1.5, "change_3m": 4.0, "change_6m": 6.0, "change_ytd": 5.0, "volume": 4000000},
        "XLB": {"price": 82.0, "change_1d": 0.6, "change_1w": 1.2, "change_1m": 2.5, "change_3m": 6.0, "change_6m": 9.0, "change_ytd": 7.0, "volume": 5000000},
        "XLI": {"price": 115.0, "change_1d": 0.7, "change_1w": 1.8, "change_1m": 3.0, "change_3m": 7.0, "change_6m": 11.0, "change_ytd": 9.0, "volume": 6000000},
        "XLC": {"price": 78.0, "change_1d": 1.3, "change_1w": 2.2, "change_1m": 4.5, "change_3m": 11.0, "change_6m": 16.0, "change_ytd": 13.0, "volume": 5500000},
        "SPY": {"price": 480.0, "change_1d": 0.6, "change_1w": 1.5, "change_1m": 3.0, "change_3m": 7.0, "change_6m": 10.0, "change_ytd": 8.0, "volume": 50000000},
    }
    
    rankings.update_prices(sample_prices)
    return rankings
