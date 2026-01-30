"""Tests for PRD-12: Crypto & Futures Expansion.

Tests cover: config, models, crypto factor model, futures manager,
FX/international markets, cross-asset optimizer, unified risk, and imports.
"""

from datetime import date, datetime, time

import pytest
import numpy as np
import pandas as pd

from src.multi_asset.config import (
    AssetClass,
    CryptoCategory,
    FuturesCategory,
    SettlementType,
    MarginAlertLevel,
    SUPPORTED_CRYPTO,
    SUPPORTED_FUTURES,
    INTL_MARKETS,
    DEFAULT_CONTRACT_SPECS,
    CROSS_ASSET_TEMPLATES,
    MultiAssetConfig,
    DEFAULT_MULTI_ASSET_CONFIG,
)
from src.multi_asset.models import (
    CryptoAsset,
    CryptoFactorScores,
    OnChainMetrics,
    FuturesContract,
    FuturesPosition,
    RollOrder,
    MarginStatus,
    FXRate,
    IntlEquity,
    AssetAllocation,
    MultiAssetPortfolio,
    CrossAssetRiskReport,
)
from src.multi_asset.crypto import CryptoDataProvider, CryptoFactorModel
from src.multi_asset.futures import FuturesManager
from src.multi_asset.international import FXRateProvider, InternationalMarketManager
from src.multi_asset.cross_asset import CrossAssetOptimizer
from src.multi_asset.risk import UnifiedRiskManager


# =============================================================================
# Config Tests
# =============================================================================


class TestConfig:
    """Test configuration and constants."""

    def test_asset_class_enum(self):
        assert AssetClass.CRYPTO.value == "crypto"
        assert AssetClass.FUTURES.value == "futures"
        assert AssetClass.US_EQUITY.value == "us_equity"

    def test_supported_crypto(self):
        assert "BTC" in SUPPORTED_CRYPTO
        assert "ETH" in SUPPORTED_CRYPTO
        assert SUPPORTED_CRYPTO["BTC"] == CryptoCategory.MAJOR
        assert SUPPORTED_CRYPTO["UNI"] == CryptoCategory.DEFI

    def test_supported_futures(self):
        assert "ES" in SUPPORTED_FUTURES
        assert "CL" in SUPPORTED_FUTURES
        assert SUPPORTED_FUTURES["ES"] == FuturesCategory.EQUITY_INDEX
        assert SUPPORTED_FUTURES["GC"] == FuturesCategory.COMMODITY

    def test_intl_markets(self):
        assert "UK" in INTL_MARKETS
        assert "Japan" in INTL_MARKETS
        assert INTL_MARKETS["UK"]["currency"] == "GBP"

    def test_contract_specs(self):
        es = DEFAULT_CONTRACT_SPECS["ES"]
        assert es.multiplier == 50
        assert es.tick_value == 12.50
        assert es.margin_initial > 0

    def test_cross_asset_templates(self):
        assert "balanced" in CROSS_ASSET_TEMPLATES
        balanced = CROSS_ASSET_TEMPLATES["balanced"]
        total = sum(balanced.values())
        assert abs(total - 1.0) < 0.01

    def test_default_config(self):
        cfg = DEFAULT_MULTI_ASSET_CONFIG
        assert cfg.crypto.max_portfolio_pct == 0.15
        assert cfg.futures.roll_threshold_days == 5


# =============================================================================
# Model Tests
# =============================================================================


