"""Venue management for smart order routing."""

import random
from typing import Dict, List, Optional

from .config import FeeModel, VenueConfig, VenueType, VENUE_FEES
from .models import Venue, VenueMetrics


class VenueManager:
    """Manages trading venues and their quality metrics."""

    def __init__(self):
        self._venues: Dict[str, Venue] = {}
        self._metrics: Dict[str, VenueMetrics] = {}

    def add_venue(self, config: VenueConfig) -> Venue:
        venue = Venue(
            venue_id=config.venue_id,
            name=config.name,
            venue_type=config.venue_type.value,
            maker_fee=config.maker_fee,
            taker_fee=config.taker_fee,
            avg_latency_ms=config.avg_latency_ms,
            fill_rate=config.fill_rate,
            is_active=config.is_active,
        )
        self._venues[config.venue_id] = venue
        return venue

    def get_venue(self, venue_id: str) -> Optional[Venue]:
        return self._venues.get(venue_id)

    def list_venues(self, active_only: bool = True) -> List[Venue]:
        venues = list(self._venues.values())
        if active_only:
            venues = [v for v in venues if v.is_active]
        return venues

    def deactivate_venue(self, venue_id: str) -> bool:
        venue = self._venues.get(venue_id)
        if not venue:
            return False
        venue.is_active = False
        return True

    def get_lit_venues(self) -> List[Venue]:
        return [v for v in self.list_venues() if v.venue_type == VenueType.LIT_EXCHANGE.value]

    def get_dark_venues(self) -> List[Venue]:
        return [
            v for v in self.list_venues()
            if v.venue_type in (VenueType.DARK_POOL.value, VenueType.MIDPOINT.value)
        ]

    def get_cheapest_venue(self, is_maker: bool = False) -> Optional[Venue]:
        venues = self.list_venues()
        if not venues:
            return None
        if is_maker:
            return min(venues, key=lambda v: v.maker_fee)
        return min(venues, key=lambda v: v.taker_fee)

    def get_fastest_venue(self) -> Optional[Venue]:
        venues = self.list_venues()
        if not venues:
            return None
        return min(venues, key=lambda v: v.avg_latency_ms)

    def update_metrics(self, venue_id: str, metrics: VenueMetrics) -> None:
        self._metrics[venue_id] = metrics
        venue = self._venues.get(venue_id)
        if venue and metrics.orders_routed > 0:
            venue.fill_rate = metrics.fill_rate
            venue.avg_price_improvement = metrics.avg_price_improvement
            venue.adverse_selection_rate = metrics.avg_adverse_selection

    def get_metrics(self, venue_id: str) -> Optional[VenueMetrics]:
        return self._metrics.get(venue_id)

    def rank_venues(self, by: str = "fill_rate") -> List[Venue]:
        venues = self.list_venues()
        if by == "fill_rate":
            return sorted(venues, key=lambda v: v.fill_rate, reverse=True)
        elif by == "latency":
            return sorted(venues, key=lambda v: v.avg_latency_ms)
        elif by == "cost":
            return sorted(venues, key=lambda v: v.taker_fee)
        elif by == "price_improvement":
            return sorted(venues, key=lambda v: v.avg_price_improvement, reverse=True)
        return venues

    @staticmethod
    def create_default_venues() -> "VenueManager":
        """Create a VenueManager with standard US equity venues."""
        mgr = VenueManager()

        venues = [
            VenueConfig("NYSE", "New York Stock Exchange", VenueType.LIT_EXCHANGE,
                         FeeModel.MAKER_TAKER, -0.0020, 0.0030, 0.8, 0.85),
            VenueConfig("NASDAQ", "NASDAQ", VenueType.LIT_EXCHANGE,
                         FeeModel.MAKER_TAKER, -0.0025, 0.0030, 0.5, 0.88),
            VenueConfig("ARCA", "NYSE Arca", VenueType.LIT_EXCHANGE,
                         FeeModel.MAKER_TAKER, -0.0024, 0.0030, 0.6, 0.82),
            VenueConfig("BATS_BZX", "Cboe BZX", VenueType.LIT_EXCHANGE,
                         FeeModel.MAKER_TAKER, -0.0025, 0.0030, 0.4, 0.80),
            VenueConfig("BATS_BYX", "Cboe BYX", VenueType.LIT_EXCHANGE,
                         FeeModel.INVERTED, 0.0003, -0.0002, 0.5, 0.75),
            VenueConfig("IEX", "IEX Exchange", VenueType.LIT_EXCHANGE,
                         FeeModel.FLAT, 0.0000, 0.0009, 1.5, 0.78,
                         supports_peg=True, supports_midpoint=True),
            VenueConfig("MEMX", "MEMX Exchange", VenueType.LIT_EXCHANGE,
                         FeeModel.MAKER_TAKER, -0.0020, 0.0025, 0.3, 0.76),
            VenueConfig("DARK_MP", "Dark Midpoint Pool", VenueType.DARK_POOL,
                         FeeModel.FLAT, 0.0, 0.0010, 2.0, 0.45,
                         supports_hidden=True, supports_midpoint=True),
            VenueConfig("SIGMA_X", "Goldman Sigma X", VenueType.DARK_POOL,
                         FeeModel.FLAT, 0.0, 0.0008, 3.0, 0.40,
                         supports_hidden=True, supports_midpoint=True),
        ]

        for vc in venues:
            venue = mgr.add_venue(vc)
            # Set some realistic default metrics
            venue.avg_price_improvement = random.uniform(0.0001, 0.0005) if vc.venue_type == VenueType.DARK_POOL else 0.0
            venue.adverse_selection_rate = random.uniform(0.01, 0.05)
            venue.volume_24h = random.uniform(5_000_000, 50_000_000)

        return mgr
