"""Crypto Options Data Models."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
from uuid import uuid4

from src.crypto_options.config import (
    CryptoOptionType,
    CryptoDerivativeType,
    CryptoExchange,
    SettlementType,
)


def _generate_id() -> str:
    return str(uuid4())


@dataclass
class CryptoOptionGreeks:
    """Option greeks for crypto options."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    iv: float = 0.0  # Implied volatility

    def to_dict(self) -> dict:
        return {
            "delta": round(self.delta, 6),
            "gamma": round(self.gamma, 6),
            "theta": round(self.theta, 6),
            "vega": round(self.vega, 6),
            "rho": round(self.rho, 6),
            "iv": round(self.iv, 4),
        }


@dataclass
class CryptoOptionContract:
    """A crypto option contract."""
    id: str = field(default_factory=_generate_id)
    underlying: str = "BTC"
    option_type: CryptoOptionType = CryptoOptionType.CALL
    strike: float = 0.0
    expiry: date = field(default_factory=date.today)
    contract_size: float = 1.0
    exchange: CryptoExchange = CryptoExchange.DERIBIT
    settlement: SettlementType = SettlementType.CASH

    @property
    def is_expired(self) -> bool:
        return date.today() > self.expiry

    @property
    def days_to_expiry(self) -> int:
        return max(0, (self.expiry - date.today()).days)

    @property
    def time_to_expiry(self) -> float:
        """Time to expiry in years."""
        return self.days_to_expiry / 365.0

    @property
    def instrument_name(self) -> str:
        """Standard instrument name (e.g., BTC-20240628-50000-C)."""
        exp_str = self.expiry.strftime("%Y%m%d")
        opt_char = "C" if self.option_type == CryptoOptionType.CALL else "P"
        return f"{self.underlying}-{exp_str}-{self.strike:.0f}-{opt_char}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "underlying": self.underlying,
            "option_type": self.option_type.value,
            "strike": self.strike,
            "expiry": self.expiry.isoformat(),
            "days_to_expiry": self.days_to_expiry,
            "instrument_name": self.instrument_name,
            "exchange": self.exchange.value,
            "settlement": self.settlement.value,
        }


@dataclass
class CryptoOptionQuote:
    """Market quote for a crypto option."""
    contract: CryptoOptionContract = field(default_factory=CryptoOptionContract)
    bid: float = 0.0
    ask: float = 0.0
    mark: float = 0.0
    last: float = 0.0
    volume_24h: float = 0.0
    open_interest: float = 0.0
    underlying_price: float = 0.0
    greeks: CryptoOptionGreeks = field(default_factory=CryptoOptionGreeks)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2 if self.bid > 0 and self.ask > 0 else self.mark

    @property
    def moneyness(self) -> float:
        """Moneyness = spot / strike."""
        if self.contract.strike == 0:
            return 0.0
        return self.underlying_price / self.contract.strike

    def to_dict(self) -> dict:
        return {
            "contract": self.contract.to_dict(),
            "bid": self.bid,
            "ask": self.ask,
            "mark": self.mark,
            "mid": self.mid,
            "spread": self.spread,
            "volume_24h": self.volume_24h,
            "open_interest": self.open_interest,
            "underlying_price": self.underlying_price,
            "moneyness": round(self.moneyness, 4),
            "greeks": self.greeks.to_dict(),
        }


@dataclass
class CryptoPerpetual:
    """Perpetual futures contract."""
    id: str = field(default_factory=_generate_id)
    underlying: str = "BTC"
    exchange: CryptoExchange = CryptoExchange.BINANCE
    mark_price: float = 0.0
    index_price: float = 0.0
    funding_rate: float = 0.0
    next_funding_time: Optional[datetime] = None
    open_interest: float = 0.0
    volume_24h: float = 0.0
    max_leverage: float = 100.0

    @property
    def basis(self) -> float:
        """Basis = mark - index."""
        return self.mark_price - self.index_price

    @property
    def basis_pct(self) -> float:
        if self.index_price == 0:
            return 0.0
        return (self.basis / self.index_price) * 100

    @property
    def annualized_funding(self) -> float:
        """Annualized funding rate (assuming 8h intervals)."""
        return self.funding_rate * 3 * 365 * 100  # 3 per day * 365 days * 100 for %

    def to_dict(self) -> dict:
        return {
            "underlying": self.underlying,
            "exchange": self.exchange.value,
            "mark_price": self.mark_price,
            "index_price": self.index_price,
            "funding_rate": self.funding_rate,
            "basis": round(self.basis, 2),
            "basis_pct": round(self.basis_pct, 4),
            "annualized_funding": round(self.annualized_funding, 2),
            "open_interest": self.open_interest,
            "volume_24h": self.volume_24h,
        }


@dataclass
class CryptoFundingRate:
    """Historical funding rate snapshot."""
    underlying: str = "BTC"
    exchange: CryptoExchange = CryptoExchange.BINANCE
    rate: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def annualized(self) -> float:
        return self.rate * 3 * 365 * 100

    def to_dict(self) -> dict:
        return {
            "underlying": self.underlying,
            "exchange": self.exchange.value,
            "rate": self.rate,
            "annualized": round(self.annualized, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CryptoBasisSpread:
    """Spot-futures basis spread analysis."""
    underlying: str = "BTC"
    spot_price: float = 0.0
    futures_price: float = 0.0
    perp_price: float = 0.0
    days_to_expiry: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def futures_basis(self) -> float:
        return self.futures_price - self.spot_price

    @property
    def futures_basis_pct(self) -> float:
        if self.spot_price == 0:
            return 0.0
        return (self.futures_basis / self.spot_price) * 100

    @property
    def annualized_basis(self) -> float:
        """Annualized basis rate."""
        if self.days_to_expiry == 0 or self.spot_price == 0:
            return 0.0
        return (self.futures_basis / self.spot_price) * (365 / self.days_to_expiry) * 100

    @property
    def perp_premium(self) -> float:
        return self.perp_price - self.spot_price

    @property
    def perp_premium_pct(self) -> float:
        if self.spot_price == 0:
            return 0.0
        return (self.perp_premium / self.spot_price) * 100

    def to_dict(self) -> dict:
        return {
            "underlying": self.underlying,
            "spot_price": self.spot_price,
            "futures_price": self.futures_price,
            "perp_price": self.perp_price,
            "futures_basis": round(self.futures_basis, 2),
            "futures_basis_pct": round(self.futures_basis_pct, 4),
            "annualized_basis": round(self.annualized_basis, 2),
            "perp_premium": round(self.perp_premium, 2),
            "perp_premium_pct": round(self.perp_premium_pct, 4),
        }
