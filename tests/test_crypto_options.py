"""Tests for Crypto Options Platform."""

import pytest
from datetime import date, timedelta

from src.crypto_options.config import (
    CryptoOptionType,
    CryptoDerivativeType,
    CryptoExchange,
    SettlementType,
    MarginType,
    SUPPORTED_UNDERLYINGS,
    CryptoOptionsConfig,
    DEFAULT_CRYPTO_OPTIONS_CONFIG,
)
from src.crypto_options.models import (
    CryptoOptionContract,
    CryptoOptionQuote,
    CryptoOptionGreeks,
    CryptoPerpetual,
    CryptoFundingRate,
    CryptoBasisSpread,
)
from src.crypto_options.pricing import CryptoOptionPricer
from src.crypto_options.analytics import CryptoDerivativesAnalyzer


# ── Config Tests ──


class TestCryptoOptionsEnums:
    def test_option_types(self):
        assert CryptoOptionType.CALL.value == "call"
        assert CryptoOptionType.PUT.value == "put"

    def test_derivative_types(self):
        assert len(CryptoDerivativeType) == 6
        assert CryptoDerivativeType.PERPETUAL.value == "perpetual"

    def test_exchanges(self):
        assert CryptoExchange.DERIBIT.value == "deribit"
        assert len(CryptoExchange) == 5

    def test_settlement_types(self):
        assert SettlementType.CASH.value == "cash"
        assert SettlementType.INVERSE.value == "inverse"

    def test_margin_types(self):
        assert MarginType.CROSS.value == "cross"
        assert MarginType.PORTFOLIO.value == "portfolio"

    def test_supported_underlyings(self):
        assert "BTC" in SUPPORTED_UNDERLYINGS
        assert "ETH" in SUPPORTED_UNDERLYINGS
        assert SUPPORTED_UNDERLYINGS["BTC"]["contract_size"] == 1.0

    def test_default_config(self):
        cfg = DEFAULT_CRYPTO_OPTIONS_CONFIG
        assert cfg.enabled is True
        assert cfg.max_leverage == 100.0
        assert cfg.default_exchange == CryptoExchange.DERIBIT


# ── Model Tests ──


class TestCryptoOptionGreeks:
    def test_to_dict(self):
        g = CryptoOptionGreeks(delta=0.55, gamma=0.001, theta=-5.2, vega=12.3, iv=0.85)
        d = g.to_dict()
        assert d["delta"] == 0.55
        assert d["iv"] == 0.85


class TestCryptoOptionContract:
    def test_instrument_name(self):
        c = CryptoOptionContract(
            underlying="BTC",
            option_type=CryptoOptionType.CALL,
            strike=50000,
            expiry=date(2025, 6, 28),
        )
        assert c.instrument_name == "BTC-20250628-50000-C"

    def test_put_instrument_name(self):
        c = CryptoOptionContract(
            underlying="ETH",
            option_type=CryptoOptionType.PUT,
            strike=3000,
            expiry=date(2025, 6, 28),
        )
        assert "P" in c.instrument_name

    def test_days_to_expiry(self):
        future = date.today() + timedelta(days=30)
        c = CryptoOptionContract(expiry=future)
        assert c.days_to_expiry == 30

    def test_time_to_expiry(self):
        future = date.today() + timedelta(days=365)
        c = CryptoOptionContract(expiry=future)
        assert abs(c.time_to_expiry - 1.0) < 0.01

    def test_is_expired(self):
        past = date.today() - timedelta(days=1)
        c = CryptoOptionContract(expiry=past)
        assert c.is_expired

    def test_not_expired(self):
        future = date.today() + timedelta(days=30)
        c = CryptoOptionContract(expiry=future)
        assert not c.is_expired

    def test_to_dict(self):
        c = CryptoOptionContract(underlying="BTC", strike=50000)
        d = c.to_dict()
        assert d["underlying"] == "BTC"
        assert d["strike"] == 50000


class TestCryptoOptionQuote:
    def test_spread(self):
        q = CryptoOptionQuote(bid=100, ask=105)
        assert q.spread == 5

    def test_mid(self):
        q = CryptoOptionQuote(bid=100, ask=110)
        assert q.mid == 105

    def test_mid_zero_bid(self):
        q = CryptoOptionQuote(bid=0, ask=0, mark=50)
        assert q.mid == 50

    def test_moneyness(self):
        c = CryptoOptionContract(strike=50000)
        q = CryptoOptionQuote(contract=c, underlying_price=55000)
        assert abs(q.moneyness - 1.1) < 0.001

    def test_moneyness_zero_strike(self):
        c = CryptoOptionContract(strike=0)
        q = CryptoOptionQuote(contract=c, underlying_price=50000)
        assert q.moneyness == 0.0

    def test_to_dict(self):
        q = CryptoOptionQuote(bid=100, ask=110, mark=105)
        d = q.to_dict()
        assert "greeks" in d
        assert d["spread"] == 10


