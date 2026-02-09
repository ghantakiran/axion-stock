"""tastytrade Options Chain Analyzer (PRD-158).

Deep options chain analytics unique to tastytrade. Provides greeks,
expirations, IV surface, and optimal strike selection for options-first
trading strategies.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


# =====================================================================
# Options Data Models
# =====================================================================


@dataclass
class OptionGreeks:
    """Option greeks for a single contract."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    iv: float = 0.0  # implied volatility

    @classmethod
    def from_api(cls, data: dict) -> "OptionGreeks":
        return cls(
            delta=float(data.get("delta", 0)),
            gamma=float(data.get("gamma", 0)),
            theta=float(data.get("theta", 0)),
            vega=float(data.get("vega", 0)),
            rho=float(data.get("rho", 0)),
            iv=float(data.get("implied-volatility", data.get("iv", 0))),
        )

    def to_dict(self) -> dict:
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "iv": self.iv,
        }


@dataclass
class OptionStrike:
    """A single strike with call and put data."""
    strike_price: float = 0.0
    # Call side
    call_bid: float = 0.0
    call_ask: float = 0.0
    call_last: float = 0.0
    call_volume: int = 0
    call_oi: int = 0
    call_greeks: OptionGreeks = field(default_factory=OptionGreeks)
    # Put side
    put_bid: float = 0.0
    put_ask: float = 0.0
    put_last: float = 0.0
    put_volume: int = 0
    put_oi: int = 0
    put_greeks: OptionGreeks = field(default_factory=OptionGreeks)

    @classmethod
    def from_api(cls, data: dict) -> "OptionStrike":
        call_data = data.get("call", {})
        put_data = data.get("put", {})
        return cls(
            strike_price=float(data.get("strike-price", data.get("strike", 0))),
            call_bid=float(call_data.get("bid", 0)),
            call_ask=float(call_data.get("ask", 0)),
            call_last=float(call_data.get("last", 0)),
            call_volume=int(call_data.get("volume", 0)),
            call_oi=int(call_data.get("open-interest", call_data.get("oi", 0))),
            call_greeks=OptionGreeks.from_api(call_data.get("greeks", {})),
            put_bid=float(put_data.get("bid", 0)),
            put_ask=float(put_data.get("ask", 0)),
            put_last=float(put_data.get("last", 0)),
            put_volume=int(put_data.get("volume", 0)),
            put_oi=int(put_data.get("open-interest", put_data.get("oi", 0))),
            put_greeks=OptionGreeks.from_api(put_data.get("greeks", {})),
        )

    def to_dict(self) -> dict:
        return {
            "strike_price": self.strike_price,
            "call_bid": self.call_bid,
            "call_ask": self.call_ask,
            "call_last": self.call_last,
            "call_volume": self.call_volume,
            "call_oi": self.call_oi,
            "call_greeks": self.call_greeks.to_dict(),
            "put_bid": self.put_bid,
            "put_ask": self.put_ask,
            "put_last": self.put_last,
            "put_volume": self.put_volume,
            "put_oi": self.put_oi,
            "put_greeks": self.put_greeks.to_dict(),
        }


@dataclass
class OptionExpiration:
    """An expiration date with available strikes."""
    expiration_date: str = ""
    days_to_expiration: int = 0
    strikes: list[OptionStrike] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> "OptionExpiration":
        strikes_data = data.get("strikes", [])
        return cls(
            expiration_date=data.get("expiration-date", data.get("expiration", "")),
            days_to_expiration=int(data.get("days-to-expiration", data.get("dte", 0))),
            strikes=[OptionStrike.from_api(s) for s in strikes_data],
        )

    def to_dict(self) -> dict:
        return {
            "expiration_date": self.expiration_date,
            "days_to_expiration": self.days_to_expiration,
            "strikes": [s.to_dict() for s in self.strikes],
        }


# =====================================================================
# Options Chain Analyzer
# =====================================================================