class TestModels:
    """Test data models."""

    def test_crypto_asset(self):
        btc = CryptoAsset(
            symbol="BTC", name="Bitcoin", category=CryptoCategory.MAJOR,
            price_usd=45000, market_cap=900e9, max_supply=21e6,
        )
        assert btc.fully_diluted_value == 45000 * 21e6

    def test_crypto_factor_scores(self):
        scores = CryptoFactorScores(
            symbol="ETH", value=0.7, momentum=0.8,
            quality=0.6, sentiment=0.5, network=0.9,
        )
        composite = scores.compute_composite()
        assert 0 < composite < 1

    def test_futures_contract(self):
        contract = FuturesContract(root="ES", contract_month="H25")
        assert contract.symbol == "ESH25"

    def test_futures_position(self):
        contract = FuturesContract(root="ES", contract_month="H25")
        pos = FuturesPosition(
            contract=contract, qty=2,
            avg_entry_price=5000, current_price=5050, multiplier=50,
        )
        assert pos.notional_value == 2 * 5050 * 50
        assert pos.unrealized_pnl == 2 * (5050 - 5000) * 50
        assert pos.side == "long"

    def test_futures_short_position(self):
        contract = FuturesContract(root="CL", contract_month="M25")
        pos = FuturesPosition(
            contract=contract, qty=-3,
            avg_entry_price=80, current_price=78, multiplier=1000,
        )
        assert pos.side == "short"
        assert pos.unrealized_pnl == -3 * (78 - 80) * 1000  # +6000

    def test_margin_status(self):
        ms = MarginStatus(total_margin_required=9000, total_margin_available=10000)
        ms.update()
        assert ms.utilization_pct == 0.9
        assert ms.alert_level == MarginAlertLevel.CRITICAL

    def test_margin_status_normal(self):
        ms = MarginStatus(total_margin_required=5000, total_margin_available=10000)
        ms.update()
        assert ms.alert_level == MarginAlertLevel.NORMAL

    def test_fx_rate(self):
        rate = FXRate(base="GBP", quote="USD", rate=1.27)
        assert rate.pair == "GBP/USD"
        assert abs(rate.inverse - 1 / 1.27) < 1e-6

    def test_intl_equity(self):
        eq = IntlEquity(
            symbol="VOD.L", name="Vodafone", exchange="LSE",
            currency="GBP", market="UK", price_local=100,
        )
        eq.convert_to_usd(1.27)
        assert eq.price_usd == 127.0

    def test_multi_asset_portfolio(self):
        port = MultiAssetPortfolio(
            name="test", total_value_usd=100000,
            allocations=[
                AssetAllocation("AAPL", AssetClass.US_EQUITY, 0.3),
                AssetAllocation("BTC", AssetClass.CRYPTO, 0.1),
                AssetAllocation("GC", AssetClass.COMMODITY, 0.1),
            ],
        )
        by_class = port.allocation_by_class
        assert by_class[AssetClass.US_EQUITY] == 0.3
        assert port.n_positions == 3


# =============================================================================
# Crypto Tests
# =============================================================================


class TestCryptoFactorModel:
    """Test crypto factor model."""

    @pytest.fixture
    def provider(self):
        dp = CryptoDataProvider()
        dp.register_asset(CryptoAsset(
            "BTC", "Bitcoin", CryptoCategory.MAJOR, price_usd=45000,
        ))
        dp.set_on_chain_metrics(OnChainMetrics(
            symbol="BTC", nvt_ratio=30, mvrv_ratio=1.5,
            stock_to_flow=50, active_addresses_24h=800000,
            transaction_count_24h=300000, hash_rate=400e18,
            staking_ratio=0.0, tvl=0, developer_commits_30d=100,
        ))
        rng = np.random.RandomState(42)
        prices = pd.Series(
            45000 * np.exp(np.cumsum(rng.normal(0.001, 0.03, 200))),
        )
        dp.set_price_history("BTC", prices)
        return dp

    def test_compute_scores(self, provider):
        model = CryptoFactorModel(provider)
        scores = model.compute_scores("BTC")

        assert scores.symbol == "BTC"
        assert scores.value > 0
        assert scores.momentum != 0
        assert scores.quality > 0
        assert scores.network > 0
        assert scores.composite != 0

    def test_rank_universe(self, provider):
        # Add a second asset
        provider.register_asset(CryptoAsset(
            "ETH", "Ethereum", CryptoCategory.MAJOR, price_usd=3000,
        ))
        provider.set_on_chain_metrics(OnChainMetrics(
            symbol="ETH", nvt_ratio=20, mvrv_ratio=1.2,
            tvl=50e9, developer_commits_30d=300,
            active_addresses_24h=500000,
        ))
        rng = np.random.RandomState(99)
        prices = pd.Series(
            3000 * np.exp(np.cumsum(rng.normal(0.0015, 0.04, 200))),
        )
        provider.set_price_history("ETH", prices)

        model = CryptoFactorModel(provider)
        ranked = model.rank_universe(["BTC", "ETH"], top_n=2)
        assert len(ranked) == 2
        assert ranked[0].composite >= ranked[1].composite

    def test_data_provider(self, provider):
        assert provider.get_asset("BTC") is not None
        assert provider.get_asset("DOGE") is None
        assert len(provider.get_all_assets()) == 1

        returns = provider.get_returns("BTC", periods=30)
        assert returns is not None
        assert len(returns) == 30


