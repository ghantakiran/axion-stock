"""International Equities Integration.

FX rate management, currency hedging, and trading hours for global markets.
"""

import logging
from datetime import datetime, time
from typing import Optional

from src.multi_asset.config import INTL_MARKETS, FXConfig
from src.multi_asset.models import FXRate, IntlEquity

logger = logging.getLogger(__name__)


class FXRateProvider:
    """Foreign exchange rate management.

    Provides FX rate lookups, cross rates, and conversion.
    In production, integrates with Open Exchange Rates or similar.
    """

    def __init__(self, base_currency: str = "USD"):
        self.base_currency = base_currency
        self._rates: dict[str, FXRate] = {}

    def set_rate(self, base: str, quote: str, rate: float):
        """Set an FX rate.

        Args:
            base: Base currency.
            quote: Quote currency.
            rate: Exchange rate (1 base = rate quote).
        """
        pair = f"{base}/{quote}"
        self._rates[pair] = FXRate(base=base, quote=quote, rate=rate)
        # Also store inverse
        inv_pair = f"{quote}/{base}"
        self._rates[inv_pair] = FXRate(base=quote, quote=base, rate=1.0 / rate if rate > 0 else 0)

    def get_rate(self, base: str, quote: str) -> Optional[float]:
        """Get FX rate.

        Args:
            base: Base currency.
            quote: Quote currency.

        Returns:
            Exchange rate or None.
        """
        if base == quote:
            return 1.0

        pair = f"{base}/{quote}"
        fx = self._rates.get(pair)
        if fx:
            return fx.rate

        # Try cross rate via USD
        if base != "USD" and quote != "USD":
            base_usd = self.get_rate(base, "USD")
            usd_quote = self.get_rate("USD", quote)
            if base_usd is not None and usd_quote is not None:
                return base_usd * usd_quote

        return None

    def convert(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """Convert an amount between currencies.

        Args:
            amount: Amount to convert.
            from_currency: Source currency.
            to_currency: Target currency.

        Returns:
            Converted amount or None.
        """
        rate = self.get_rate(from_currency, to_currency)
        if rate is None:
            return None
        return amount * rate

    def get_all_rates(self, quote: str = "USD") -> dict[str, float]:
        """Get all rates against a quote currency.

        Args:
            quote: Quote currency.

        Returns:
            Dict of base currency -> rate.
        """
        result = {}
        for pair, fx in self._rates.items():
            if fx.quote == quote:
                result[fx.base] = fx.rate
        return result


class InternationalMarketManager:
    """Manages international equity markets.

    Features:
    - Market metadata (exchange, currency, trading hours)
    - FX-aware valuation
    - Trading session detection
    - Currency hedging analysis
    """

    def __init__(
        self,
        fx_provider: Optional[FXRateProvider] = None,
        fx_config: Optional[FXConfig] = None,
    ):
        self.fx = fx_provider or FXRateProvider()
        self.config = fx_config or FXConfig()
        self._equities: dict[str, IntlEquity] = {}

    def register_equity(self, equity: IntlEquity):
        """Register an international equity."""
        self._equities[equity.symbol.upper()] = equity

    def get_equity(self, symbol: str) -> Optional[IntlEquity]:
        """Get equity by symbol."""
        return self._equities.get(symbol.upper())

    def get_equities_by_market(self, market: str) -> list[IntlEquity]:
        """Get all equities for a market."""
        return [e for e in self._equities.values() if e.market == market]

    def get_supported_markets(self) -> dict:
        """Get all supported international markets."""
        return dict(INTL_MARKETS)

    def is_market_open(self, market: str, check_time: Optional[datetime] = None) -> bool:
        """Check if a market is currently open.

        Args:
            market: Market name (e.g. 'UK', 'Japan').
            check_time: Time to check (defaults to now UTC).

        Returns:
            True if market is in trading hours.
        """
        info = INTL_MARKETS.get(market)
        if not info:
            return False

        hours = info["hours"]
        parts = hours.split("-")
        if len(parts) != 2:
            return False

        open_h, open_m = map(int, parts[0].strip().split(":"))
        close_h, close_m = map(int, parts[1].strip().split(":"))

        open_time = time(open_h, open_m)
        close_time = time(close_h, close_m)

        now = (check_time or datetime.utcnow()).time()

        # Handle overnight sessions (e.g. Japan 19:00-01:00)
        if open_time > close_time:
            return now >= open_time or now <= close_time
        else:
            return open_time <= now <= close_time

    def convert_to_usd(self, equity: IntlEquity) -> float:
        """Convert equity price to USD.

        Args:
            equity: International equity.

        Returns:
            Price in USD (0 if FX rate unavailable).
        """
        rate = self.fx.get_rate(equity.currency, "USD")
        if rate is not None:
            equity.price_usd = equity.price_local * rate
            return equity.price_usd
        return 0.0

    def compute_currency_exposure(
        self,
        positions: list[IntlEquity],
    ) -> dict[str, float]:
        """Compute total USD exposure by currency.

        Args:
            positions: List of international equity positions.

        Returns:
            Dict of currency -> USD exposure.
        """
        exposure: dict[str, float] = {}
        for eq in positions:
            self.convert_to_usd(eq)
            exposure[eq.currency] = exposure.get(eq.currency, 0) + eq.price_usd

        return exposure

    def compute_hedge_ratios(
        self,
        positions: list[IntlEquity],
        total_portfolio_value: float,
    ) -> dict[str, float]:
        """Compute FX hedge ratios for each currency.

        Currencies exceeding the hedge threshold get a recommended
        hedge ratio based on exposure relative to portfolio.

        Args:
            positions: International equity positions.
            total_portfolio_value: Total portfolio value in USD.

        Returns:
            Dict of currency -> recommended hedge ratio (0-1).
        """
        if total_portfolio_value <= 0:
            return {}

        exposure = self.compute_currency_exposure(positions)
        hedges = {}

        for currency, usd_value in exposure.items():
            if currency == "USD":
                continue
            pct = usd_value / total_portfolio_value
            if pct > self.config.hedge_threshold:
                hedges[currency] = min(1.0, pct)

        return hedges
