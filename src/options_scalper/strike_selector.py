"""Optimal strike and expiry selection for options scalps.

Selects strikes based on delta target, bid-ask spread, open interest,
and volume criteria. Prefers 0DTE, falls back to 1DTE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Optional

logger = logging.getLogger(__name__)


@dataclass
class StrikeSelection:
    """Selected strike for a scalp trade."""

    strike: float
    expiry: date
    dte: int
    option_type: Literal["call", "put"]
    option_symbol: str
    delta: float
    gamma: float
    theta: float
    iv: float
    bid: float
    ask: float
    mid: float
    spread_pct: float
    open_interest: int
    volume: int
    score: float

    def to_dict(self) -> dict:
        return {
            "strike": self.strike,
            "expiry": self.expiry.isoformat(),
            "dte": self.dte,
            "option_type": self.option_type,
            "option_symbol": self.option_symbol,
            "delta": round(self.delta, 3),
            "theta": round(self.theta, 3),
            "iv": round(self.iv, 4),
            "mid": round(self.mid, 2),
            "spread_pct": round(self.spread_pct, 4),
            "score": round(self.score, 2),
        }


class StrikeSelector:
    """Select the optimal strike price and expiry for a scalp trade.

    Selection criteria (priority order):
    1. Expiry: 0DTE first, 1DTE if 0DTE not available or after 2 PM
    2. Delta target: 0.30-0.50 for directional scalps
    3. Bid-ask spread: < 10% of option mid price
    4. Open interest: > 1,000 contracts
    5. Volume: > 500 contracts traded today
    """

    def __init__(self, config):
        self.config = config

    def select(
        self,
        ticker: str,
        direction: str,
        chain_data: Optional[list] = None,
        underlying_price: float = 0.0,
    ) -> Optional[StrikeSelection]:
        """Select the best strike from the chain.

        If no chain_data is provided, generates a synthetic ATM selection
        for paper trading / testing purposes.
        """
        if chain_data:
            return self._select_from_chain(ticker, direction, chain_data)
        return self._synthetic_selection(ticker, direction, underlying_price)

    def _select_from_chain(
        self, ticker: str, direction: str, chain_data: list
    ) -> Optional[StrikeSelection]:
        """Select from real chain data (list of contract dicts)."""
        option_type: Literal["call", "put"] = "call" if direction == "long" else "put"

        # Filter by option type
        candidates = [c for c in chain_data if c.get("option_type") == option_type]
        if not candidates:
            return None

        # Filter by delta
        candidates = self._filter_by_delta(candidates)
        if not candidates:
            return None

        # Filter by liquidity
        candidates = self._filter_by_liquidity(candidates)
        if not candidates:
            return None

        # Score and pick best
        scored = self._score_strikes(candidates)
        best = max(scored, key=lambda x: x["score"])

        expiry = best.get("expiry", date.today())
        if isinstance(expiry, str):
            expiry = date.fromisoformat(expiry)
        dte = (expiry - date.today()).days

        bid = best.get("bid", 0.0)
        ask = best.get("ask", 0.0)
        mid = (bid + ask) / 2 if (bid + ask) > 0 else best.get("last", 1.0)
        spread_pct = (ask - bid) / mid if mid > 0 else 1.0

        return StrikeSelection(
            strike=best["strike"],
            expiry=expiry,
            dte=dte,
            option_type=option_type,
            option_symbol=best.get("symbol", f"{ticker}{expiry.strftime('%y%m%d')}{option_type[0].upper()}{int(best['strike']*1000):08d}"),
            delta=abs(best.get("delta", 0.40)),
            gamma=best.get("gamma", 0.05),
            theta=best.get("theta", -0.05),
            iv=best.get("iv", 0.30),
            bid=bid,
            ask=ask,
            mid=round(mid, 2),
            spread_pct=round(spread_pct, 4),
            open_interest=best.get("open_interest", 0),
            volume=best.get("volume", 0),
            score=best["score"],
        )

    def _synthetic_selection(
        self, ticker: str, direction: str, underlying_price: float
    ) -> StrikeSelection:
        """Generate a synthetic ATM selection for paper trading."""
        option_type: Literal["call", "put"] = "call" if direction == "long" else "put"
        strike = round(underlying_price, 0)
        expiry = date.today()
        dte = 0

        # Approximate ATM premiums
        premium = underlying_price * 0.005  # ~0.5% of underlying

        symbol = f"{ticker}{expiry.strftime('%y%m%d')}{option_type[0].upper()}{int(strike*1000):08d}"

        return StrikeSelection(
            strike=strike,
            expiry=expiry,
            dte=dte,
            option_type=option_type,
            option_symbol=symbol,
            delta=0.50 if option_type == "call" else -0.50,
            gamma=0.05,
            theta=-0.10,
            iv=0.25,
            bid=round(premium * 0.95, 2),
            ask=round(premium * 1.05, 2),
            mid=round(premium, 2),
            spread_pct=0.05,
            open_interest=5000,
            volume=2000,
            score=80.0,
        )

    def _filter_by_delta(self, candidates: list) -> list:
        """Keep contracts within target delta range."""
        return [
            c for c in candidates
            if self.config.target_delta_min <= abs(c.get("delta", 0)) <= self.config.target_delta_max
        ]

    def _filter_by_liquidity(self, candidates: list) -> list:
        """Keep contracts meeting liquidity requirements."""
        result = []
        for c in candidates:
            bid = c.get("bid", 0)
            ask = c.get("ask", 0)
            mid = (bid + ask) / 2 if (bid + ask) > 0 else 0

            if mid > 0:
                spread_pct = (ask - bid) / mid
                if spread_pct > self.config.max_spread_pct:
                    continue

            if c.get("open_interest", 0) < self.config.min_open_interest:
                continue
            if c.get("volume", 0) < self.config.min_volume:
                continue

            result.append(c)
        return result

    def _score_strikes(self, candidates: list) -> list:
        """Score each candidate strike."""
        for c in candidates:
            score = 0.0
            delta = abs(c.get("delta", 0))

            # Delta closer to 0.40 is ideal
            delta_score = 1.0 - abs(delta - 0.40) / 0.10
            score += max(delta_score, 0) * 40

            # Lower spread is better
            bid = c.get("bid", 0)
            ask = c.get("ask", 0)
            mid = (bid + ask) / 2 if (bid + ask) > 0 else 1.0
            spread = (ask - bid) / mid if mid > 0 else 1.0
            spread_score = max(1.0 - spread / self.config.max_spread_pct, 0)
            score += spread_score * 30

            # Higher volume is better
            vol = c.get("volume", 0)
            vol_score = min(vol / 5000, 1.0)
            score += vol_score * 15

            # Higher OI is better
            oi = c.get("open_interest", 0)
            oi_score = min(oi / 10000, 1.0)
            score += oi_score * 15

            c["score"] = round(score, 2)
        return candidates