# =============================================================================
# Futures Tests
# =============================================================================


class TestFuturesManager:
    """Test futures contract management."""

    @pytest.fixture
    def fm(self):
        return FuturesManager()

    def test_get_contract_spec(self, fm):
        spec = fm.get_contract_spec("ES")
        assert spec is not None
        assert spec.multiplier == 50
        assert spec.tick_value == 12.50

    def test_get_unknown_spec(self, fm):
        assert fm.get_contract_spec("UNKNOWN") is None

    def test_front_month(self, fm):
        front = fm.get_front_month("ES", as_of=date(2025, 2, 15))
        assert front is not None
        assert front.startswith("ES")
        assert "H25" in front  # March 2025

    def test_next_contract(self, fm):
        next_c = fm.get_next_contract("ES", "H25")
        assert next_c == "ESM25"

    def test_next_contract_year_wrap(self, fm):
        next_c = fm.get_next_contract("ES", "Z25")
        assert next_c == "ESH26"

    def test_check_roll_needed(self, fm):
        contract = FuturesContract(
            root="ES", contract_month="H25",
            expiry=date.today() + __import__("datetime").timedelta(days=3),
        )
        pos = FuturesPosition(contract=contract, qty=1)
        roll = fm.check_roll(pos)
        assert roll is not None
        assert roll.old_contract == "ESH25"

    def test_check_roll_not_needed(self, fm):
        contract = FuturesContract(
            root="ES", contract_month="H25",
            expiry=date.today() + __import__("datetime").timedelta(days=30),
        )
        pos = FuturesPosition(contract=contract, qty=1)
        roll = fm.check_roll(pos)
        assert roll is None

    def test_margin_tracking(self, fm):
        contract = FuturesContract(root="ES", contract_month="H25")
        pos = FuturesPosition(
            contract=contract, qty=2,
            avg_entry_price=5000, current_price=5000,
            multiplier=50, margin_required=25300,
        )
        fm.add_position(pos)
        fm.set_margin_available(50000)

        status = fm.get_margin_status()
        assert status.utilization_pct > 0
        assert status.alert_level == MarginAlertLevel.NORMAL

    def test_calendar_spread(self, fm):
        spread = fm.build_calendar_spread("ES", "H25", "M25", qty=2)
        assert spread["type"] == "calendar_spread"
        assert spread["front_leg"]["qty"] == 2

    def test_position_lifecycle(self, fm):
        contract = FuturesContract(root="CL", contract_month="M25")
        pos = FuturesPosition(contract=contract, qty=5, margin_required=33000)
        fm.add_position(pos)
        assert len(fm.get_all_positions()) == 1

        fm.remove_position("CLM25")
        assert len(fm.get_all_positions()) == 0


# =============================================================================
# International / FX Tests
# =============================================================================


class TestFXRateProvider:
    """Test FX rate management."""

    @pytest.fixture
    def fx(self):
        provider = FXRateProvider()
        provider.set_rate("GBP", "USD", 1.27)
        provider.set_rate("EUR", "USD", 1.08)
        provider.set_rate("JPY", "USD", 0.0067)
        return provider

    def test_get_rate(self, fx):
        assert fx.get_rate("GBP", "USD") == 1.27

    def test_inverse_rate(self, fx):
        rate = fx.get_rate("USD", "GBP")
        assert rate is not None
        assert abs(rate - 1 / 1.27) < 1e-6

    def test_same_currency(self, fx):
        assert fx.get_rate("USD", "USD") == 1.0

    def test_cross_rate(self, fx):
        rate = fx.get_rate("GBP", "EUR")
        assert rate is not None
        # GBP/EUR = GBP/USD * USD/EUR
        expected = 1.27 * (1 / 1.08)
        assert abs(rate - expected) < 0.01

    def test_convert(self, fx):
        usd = fx.convert(100, "GBP", "USD")
        assert usd == 127.0

    def test_get_all_rates(self, fx):
        rates = fx.get_all_rates("USD")
        assert "GBP" in rates
        assert "EUR" in rates


