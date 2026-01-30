"""Crypto & Futures Expansion.

Multi-asset support including:
- Cryptocurrency integration with 5-factor model (value, momentum, quality, sentiment, network)
- Futures trading with contract management, auto-roll, and margin tracking
- International equities with FX rate management and currency hedging
- Cross-asset portfolio optimization with pre-built templates
- Unified risk management with cross-asset VaR and correlation regime detection

Example:
    from src.multi_asset import CryptoFactorModel, FuturesManager
    from src.multi_asset import CrossAssetOptimizer, UnifiedRiskManager

    # Crypto factors
    model = CryptoFactorModel()
    scores = model.compute_scores("BTC")

    # Futures
    fm = FuturesManager()
    spec = fm.get_contract_spec("ES")

    # Cross-asset optimization
    optimizer = CrossAssetOptimizer()
    portfolio = optimizer.from_template("balanced", symbols_by_class)
"""

from src.multi_asset.config import (
    AssetClass,
    CryptoCategory,
    FuturesCategory,
    SettlementType,
    MarginAlertLevel,
    ContractSpec,
    SUPPORTED_CRYPTO,
    SUPPORTED_FUTURES,
    INTL_MARKETS,
    DEFAULT_CONTRACT_SPECS,
    CROSS_ASSET_TEMPLATES,
    CryptoConfig,
    FuturesConfig,
    FXConfig,
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

from src.multi_asset.crypto import (
    CryptoDataProvider,
    CryptoFactorModel,
)

from src.multi_asset.futures import (
    FuturesManager,
)

from src.multi_asset.international import (
    FXRateProvider,
    InternationalMarketManager,
)

from src.multi_asset.cross_asset import (
    CrossAssetOptimizer,
)

from src.multi_asset.risk import (
    UnifiedRiskManager,
)

__all__ = [
    # Config
    "AssetClass",
    "CryptoCategory",
    "FuturesCategory",
    "SettlementType",
    "MarginAlertLevel",
    "ContractSpec",
    "SUPPORTED_CRYPTO",
    "SUPPORTED_FUTURES",
    "INTL_MARKETS",
    "DEFAULT_CONTRACT_SPECS",
    "CROSS_ASSET_TEMPLATES",
    "CryptoConfig",
    "FuturesConfig",
    "FXConfig",
    "MultiAssetConfig",
    "DEFAULT_MULTI_ASSET_CONFIG",
    # Models
    "CryptoAsset",
    "CryptoFactorScores",
    "OnChainMetrics",
    "FuturesContract",
    "FuturesPosition",
    "RollOrder",
    "MarginStatus",
    "FXRate",
    "IntlEquity",
    "AssetAllocation",
    "MultiAssetPortfolio",
    "CrossAssetRiskReport",
    # Crypto
    "CryptoDataProvider",
    "CryptoFactorModel",
    # Futures
    "FuturesManager",
    # International
    "FXRateProvider",
    "InternationalMarketManager",
    # Cross-Asset
    "CrossAssetOptimizer",
    # Risk
    "UnifiedRiskManager",
]