class OptionsChainAnalyzer:
    """Deep options chain analytics for tastytrade.

    Provides expiration discovery, full chain retrieval, optimal strike
    selection, and implied volatility surface analysis.

    All methods work in demo mode with realistic options data.

    Example:
        analyzer = OptionsChainAnalyzer(client)
        expirations = await analyzer.get_expirations("SPY")
        chain = await analyzer.get_chain("SPY", "2025-03-21")
        optimal = await analyzer.find_optimal_strike("SPY", "long_call", target_delta=0.30)
    """

    def __init__(self, client: Any = None):
        self._client = client

    async def get_expirations(self, symbol: str) -> list[OptionExpiration]:
        """Get available expiration dates for a symbol.

        Args:
            symbol: Underlying symbol (e.g., "SPY", "AAPL").

        Returns:
            List of OptionExpiration with dates and DTE.
        """
        if self._client and hasattr(self._client, "_mode") and self._client._mode == "http":
            try:
                resp = await self._client._http_client.get(
                    f"{self._client._config.base_url}/option-chains/{symbol}/nested",
                    headers=self._client._session_mgr.auth_headers(),
                )
                if resp.status_code == 200:
                    items = resp.json().get("data", {}).get("items", [])
                    return [OptionExpiration.from_api(item) for item in items]
            except Exception as e:
                logger.warning(f"Failed to fetch expirations for {symbol}: {e}")

        return self._demo_expirations(symbol)

    async def get_chain(self, symbol: str, expiration_date: str) -> list[OptionStrike]:
        """Get full options chain for a symbol and expiration.

        Args:
            symbol: Underlying symbol.
            expiration_date: Expiration date string (YYYY-MM-DD).

        Returns:
            List of OptionStrike with call/put data and greeks.
        """
        if self._client and hasattr(self._client, "_mode") and self._client._mode == "http":
            try:
                resp = await self._client._http_client.get(
                    f"{self._client._config.base_url}/option-chains/{symbol}/nested",
                    params={"expiration-date": expiration_date},
                    headers=self._client._session_mgr.auth_headers(),
                )
                if resp.status_code == 200:
                    items = resp.json().get("data", {}).get("items", [])
                    strikes = []
                    for item in items:
                        for s in item.get("strikes", []):
                            strikes.append(OptionStrike.from_api(s))
                    return strikes
            except Exception as e:
                logger.warning(f"Failed to fetch chain for {symbol} {expiration_date}: {e}")

        return self._demo_chain(symbol)

    async def find_optimal_strike(
        self, symbol: str, strategy: str = "long_call", target_delta: float = 0.30
    ) -> OptionStrike:
        """Find the optimal strike for a given strategy and target delta.

        Args:
            symbol: Underlying symbol.
            strategy: Strategy type (long_call, long_put, short_call, short_put,
                      bull_call_spread, bear_put_spread).
            target_delta: Target absolute delta value (0.0 to 1.0).

        Returns:
            The OptionStrike closest to the target delta.
        """
        chain = await self.get_chain(symbol, "")
        if not chain:
            return OptionStrike()

        best_strike = chain[0]
        best_diff = float("inf")

        for strike in chain:
            if strategy in ("long_call", "short_call", "bull_call_spread"):
                delta = abs(strike.call_greeks.delta)
            else:
                delta = abs(strike.put_greeks.delta)

            diff = abs(delta - target_delta)
            if diff < best_diff:
                best_diff = diff
                best_strike = strike

        return best_strike

    async def get_iv_surface(self, symbol: str) -> dict:
        """Get implied volatility surface (strike x expiration -> IV).

        Args:
            symbol: Underlying symbol.

        Returns:
            Nested dict: {strike_price: {expiration_date: iv}}.
        """
        expirations = await self.get_expirations(symbol)
        surface: dict[float, dict[str, float]] = {}

        for exp in expirations:
            chain = await self.get_chain(symbol, exp.expiration_date)
            for strike in chain:
                if strike.strike_price not in surface:
                    surface[strike.strike_price] = {}
                # Average of call and put IV
                avg_iv = (strike.call_greeks.iv + strike.put_greeks.iv) / 2
                surface[strike.strike_price][exp.expiration_date] = round(avg_iv, 4)

        return surface

    # -- Demo Data ---------------------------------------------------------

    def _demo_expirations(self, symbol: str) -> list[OptionExpiration]:
        """Generate realistic expiration dates."""
        today = date.today()
        expirations = []
        # Weekly expirations for next 4 weeks, then monthly for 3 months
        dte_list = [3, 7, 14, 21, 30, 60, 90]
        for dte in dte_list:
            exp_date = today + timedelta(days=dte)
            expirations.append(OptionExpiration(
                expiration_date=exp_date.strftime("%Y-%m-%d"),
                days_to_expiration=dte,
                strikes=[],
            ))
        return expirations

    def _demo_chain(self, symbol: str) -> list[OptionStrike]:
        """Generate realistic options chain with proper greeks."""
        demo_bases = {
            "SPY": 590.50, "AAPL": 230.75, "MSFT": 415.30,
            "NVDA": 875.20, "GOOGL": 185.40, "QQQ": 510.80,
            "IWM": 225.60, "TSLA": 382.50, "AMZN": 202.10,
        }
        base = demo_bases.get(symbol, 100.0)
        strikes = []
        step = max(1.0, round(base * 0.01, 0))  # ~1% strike spacing

        for i in range(-10, 11):
            strike_price = round(base + i * step, 2)
            moneyness = (base - strike_price) / base  # positive = ITM call

            # Call greeks
            call_delta = round(max(0.02, min(0.98, 0.50 + moneyness * 5.0)), 3)
            call_gamma = round(max(0.001, 0.04 * (1 - abs(moneyness) * 8)), 4)
            call_theta = round(-0.08 * (1 - abs(moneyness) * 3), 4)
            call_vega = round(max(0.01, 0.25 * (1 - abs(moneyness) * 5)), 4)
            call_iv = round(0.22 + abs(moneyness) * 0.15, 4)  # vol smile

            # Put greeks (put-call parity)
            put_delta = round(call_delta - 1.0, 3)
            put_gamma = call_gamma
            put_theta = round(call_theta + 0.01, 4)
            put_vega = call_vega
            put_iv = round(call_iv + 0.005, 4)  # slight put skew

            # Prices from intrinsic + time value
            call_intrinsic = max(0, base - strike_price)
            put_intrinsic = max(0, strike_price - base)
            time_value = max(0.05, base * 0.02 * (1 - abs(moneyness) * 3))

            call_mid = round(call_intrinsic + time_value, 2)
            put_mid = round(put_intrinsic + time_value, 2)
            spread = round(max(0.01, call_mid * 0.02), 2)

            strikes.append(OptionStrike(
                strike_price=strike_price,
                call_bid=round(max(0.01, call_mid - spread), 2),
                call_ask=round(max(0.02, call_mid + spread), 2),
                call_last=round(max(0.01, call_mid), 2),
                call_volume=max(10, 5000 - abs(i) * 400),
                call_oi=max(100, 15000 - abs(i) * 1200),
                call_greeks=OptionGreeks(
                    delta=call_delta, gamma=call_gamma, theta=call_theta,
                    vega=call_vega, rho=round(0.05 * call_delta, 4), iv=call_iv,
                ),
                put_bid=round(max(0.01, put_mid - spread), 2),
                put_ask=round(max(0.02, put_mid + spread), 2),
                put_last=round(max(0.01, put_mid), 2),
                put_volume=max(10, 4500 - abs(i) * 350),
                put_oi=max(100, 13000 - abs(i) * 1000),
                put_greeks=OptionGreeks(
                    delta=put_delta, gamma=put_gamma, theta=put_theta,
                    vega=put_vega, rho=round(0.05 * put_delta, 4), iv=put_iv,
                ),
            ))

        return strikes