class TestInternationalMarketManager:
    """Test international market management."""

    @pytest.fixture
    def intl(self):
        fx = FXRateProvider()
        fx.set_rate("GBP", "USD", 1.27)
        mgr = InternationalMarketManager(fx_provider=fx)
        mgr.register_equity(IntlEquity(
            symbol="VOD.L", name="Vodafone", exchange="LSE",
            currency="GBP", market="UK", price_local=100,
        ))
        return mgr

    def test_get_equity(self, intl):
        eq = intl.get_equity("VOD.L")
        assert eq is not None
        assert eq.currency == "GBP"

    def test_convert_to_usd(self, intl):
        eq = intl.get_equity("VOD.L")
        usd = intl.convert_to_usd(eq)
        assert usd == 127.0

    def test_supported_markets(self, intl):
        markets = intl.get_supported_markets()
        assert "UK" in markets
        assert "Japan" in markets

    def test_currency_exposure(self, intl):
        positions = [intl.get_equity("VOD.L")]
        exposure = intl.compute_currency_exposure(positions)
        assert "GBP" in exposure
        assert exposure["GBP"] == 127.0

    def test_hedge_ratios(self, intl):
        eq = intl.get_equity("VOD.L")
        eq.price_local = 1000
        hedges = intl.compute_hedge_ratios([eq], total_portfolio_value=5000)
        # 1270/5000 = 25.4% > 10% threshold
        assert "GBP" in hedges


# =============================================================================
# Cross-Asset Optimizer Tests
# =============================================================================


class TestCrossAssetOptimizer:
    """Test cross-asset portfolio optimization."""

    @pytest.fixture
    def optimizer(self):
        return CrossAssetOptimizer()

    def test_from_template(self, optimizer):
        symbols_by_class = {
            AssetClass.US_EQUITY: ["AAPL", "MSFT"],
            AssetClass.INTL_EQUITY: ["VOD.L"],
            AssetClass.CRYPTO: ["BTC"],
            AssetClass.FIXED_INCOME: ["TLT"],
            AssetClass.COMMODITY: ["GLD"],
            AssetClass.CASH: ["SHV"],
        }
        port = optimizer.from_template("balanced", symbols_by_class, 100_000)

        assert port.template == "balanced"
        assert port.n_positions > 0
        total_w = sum(a.weight for a in port.allocations)
        assert abs(total_w - 1.0) < 0.01

    def test_invalid_template(self, optimizer):
        with pytest.raises(ValueError, match="Unknown template"):
            optimizer.from_template("invalid", {}, 100_000)

    def test_optimize(self, optimizer):
        returns = {"AAPL": 0.10, "BTC": 0.30, "GLD": 0.05}
        rng = np.random.RandomState(42)
        cov_data = rng.randn(3, 3) * 0.01
        cov = pd.DataFrame(
            cov_data @ cov_data.T + np.eye(3) * 0.01,
            index=["AAPL", "BTC", "GLD"], columns=["AAPL", "BTC", "GLD"],
        )
        classes = {
            "AAPL": AssetClass.US_EQUITY,
            "BTC": AssetClass.CRYPTO,
            "GLD": AssetClass.COMMODITY,
        }

        port = optimizer.optimize(returns, cov, classes, total_capital=100_000)
        assert port.n_positions == 3
        total_w = sum(a.weight for a in port.allocations)
        assert abs(total_w - 1.0) < 1e-6

    def test_build_covariance(self, optimizer):
        rng = np.random.RandomState(42)
        returns = {
            "A": pd.Series(rng.normal(0, 0.02, 252)),
            "B": pd.Series(rng.normal(0, 0.03, 252)),
        }
        cov = optimizer.build_covariance(returns)
        assert cov.shape == (2, 2)
        assert cov.loc["A", "A"] > 0

    def test_risk_budget_allocation(self, optimizer):
        rng = np.random.RandomState(42)
        n = 3
        A = rng.randn(n, n) * 0.01
        cov = pd.DataFrame(
            A @ A.T + np.eye(n) * 0.01,
            index=["A", "B", "C"], columns=["A", "B", "C"],
        )
        budgets = {"A": 0.5, "B": 0.25, "C": 0.25}
        weights = optimizer.risk_budget_allocation(cov, budgets)

        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 1e-6


# =============================================================================
# Unified Risk Tests
# =============================================================================


