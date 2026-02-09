"""TradingView Scanner Integration.

Live market screening powered by TradingView's screener API via tvscreener.
Supports stocks, crypto, forex, bonds, futures, and coins with 13,000+ fields.

Example:
    from src.tv_scanner import TVScannerEngine, PRESET_TV_SCANS

    engine = TVScannerEngine()
    report = engine.run_preset("momentum_breakout")
    for r in report.results:
        print(f"{r.symbol}: ${r.price} RSI={r.rsi} strength={r.signal_strength}")
"""

from src.tv_scanner.config import (
    AssetClass,
    TVFieldCategory,
    TVScanCategory,
    TVScannerConfig,
    TVTimeInterval,
    TV_FIELD_MAP,
)
from src.tv_scanner.models import (
    TVFieldSpec,
    TVFilterCriterion,
    TVPreset,
    TVScanReport,
    TVScanResult,
)
from src.tv_scanner.presets import (
    PRESET_TV_SCANS,
    get_all_tv_presets,
    get_tv_preset,
    get_tv_presets_by_category,
)
from src.tv_scanner.engine import TVScannerEngine
from src.tv_scanner.bridge import TVDataBridge

__all__ = [
    # Config
    "AssetClass",
    "TVFieldCategory",
    "TVScanCategory",
    "TVScannerConfig",
    "TVTimeInterval",
    "TV_FIELD_MAP",
    # Models
    "TVFieldSpec",
    "TVFilterCriterion",
    "TVPreset",
    "TVScanReport",
    "TVScanResult",
    # Presets
    "PRESET_TV_SCANS",
    "get_all_tv_presets",
    "get_tv_preset",
    "get_tv_presets_by_category",
    # Engine
    "TVScannerEngine",
    # Bridge
    "TVDataBridge",
]
