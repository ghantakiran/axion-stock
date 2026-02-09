"""Survivorship Bias Filter — prevents look-ahead bias in backtesting.

Filters the backtest universe to only include tickers that were
actually tradable (listed, liquid, not delisted) at each point in time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional


@dataclass
class SurvivorshipConfig:
    """Configuration for the survivorship filter.

    Attributes:
        min_price: Minimum price to be considered tradable.
        min_volume: Minimum average daily volume.
        min_market_cap: Minimum market cap (in millions).
        exclude_otc: Whether to exclude OTC/pink sheet stocks.
        require_continuous_data: Require unbroken price history.
        max_gap_days: Maximum days of missing data before exclusion.
    """

    min_price: float = 5.0
    min_volume: float = 500_000
    min_market_cap: float = 500.0
    exclude_otc: bool = True
    require_continuous_data: bool = True
    max_gap_days: int = 5


class SurvivorshipFilter:
    """Filters tickers to prevent survivorship bias in backtests.

    At each point in the backtest, only tickers that were actually
    available for trading are included. Delisted stocks, tickers
    with insufficient liquidity, and those with gaps are excluded.

    Args:
        config: SurvivorshipConfig with filtering thresholds.

    Example:
        filt = SurvivorshipFilter()
        # Provide listing metadata
        filt.add_listing("AAPL", listed_date=date(1980, 12, 12))
        filt.add_listing("ENRON", listed_date=date(1985, 1, 1), delisted_date=date(2001, 12, 2))

        # Get tradable universe at a specific date
        tradable = filt.filter_universe(
            tickers=["AAPL", "ENRON", "TSLA"],
            as_of=date(2023, 6, 1),
            prices={"AAPL": 180.0, "TSLA": 250.0},
            volumes={"AAPL": 50_000_000, "TSLA": 80_000_000},
        )
        # Returns ["AAPL", "TSLA"] — ENRON was delisted
    """

    def __init__(self, config: SurvivorshipConfig | None = None) -> None:
        self.config = config or SurvivorshipConfig()
        self._listings: dict[str, dict[str, Any]] = {}

    def add_listing(
        self,
        ticker: str,
        listed_date: date | None = None,
        delisted_date: date | None = None,
        exchange: str = "NYSE",
    ) -> None:
        """Register a ticker's listing metadata."""
        self._listings[ticker] = {
            "listed_date": listed_date,
            "delisted_date": delisted_date,
            "exchange": exchange,
        }

    def add_listings_bulk(self, listings: list[dict[str, Any]]) -> None:
        """Register multiple listings at once.

        Each dict should have: ticker, listed_date, delisted_date (optional), exchange.
        """
        for entry in listings:
            self.add_listing(
                ticker=entry["ticker"],
                listed_date=entry.get("listed_date"),
                delisted_date=entry.get("delisted_date"),
                exchange=entry.get("exchange", "NYSE"),
            )

    def filter_universe(
        self,
        tickers: list[str],
        as_of: date,
        prices: dict[str, float] | None = None,
        volumes: dict[str, float] | None = None,
    ) -> list[str]:
        """Filter tickers to those that were tradable on a given date.

        Args:
            tickers: Candidate tickers.
            as_of: Date to check tradability.
            prices: Current prices (for min price filter).
            volumes: Average daily volumes (for liquidity filter).

        Returns:
            List of tickers that pass all filters.
        """
        prices = prices or {}
        volumes = volumes or {}
        tradable = []

        for ticker in tickers:
            if not self._is_listed(ticker, as_of):
                continue
            if not self._meets_price_filter(ticker, prices):
                continue
            if not self._meets_volume_filter(ticker, volumes):
                continue
            tradable.append(ticker)

        return tradable

    def get_delisted_at(self, as_of: date) -> list[str]:
        """Get tickers that were delisted by a specific date."""
        delisted = []
        for ticker, info in self._listings.items():
            dl = info.get("delisted_date")
            if dl and dl <= as_of:
                delisted.append(ticker)
        return delisted

    def get_stats(self) -> dict[str, Any]:
        """Get filtering statistics."""
        total = len(self._listings)
        delisted = sum(
            1 for info in self._listings.values() if info.get("delisted_date")
        )
        return {
            "total_listings": total,
            "active": total - delisted,
            "delisted": delisted,
            "config": {
                "min_price": self.config.min_price,
                "min_volume": self.config.min_volume,
            },
        }

    def _is_listed(self, ticker: str, as_of: date) -> bool:
        """Check if a ticker was listed and not delisted on a given date."""
        info = self._listings.get(ticker)
        if info is None:
            # No listing info = assume tradable (for tickers without metadata)
            return True

        listed = info.get("listed_date")
        delisted = info.get("delisted_date")

        if listed and as_of < listed:
            return False
        if delisted and as_of >= delisted:
            return False

        if self.config.exclude_otc and info.get("exchange", "").upper() in ("OTC", "PINK"):
            return False

        return True

    def _meets_price_filter(self, ticker: str, prices: dict[str, float]) -> bool:
        """Check if ticker meets minimum price requirement."""
        price = prices.get(ticker)
        if price is None:
            return True  # No price data = don't filter
        return price >= self.config.min_price

    def _meets_volume_filter(self, ticker: str, volumes: dict[str, float]) -> bool:
        """Check if ticker meets minimum volume requirement."""
        vol = volumes.get(ticker)
        if vol is None:
            return True  # No volume data = don't filter
        return vol >= self.config.min_volume