class TestUnifiedRiskManager:
    """Test cross-asset risk management."""

    @pytest.fixture
    def risk_mgr(self):
        return UnifiedRiskManager()

    @pytest.fixture
    def sample_portfolio(self):
        return MultiAssetPortfolio(
            name="test", total_value_usd=100_000,
            allocations=[
                AssetAllocation("AAPL", AssetClass.US_EQUITY, 0.40, 40000),
                AssetAllocation("BTC", AssetClass.CRYPTO, 0.10, 10000),
                AssetAllocation("GLD", AssetClass.COMMODITY, 0.10, 10000),
                AssetAllocation("TLT", AssetClass.FIXED_INCOME, 0.30, 30000),
                AssetAllocation("VOD.L", AssetClass.INTL_EQUITY, 0.10, 10000,
                               currency="GBP"),
            ],
        )

    @pytest.fixture
    def sample_returns(self):
        rng = np.random.RandomState(42)
        return pd.DataFrame({
            "AAPL": rng.normal(0.0005, 0.015, 252),
            "BTC": rng.normal(0.001, 0.04, 252),
            "GLD": rng.normal(0.0002, 0.01, 252),
            "TLT": rng.normal(0.0001, 0.008, 252),
            "VOD.L": rng.normal(0.0003, 0.012, 252),
        })

    def test_compute_risk(self, risk_mgr, sample_portfolio, sample_returns):
        cov = sample_returns.cov() * 252
        report = risk_mgr.compute_portfolio_risk(
            sample_portfolio, sample_returns, cov,
        )

        assert report.total_var_95 < 0  # VaR is negative
        assert report.total_var_99 < report.total_var_95  # 99% is worse
        assert len(report.risk_by_asset_class) > 0
        assert report.currency_risk == 0.10  # VOD.L is GBP
        assert report.leverage_ratio == 1.0

    def test_margin_check(self, risk_mgr):
        status = risk_mgr.check_margin(9500, 10000)
        assert status.alert_level == MarginAlertLevel.CRITICAL

    def test_margin_alerts_normal(self, risk_mgr):
        risk_mgr.check_margin(5000, 10000)
        alerts = risk_mgr.get_margin_alerts()
        assert len(alerts) == 0

    def test_margin_alerts_warning(self, risk_mgr):
        risk_mgr.check_margin(8500, 10000)
        alerts = risk_mgr.get_margin_alerts()
        assert len(alerts) == 1
        assert alerts[0]["level"] == "warning"

    def test_margin_alerts_liquidation(self, risk_mgr):
        risk_mgr.check_margin(11500, 10000)
        alerts = risk_mgr.get_margin_alerts()
        assert alerts[0]["level"] == "liquidation"

    def test_correlation_regime(self, risk_mgr, sample_returns):
        cov = sample_returns.cov() * 252
        report = risk_mgr.compute_portfolio_risk(
            MultiAssetPortfolio("t", 100000, [
                AssetAllocation("AAPL", AssetClass.US_EQUITY, 0.5),
                AssetAllocation("BTC", AssetClass.CRYPTO, 0.5),
            ]),
            sample_returns, cov,
        )
        assert report.correlation_regime in ["normal", "elevated", "stress"]


# =============================================================================
# Module Import Tests
# =============================================================================


class TestModuleImports:
    """Test all public exports."""

    def test_import_config(self):
        from src.multi_asset import (
            AssetClass, SUPPORTED_CRYPTO, SUPPORTED_FUTURES,
            CROSS_ASSET_TEMPLATES, DEFAULT_MULTI_ASSET_CONFIG,
        )
        assert AssetClass.CRYPTO
        assert len(SUPPORTED_CRYPTO) > 0

    def test_import_models(self):
        from src.multi_asset import (
            CryptoAsset, FuturesContract, FXRate,
            MultiAssetPortfolio, CrossAssetRiskReport,
        )
        assert CryptoAsset
        assert FuturesContract

    def test_import_crypto(self):
        from src.multi_asset import CryptoDataProvider, CryptoFactorModel
        assert CryptoDataProvider
        assert CryptoFactorModel

    def test_import_futures(self):
        from src.multi_asset import FuturesManager
        assert FuturesManager

    def test_import_international(self):
        from src.multi_asset import FXRateProvider, InternationalMarketManager
        assert FXRateProvider

    def test_import_cross_asset(self):
        from src.multi_asset import CrossAssetOptimizer
        assert CrossAssetOptimizer

    def test_import_risk(self):
        from src.multi_asset import UnifiedRiskManager
        assert UnifiedRiskManager