class TestCryptoPerpetual:
    def test_basis(self):
        p = CryptoPerpetual(mark_price=50100, index_price=50000)
        assert p.basis == 100

    def test_basis_pct(self):
        p = CryptoPerpetual(mark_price=50100, index_price=50000)
        assert abs(p.basis_pct - 0.2) < 0.01

    def test_annualized_funding(self):
        p = CryptoPerpetual(funding_rate=0.0001)
        assert p.annualized_funding == pytest.approx(0.0001 * 3 * 365 * 100, rel=1e-3)

    def test_zero_index(self):
        p = CryptoPerpetual(mark_price=50000, index_price=0)
        assert p.basis_pct == 0.0

    def test_to_dict(self):
        p = CryptoPerpetual(underlying="ETH")
        d = p.to_dict()
        assert d["underlying"] == "ETH"


class TestCryptoFundingRate:
    def test_annualized(self):
        fr = CryptoFundingRate(rate=0.0001)
        assert fr.annualized > 0

    def test_to_dict(self):
        fr = CryptoFundingRate(underlying="BTC", rate=0.0001)
        d = fr.to_dict()
        assert d["underlying"] == "BTC"


class TestCryptoBasisSpread:
    def test_futures_basis(self):
        bs = CryptoBasisSpread(spot_price=50000, futures_price=50500, perp_price=50100)
        assert bs.futures_basis == 500

    def test_futures_basis_pct(self):
        bs = CryptoBasisSpread(spot_price=50000, futures_price=50500)
        assert abs(bs.futures_basis_pct - 1.0) < 0.01

    def test_annualized_basis(self):
        bs = CryptoBasisSpread(spot_price=50000, futures_price=50500, days_to_expiry=90)
        annual = bs.annualized_basis
        assert annual > 0

    def test_zero_days(self):
        bs = CryptoBasisSpread(spot_price=50000, futures_price=50500, days_to_expiry=0)
        assert bs.annualized_basis == 0.0

    def test_perp_premium(self):
        bs = CryptoBasisSpread(spot_price=50000, perp_price=50100)
        assert bs.perp_premium == 100
        assert abs(bs.perp_premium_pct - 0.2) < 0.01

    def test_to_dict(self):
        bs = CryptoBasisSpread(underlying="BTC", spot_price=50000)
        d = bs.to_dict()
        assert d["underlying"] == "BTC"


# ── Pricing Tests ──


class TestCryptoOptionPricer:
    def setup_method(self):
        self.pricer = CryptoOptionPricer()
        self.future_expiry = date.today() + timedelta(days=30)

    def test_call_price_positive(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=50000, expiry=self.future_expiry,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.mark > 0

    def test_put_price_positive(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.PUT,
            strike=50000, expiry=self.future_expiry,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.mark > 0

    def test_deep_itm_call(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=30000, expiry=self.future_expiry,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.mark > 19000  # At least intrinsic

    def test_deep_otm_call(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=100000, expiry=self.future_expiry,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.mark < 1000  # Very small value

    def test_atm_delta_near_half(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=50000, expiry=self.future_expiry,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert 0.4 < quote.greeks.delta < 0.7

    def test_put_delta_negative(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.PUT,
            strike=50000, expiry=self.future_expiry,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.greeks.delta < 0

    def test_gamma_positive(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=50000, expiry=self.future_expiry,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.greeks.gamma > 0

    def test_theta_negative(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=50000, expiry=self.future_expiry,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.greeks.theta < 0

    def test_expired_option(self):
        past = date.today() - timedelta(days=1)
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=40000, expiry=past,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.mark == 10000  # Intrinsic only

    def test_expired_otm(self):
        past = date.today() - timedelta(days=1)
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=60000, expiry=past,
        )
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        assert quote.mark == 0

    def test_implied_vol(self):
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=50000, expiry=self.future_expiry,
        )
        # Price at known vol, then solve back
        quote = self.pricer.price(c, spot=50000, vol=0.80)
        solved_iv = self.pricer.implied_vol(c, spot=50000, market_price=quote.mark)
        assert abs(solved_iv - 0.80) < 0.01

    def test_implied_vol_expired(self):
        past = date.today() - timedelta(days=1)
        c = CryptoOptionContract(expiry=past)
        assert self.pricer.implied_vol(c, spot=50000, market_price=100) == 0.0

    def test_vol_surface(self):
        quotes = []
        for strike in [45000, 50000, 55000]:
            c = CryptoOptionContract(
                underlying="BTC", option_type=CryptoOptionType.CALL,
                strike=strike, expiry=self.future_expiry,
            )
            q = self.pricer.price(c, spot=50000, vol=0.80)
            quotes.append(q)

        surface = self.pricer.build_vol_surface("BTC", 50000, quotes)
        assert len(surface) == 3

    def test_get_vol_surface_empty(self):
        assert self.pricer.get_vol_surface("UNKNOWN") == {}


# ── Analytics Tests ──


class TestCryptoDerivativesAnalyzer:
    def setup_method(self):
        self.analyzer = CryptoDerivativesAnalyzer()

    def test_record_funding_rate(self):
        fr = self.analyzer.record_funding_rate("BTC", CryptoExchange.BINANCE, 0.0001)
        assert fr.rate == 0.0001
        assert fr.underlying == "BTC"

    def test_get_funding_history(self):
        for i in range(5):
            self.analyzer.record_funding_rate("BTC", CryptoExchange.BINANCE, 0.0001 * (i + 1))
        history = self.analyzer.get_funding_history("BTC", CryptoExchange.BINANCE)
        assert len(history) == 5

    def test_average_funding_rate(self):
        for rate in [0.0001, 0.0002, 0.0003]:
            self.analyzer.record_funding_rate("BTC", CryptoExchange.BINANCE, rate)
        avg = self.analyzer.average_funding_rate("BTC", CryptoExchange.BINANCE)
        assert abs(avg - 0.0002) < 1e-6

    def test_average_funding_empty(self):
        avg = self.analyzer.average_funding_rate("BTC", CryptoExchange.BINANCE)
        assert avg == 0.0

    def test_compute_basis(self):
        basis = self.analyzer.compute_basis("BTC", 50000, 50500, 50100, 90)
        assert basis.futures_basis == 500
        assert basis.perp_premium == 100

    def test_put_call_ratio(self):
        future_expiry = date.today() + timedelta(days=30)
        quotes = [
            CryptoOptionQuote(
                contract=CryptoOptionContract(option_type=CryptoOptionType.CALL, expiry=future_expiry),
                open_interest=100,
            ),
            CryptoOptionQuote(
                contract=CryptoOptionContract(option_type=CryptoOptionType.PUT, expiry=future_expiry),
                open_interest=80,
            ),
        ]
        ratio = self.analyzer.put_call_ratio(quotes)
        assert abs(ratio - 0.8) < 0.001

    def test_put_call_ratio_no_calls(self):
        future_expiry = date.today() + timedelta(days=30)
        quotes = [
            CryptoOptionQuote(
                contract=CryptoOptionContract(option_type=CryptoOptionType.PUT, expiry=future_expiry),
                open_interest=80,
            ),
        ]
        assert self.analyzer.put_call_ratio(quotes) == 0.0

    def test_max_pain(self):
        future_expiry = date.today() + timedelta(days=30)
        quotes = [
            CryptoOptionQuote(
                contract=CryptoOptionContract(
                    option_type=CryptoOptionType.CALL, strike=50000, expiry=future_expiry,
                ),
                open_interest=100,
            ),
            CryptoOptionQuote(
                contract=CryptoOptionContract(
                    option_type=CryptoOptionType.PUT, strike=50000, expiry=future_expiry,
                ),
                open_interest=100,
            ),
            CryptoOptionQuote(
                contract=CryptoOptionContract(
                    option_type=CryptoOptionType.CALL, strike=55000, expiry=future_expiry,
                ),
                open_interest=50,
            ),
        ]
        mp = self.analyzer.max_pain(quotes, 50000)
        assert mp > 0

    def test_max_pain_empty(self):
        mp = self.analyzer.max_pain([], 50000)
        assert mp == 50000

    def test_perpetual_crud(self):
        perp = CryptoPerpetual(underlying="BTC", mark_price=50100, index_price=50000)
        self.analyzer.update_perpetual(perp)
        retrieved = self.analyzer.get_perpetual("BTC")
        assert retrieved is not None
        assert retrieved.mark_price == 50100

    def test_perpetual_not_found(self):
        assert self.analyzer.get_perpetual("UNKNOWN") is None


# ── Module Import Test ──


class TestCryptoOptionsModuleImports:
    def test_top_level_imports(self):
        from src.crypto_options import (
            CryptoOptionPricer,
            CryptoDerivativesAnalyzer,
            CryptoOptionContract,
            CryptoPerpetual,
        )
        assert CryptoOptionPricer is not None
        assert CryptoDerivativesAnalyzer is not None
